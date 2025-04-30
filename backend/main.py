# backend/main.py

# API sunucusunu çalıştırmak, HTTP isteklerini almak, sonuçları döndürmek için FastAPI kullanıyoruz.
# FastAPI, asenkron programlama ile yüksek performanslı web uygulamaları geliştirmek için ideal bir framework'tür.
# main.py sadece FastAPI sunucusu ve endpointlerin tanımıyla uğraşmalı. Mantıksal iş (prompt oluşturma gibi) ayrı dosyada olmalı.
# Yarın bir gün prompt yapısını değiştirmek, geliştirmek istersek sadece utils.py'yi güncelleriz. main.py dosyasına dokunmamıza gerek kalmaz.
# main.py daha sade kalır, sadece akışı yönetir (save_answer, upload_hand_image, analyze gibi). Karmaşa olmaz.
# İleride farklı analiz tipleri (örneğin sadece astrocartography analizi, sadece el falı analizi) eklemek istersek utils.py içinde yeni fonksiyonlar yazıp yönlendirme yaparız. main.py yine temiz kalır.
# utils.py'yi bağımsız test edebilirsin. Prompt doğru hazırlanıyor mu diye tek başına unit test bile yazabiliriz. (İleride büyürse çok işimize yarar.)



# backend/main.py

from fastapi import FastAPI, UploadFile, Form, Request, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from dotenv import load_dotenv
import google.generativeai as genai
from utils import analyze_user
from utils import extract_table_from_analysis


# 🌍 Ortam değişkenlerini yükle
load_dotenv()

# API Anahtarlarını al
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

# Gemini ayarlarını yapılandır
genai.configure(api_key=GEMINI_API_KEY)

# 🔮 Gemini Modeli başlat
model = genai.GenerativeModel("gemini-1.5-pro-002")

# 🚀 FastAPI app oluştur
app = FastAPI()

# 🎨 Frontend klasörlerini bağla
app.mount("/static", StaticFiles(directory="../frontend/static"), name="static")
templates = Jinja2Templates(directory="../frontend/templates")


# 🧠 Geçici kullanıcı veri deposu (in-memory)
user_data = {}

# 🏠 Ana sayfa
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 📥 Kullanıcıdan gelen her cevabı kaydet
@app.post("/save_answer")
async def save_answer(key: str = Form(...), value: str = Form(...)):
    user_data[key] = value
    return {"message": "Cevap kaydedildi."}

# 🖐️ El fotoğrafı yükle
@app.post("/upload_hand_image")
async def upload_hand_image(file: UploadFile = File(...)):
    upload_folder = os.path.join("backend", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    file_location = os.path.join(upload_folder, file.filename)
    with open(file_location, "wb") as f:
        f.write(await file.read())

    user_data["hand_image"] = file_location
    return {"message": "El fotoğrafı yüklendi."}

# 🔎 Kullanıcı verilerini oku
async def get_user_answers():
    return user_data

# 🧠 Analiz başlat
@app.post("/analyze")
async def analyze():
    form_data = await get_user_answers()

    # Analizi al
    raw_analysis = analyze_user(form_data, model)

    # ** işaretlerini temizle
    cleaned = raw_analysis.replace("**", "")

    # Tabloyu ayrıştır
    cleaned_without_table, html_table = extract_table_from_analysis(cleaned)

    # "Sonuç" bölümünü sona taşı
    if "Sonuç:" in cleaned_without_table:
        parts = cleaned_without_table.split("Sonuç:")
        main_part = parts[0].strip()
        result_part = parts[1].strip() if len(parts) > 1 else ""
        cleaned_without_table = main_part
    else:
        result_part = ""

    final_text = cleaned_without_table + "\n\n" + html_table

    if result_part:
        final_text += "\n\n📝 Sonuç:\n" + result_part

    return JSONResponse(content={"analysis": final_text})

# 🔐 Google Maps API anahtarı
@app.get("/api/get-google-key")
async def get_google_key():
    return JSONResponse(content={"key": GOOGLE_PLACES_API_KEY})

# (isteğe bağlı) Gemini API key endpoint
@app.get("/api/get-gemini-key")
async def get_gemini_key():
    return JSONResponse(content={"key": GEMINI_API_KEY})


# uvicorn backend.main:app --reload