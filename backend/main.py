# backend/main.py

# API sunucusunu çalıştırmak, HTTP isteklerini almak, sonuçları döndürmek için FastAPI kullanıyoruz.
# FastAPI, asenkron programlama ile yüksek performanslı web uygulamaları geliştirmek için ideal bir framework'tür.
# main.py sadece FastAPI sunucusu ve endpointlerin tanımıyla uğraşmalı. Mantıksal iş (prompt oluşturma gibi) ayrı dosyada olmalı.
# Yarın bir gün prompt yapısını değiştirmek, geliştirmek istersek sadece utils.py'yi güncelleriz. main.py dosyasına dokunmamıza gerek kalmaz.
# main.py daha sade kalır, sadece akışı yönetir (save_answer, upload_hand_image, analyze gibi). Karmaşa olmaz.
# İleride farklı analiz tipleri (örneğin sadece astrocartography analizi, sadece el falı analizi) eklemek istersek utils.py içinde yeni fonksiyonlar yazıp yönlendirme yaparız. main.py yine temiz kalır.
# utils.py'yi bağımsız test edebilirsin. Prompt doğru hazırlanıyor mu diye tek başına unit test bile yazabiliriz. (İleride büyürse çok işimize yarar.)



# backend/main.py

import sys
# 🪟 Windows konsolu (cp1254) emoji içeren print()'lerde çökebilir; UTF-8'e sabitle.
# Bu yapılmazsa emoji basan endpoint'ler UnicodeEncodeError ile 500 döner.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from fastapi import FastAPI, UploadFile, Form, Request, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, UploadFile, File
from pathlib import Path
import os
import shutil
import json
import time
import logging
import traceback
from dotenv import load_dotenv
from anthropic import AsyncAnthropic
try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None
from backend.utils import analyze_user
from backend.utils import extract_table_from_analysis
from uuid import uuid4
import asyncio
# 📍 Koordinatlara göre TimeZone hesaplama
from fastapi import Query
import httpx
import asyncio
import threading

# 🌍 Ortam değişkenlerini yükle
load_dotenv()

# 📝 Loglama — Render loglarında zaman damgalı, seviyeli, aranabilir çıktı.
logger = logging.getLogger("astroline")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s astroline | %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

# 🛰️ Sentry — hata izleme. DSN yalnızca ortam değişkeninden okunur (koda gömülmez).
# DSN yoksa (lokal geliştirme) Sentry sessizce devre dışı kalır.
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN and sentry_sdk:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("APP_ENV", "development"),  # lokal/canlı hataları ayır
        send_default_pii=False,     # IP/başlık gönderme (gizlilik). İstersen True yap.
        enable_logs=True,           # logları Sentry'ye ilet
        traces_sample_rate=0.3,     # performans örnekleme; kotayı korumak için 0.3
    )
    logger.info("Sentry aktif")


# 🧐 Geçici kullanıcı veri deposu (in-memory)
# {"user_id": {"birth_date": ..., "hand_image": ..., ...}} 
# # Bu veri tabanı yerine kullanılabilir. Ancak uygulama kapandığında veriler kaybolur. 
# Kalıcı bir veri tabanı (örneğin SQLite, PostgreSQL) kullanmak daha iyi olur.
user_data = {}  # {user_id: {"key": value}}

# 🔁 USER VERİSİNİ 3 DK SONRA TEMİZLEME FONKSİYONU
async def clear_user_data_later(user_id: str, delay: int = 180):  # 180 saniye = 3 dakika
    await asyncio.sleep(delay)
    if user_id in user_data:
        del user_data[user_id]
        print(f"🩹 {user_id} verisi silindi (timeout sonrası)")


# API Anahtarlarını al
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

# 🔮 Claude (Anthropic) ASENKRON istemci — LLM çağrısı olay döngüsünü bloklamaz.
# Model seçimi backend/utils.py içindeki CLAUDE_MODEL sabitindedir (şu an Haiku 4.5).
anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# 🚀 FastAPI app oluştur
app = FastAPI()

# 🎨 Frontend klasörlerini bağla
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "frontend", "static", "uploads")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "frontend", "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "frontend", "templates"))

# 🔒 Güvenli dosya yükleme ayarları
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB


async def save_uploaded_image(file: UploadFile) -> str:
    """Yüklenen el görselini güvenli şekilde diske kaydeder ve tam yolu döner.

    - Uzantı whitelist kontrolü (path traversal ve keyfi dosya türlerini engeller)
    - Rastgele (uuid) dosya adı — kullanıcının gönderdiği isim asla kullanılmaz
    - Boyut sınırı (DoS / disk doldurma koruması)
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Geçersiz dosya türü. Yalnızca JPG, PNG veya WEBP yükleyin.")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Dosya çok büyük (maksimum 8 MB).")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid4().hex}{ext}"
    file_location = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_location, "wb") as f:
        f.write(content)
    return file_location

# ❤️ Sağlık kontrolü (UptimeRobot / uptime monitoring için)
# GET ve HEAD'e hızlıca 200 döner; DB/dosya/şablon işi YOK, auth YOK.
# UptimeRobot ücretsiz planı varsayılan olarak HEAD kullanır — ikisi de destekli.
@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}


# 🧯 Global hata yakalayıcı — yakalanmamış her exception'ı TAM traceback +
# hangi endpoint + hangi kullanıcı bilgisiyle loglar. Render loglarında görünür.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    user_id = request.cookies.get("user_id", "?")
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error(
        "UNHANDLED %s %s | user=%s | %s\n%s",
        request.method, request.url.path, user_id, repr(exc), tb,
    )
    # Sentry'ye de gönder — catch-all handler olmasa Sentry otomatik yakalardı,
    # handler exception'ı "yuttuğu" için burada elle raporluyoruz.
    if sentry_sdk:
        sentry_sdk.set_tag("user_cookie", user_id)
        sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Beklenmeyen bir sunucu hatası oluştu. Kayıt altına alındı, lütfen tekrar deneyin."},
    )


# 📡 Tarayıcı (client) tarafındaki hataları toplar → Render loglarına yazar.
# "Sayfa açılmadı / analiz çalışmadı" gibi olayların kaynağını görmemizi sağlar.
@app.post("/client-log")
async def client_log(request: Request):
    user_id = request.cookies.get("user_id", "?")
    try:
        data = await request.json()
    except Exception:
        data = {"raw": (await request.body()).decode("utf-8", "replace")[:500]}
    logger.warning("CLIENT user=%s rid=%s | %s",
                   user_id, data.get("request_id", "-"),
                   json.dumps(data, ensure_ascii=False)[:1200])
    if sentry_sdk:
        rid = data.get("request_id")
        if rid:
            sentry_sdk.set_tag("request_id", rid)
        sentry_sdk.capture_message(
            f"CLIENT {data.get('type', '?')}: {data.get('message', '')}",
            level="warning",
        )
    return {"ok": True}


# 🏠 Ana sayfa (GET ve HEAD — HEAD'de de 405 yerine 200 döner)
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def home(request: Request):
    # 🩺 HEAD (health/probe) isteklerinde kullanıcı ID ATAMA ve LOG BASMA.
    # UptimeRobot/Render probe'ları "kullanıcı" gibi görünmesin.
    if request.method != "GET":
        return templates.TemplateResponse(request, "index.html")

    user_id = request.cookies.get("user_id")
    if not user_id:
        # Sadece gerçek GET sayfa açılışında yeni ID ata + Set-Cookie yaz + logla
        user_id = str(uuid4())
        response = templates.TemplateResponse(request, "index.html")
        response.set_cookie(key="user_id", value=user_id, httponly=True, samesite="lax")
        logger.info("Yeni kullanıcıya ID atandı: %s", user_id)
        return response
    return templates.TemplateResponse(request, "index.html")

# 📅 Kullanıcıdan gelen her cevabı kaydet
@app.post("/save_answer")
async def save_answer(request: Request, key: str = Form(...), value: str = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return JSONResponse(content={"error": "Kullanıcı ID bulunamadı."}, status_code=400)

    is_new_user = user_id not in user_data
    if is_new_user:
        user_data[user_id] = {}
        asyncio.create_task(clear_user_data_later(user_id))  # ⏱️ 3 dk sonra silme başlat
        print(f"📂 Yeni kullanıcı verisi oluşturuldu: {user_id}")

    user_data[user_id][key] = value
    print(f"✅ [{user_id}] için kaydedilen veri: {key} = {value}")
    return {"message": "Cevap kaydedildi."}

# 🔎 Kullanıcı verilerini oku
async def get_user_answers(request: Request):
    user_id = request.cookies.get("user_id")
    return user_data.get(user_id, {})

@app.post("/analyze")
async def analyze(request: Request):
    t0 = time.monotonic()
    form_data = await request.form()
    user_data = dict(form_data)

    # 🔗 İstek kimliği — frontend gönderirse onu kullan, yoksa üret. Böylece
    # Sentry (client-log) ile Render backend loglarını AYNI rid ile eşleştiririz.
    request_id = (str(user_data.get("request_id") or "").strip() or uuid4().hex)[:36]
    user_id = request.cookies.get("user_id", "?")
    if sentry_sdk:
        sentry_sdk.set_tag("request_id", request_id)

    hand_image = form_data.get("hand_image")
    has_hand = bool(hand_image and hasattr(hand_image, "filename") and hand_image.filename)

    # 🔎 Başlangıç logu — PRIVACY-SAFE: sadece meta veri, görsel İÇERİĞİ/base64 ASLA loglanmaz.
    logger.info(
        "ANALYZE start | rid=%s user=%s hand=%s name=%s type=%s size=%s",
        request_id, user_id, has_hand,
        getattr(hand_image, "filename", None) if has_hand else None,
        getattr(hand_image, "content_type", None) if has_hand else None,
        getattr(hand_image, "size", None) if has_hand else None,
    )

    file_location = None
    image_url = None  # El çizgisi overlay'i kaldırıldı; foto yalnızca vision modeline gider

    try:
        if has_hand:
            try:
                file_location = await save_uploaded_image(hand_image)
                user_data["hand_image"] = file_location
                logger.info("ANALYZE image saved | rid=%s size_bytes=%s",
                            request_id, os.path.getsize(file_location))
            except ValueError as e:
                logger.warning("ANALYZE bad image | rid=%s %s", request_id, e)
                return JSONResponse(content={"analysis": f"❌ {e}", "request_id": request_id}, status_code=400)

            # 🧹 Yüklenen görseli 5 dakika sonra sil (kalıcı saklanmaz)
            def _safe_remove(p):
                try:
                    if p and os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
            threading.Timer(300, _safe_remove, args=[file_location]).start()
        else:
            user_data["hand_image"] = None

        # 🤖 LLM (Claude) — asenkron. El fotoğrafını vision olarak okur (overlay çizmeden).
        raw_analysis = await analyze_user(user_data, anthropic_client)

        if raw_analysis is None:
            logger.warning("ANALYZE missing-info | rid=%s", request_id)
            return JSONResponse(
                content={"analysis": "❌ Gerekli bilgiler eksik. Lütfen formu eksiksiz doldurun.", "request_id": request_id},
                status_code=400,
            )

        analysis_text, html_table = extract_table_from_analysis(raw_analysis)
        elapsed = int((time.monotonic() - t0) * 1000)
        logger.info("ANALYZE success | rid=%s status=success elapsed_ms=%d hand_used=%s",
                    request_id, elapsed, bool(user_data.get("hand_image")))
        return JSONResponse(content={
            "text": analysis_text,
            "table": html_table,
            "image_url": image_url,
            "request_id": request_id,
        })

    except Exception as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        logger.error("ANALYZE error | rid=%s status=error elapsed_ms=%d %s: %s",
                     request_id, elapsed, type(exc).__name__, exc, exc_info=True)
        if sentry_sdk:
            sentry_sdk.capture_exception(exc)
        return JSONResponse(
            status_code=500,
            content={"error": "Analiz sırasında bir hata oluştu.", "request_id": request_id},
        )

# 🔐 Google Maps (Places) API anahtarı
# NOT: Bu anahtar tarayıcıda Maps JS API'yi yüklemek için gereklidir; bu yüzden
# frontend'e verilmesi normaldir. GÜVENLİK için anahtarı Google Cloud Console'da
# mutlaka HTTP referrer (domain) ve API kısıtlamasıyla sınırlandır.
@app.get("/api/get-google-key")
async def get_google_key():
    return JSONResponse(content={"key": GOOGLE_PLACES_API_KEY})

# ⚠️ GÜVENLİK: Gemini API anahtarını döndüren endpoint kaldırıldı.
# Gemini anahtarı yalnızca sunucu tarafında kullanılmalıdır; tarayıcıya
# sızdırılırsa kötüye kullanılıp faturalandırılabilir.

@app.get("/api/timezone")
async def get_timezone(lat: float = Query(...), lng: float = Query(...), timestamp: int = Query(...)):
    try:
        url = (
            f"https://maps.googleapis.com/maps/api/timezone/json?"
            f"location={lat},{lng}&timestamp={timestamp}&key={GOOGLE_PLACES_API_KEY}"
        )
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()

        raw_offset = data.get("rawOffset", 0)
        dst_offset = data.get("dstOffset", 0)
        total_offset_hours = (raw_offset + dst_offset) / 3600

        # "+03:00" gibi formatla
        hours = int(total_offset_hours)
        minutes = int((total_offset_hours - hours) * 60)
        timezone_str = f"{'+' if hours >= 0 else '-'}{abs(hours):02d}:{abs(minutes):02d}"

        return {"timezone": timezone_str}

    except Exception as e:
        return {"error": str(e)}


# uvicorn backend.main:app --reload
# uvicorn backend.main:app --reload --port 8001