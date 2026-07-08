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
from dotenv import load_dotenv
from anthropic import Anthropic
from backend.utils import analyze_user
from backend.utils import extract_table_from_analysis
from backend.hand_analysis import analyze_hand_image
from uuid import uuid4
import asyncio
# 📍 Koordinatlara göre TimeZone hesaplama
from fastapi import Query
import httpx
import asyncio
import threading

# 🌍 Ortam değişkenlerini yükle
load_dotenv()


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

# 🔮 Claude (Anthropic) istemcisini başlat — anahtar ortam değişkeninden okunur.
# Model seçimi backend/utils.py içindeki CLAUDE_MODEL sabitindedir (şu an Haiku 4.5).
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

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


# 🏠 Ana sayfa (GET ve HEAD — HEAD'de de 405 yerine 200 döner)
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def home(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        user_id = str(uuid4())
        # Yeni Starlette imzası: TemplateResponse(request, name, context=...)
        response = templates.TemplateResponse(request, "index.html")
        response.set_cookie(key="user_id", value=user_id, httponly=True, samesite="lax")
        print(f"🆔 Yeni kullanıcıya ID atandı: {user_id}")
        return response
    else:
        print(f"👤 Var olan kullanıcı tekrar giriş yaptı: {user_id}")
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

# 🗐 El fotoğrafı yükle
@app.post("/upload_hand_image")
async def upload_hand_image(request: Request, file: UploadFile = File(...)):
    try:
        file_location = await save_uploaded_image(file)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    # Cookie'den kullanıcı kimliği al
    user_id = request.cookies.get("user_id", "default")
    # Kullanıcı verisi yoksa başlat
    if user_id not in user_data:
        user_data[user_id] = {}

    # 🔸 Frontend'in kullanabileceği yol
    relative_path = f"static/uploads/{os.path.basename(file_location)}"

    # Görseli kaydet ve analiz et
    user_data[user_id]["hand_image"] = file_location
    palm_prompt = analyze_hand_image(file_location)
    user_data[user_id]["palm_analysis"] = palm_prompt

    return {"message": "El fotoğrafı yüklendi ve analiz edildi.", "path": relative_path}

# 🔎 Kullanıcı verilerini oku
async def get_user_answers(request: Request):
    user_id = request.cookies.get("user_id")
    return user_data.get(user_id, {})

@app.post("/analyze")
async def analyze(request: Request):
    form_data = await request.form()
    user_data = dict(form_data)

    hand_image = form_data.get("hand_image")
    file_location = None
    image_url = None  # Çizgili el görselinin web yolu (/static/...)

    if hand_image and hasattr(hand_image, "filename") and hand_image.filename:
        try:
            file_location = await save_uploaded_image(hand_image)
            user_data["hand_image"] = file_location
        except ValueError as e:
            return JSONResponse(content={"analysis": f"❌ {e}"}, status_code=400)
    else:
        user_data["hand_image"] = None

    # ✅ El görseli varsa analiz et (ve hata yoksa palm_analysis içine ekle)
    if user_data.get("hand_image"):
        from backend.hand_analysis import analyze_hand_image, detect_palm_lines

        # 🖐️ 1. El falı analizi (palm_result)
        palm_result = analyze_hand_image(user_data["hand_image"])
        if "error" not in palm_result:
            user_data["palm_analysis"] = palm_result

        # 📸 2. El çizgilerini sınıflandırıp renklendiren görsel üret
        try:
            processed_abs_path, image_url = detect_palm_lines(user_data["hand_image"])
        except Exception as e:
            print(f"⚠️ El çizgisi görseli üretilemedi: {e}")
            processed_abs_path = None

        # 🧹 3. 5 dakika sonra hem orijinal hem analizli görseli sil
        def _safe_remove(p):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass

        threading.Timer(300, _safe_remove, args=[file_location]).start()
        if processed_abs_path:
            threading.Timer(300, _safe_remove, args=[processed_abs_path]).start()

    # 🤖 LLM (Claude) ile genel analiz üret
    raw_analysis = analyze_user(user_data, anthropic_client)

    if raw_analysis is None:
        return JSONResponse(content={"analysis": "❌ Gerekli bilgiler eksik. Lütfen formu eksiksiz doldurun."}, status_code=400)

    analysis_text, html_table = extract_table_from_analysis(raw_analysis)

    return JSONResponse(content={
        "text": analysis_text,
        "table": html_table,
        "image_url": image_url  # ✅ Görsel frontend'e gönderilir
    })

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