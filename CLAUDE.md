# CLAUDE.md

Bu dosya, bu depoda çalışan Claude Code (ve diğer AI ajanları) için rehberdir.

## Proje Özeti

**Astroline**, kullanıcının doğum bilgileri, hedefleri, sevdiği ülkeler ve (opsiyonel)
sol el fotoğrafından yola çıkarak **astrocartography**, **doğum haritası** ve **el falı
(palmistry)** analizi üreten bir web uygulamasıdır. Nihai yorum Google Gemini ile
oluşturulur. Sonuçta kişiye hangi ülke/şehir ve **kültüre** ait hissedeceğine dair
öneriler sunulur.

> ⚠️ Eğlence ve kişisel farkındalık amaçlıdır; bilimsel dayanağı yoktur.

## Teknoloji Yığını

- **Backend:** FastAPI (Python), Uvicorn
- **Frontend:** Vanilla HTML/CSS/JS (Jinja2 template), tek sayfa çok adımlı form
- **LLM:** Anthropic Claude (vision) — `anthropic` SDK. Model `backend/utils.py`
  içindeki `CLAUDE_MODEL` sabitinde (şu an `claude-haiku-4-5`: ucuz+hızlı; büyüyünce
  `claude-sonnet-5`). El fotoğrafı modele base64 görsel olarak gönderilir (gerçek vision).
- **Astroloji:** `flatlib` (doğum haritası)
- **Görüntü işleme:** OpenCV + MediaPipe (el landmark tespiti + çizgi sınıflandırma)
- **Harita/konum:** Google Maps JS (Places Autocomplete), Google TimeZone API
- **Deploy:** Render.com

## Dizin Yapısı

```
astroline-app/
├── requirements.txt          # ✅ TEK gerçek bağımlılık listesi (kök)
├── .env.example              # Ortam değişkeni şablonu
├── backend/
│   ├── main.py               # FastAPI app, endpoint'ler, dosya yükleme
│   ├── utils.py              # Prompt oluşturma + LLM çağrısı + tablo ayıklama
│   ├── astro_utils.py        # flatlib ile doğum haritası hesabı (TEK kaynak)
│   ├── hand_analysis.py      # MediaPipe/OpenCV el çizgisi tespiti + sınıflandırma
│   └── requirements.txt      # Sadece köke yönlendiren pointer (kullanma)
└── frontend/
    ├── templates/index.html  # Çok adımlı form + sonuç alanı
    └── static/
        ├── app.js            # Adım geçişleri, form gönderimi, Google Maps
        ├── style.css         # Kozmik tema
        ├── uploads/          # (gitignore) yüklenen el görselleri, 5 dk sonra silinir
        └── processed/        # (gitignore) çizgileri renklendirilmiş çıktı görseli
```

## Çalıştırma (lokal)

**⚠️ Python sürümü: 3.11 kullan (3.12 de olur).** Python 3.14 ile ÇALIŞMAZ:
`flatlib` eski `pyswisseph`'e bağlı ve 3.14 için hiç wheel yok, kaynaktan da derlenmiyor.
Ayrıca `mediapipe` 0.10.18'in `solutions` API'si için 3.11/3.12 wheel'i gerekir.

**Önemli:** Uygulama **proje kökünden** başlatılmalıdır; çünkü kod `from backend...`
biçiminde mutlak import kullanır. `cd backend` yapıp `uvicorn main:app` çalıştırmak
import hatası verir.

```bash
py -3.11 -m venv venv           # Windows: mutlaka 3.11
# python3.11 -m venv venv       # macOS/Linux
.\venv\Scripts\activate          # Windows PowerShell
# source venv/bin/activate       # macOS/Linux
pip install -r requirements.txt

# .env dosyasını oluştur (bkz. .env.example) ve anahtarları gir
uvicorn backend.main:app --reload
```

Uygulama: http://127.0.0.1:8000

## Mimari Notları / Konvansiyonlar

- **İş mantığı `utils.py`'de, akış `main.py`'de.** Prompt yapısını değiştirirken
  `utils.py`'yi düzenle; `main.py` sade kalsın.
- **Doğum haritası hesabı yalnızca `astro_utils.calculate_birth_chart` içindedir.**
  Başka yerde ikinci bir tanım açma (eskiden `utils.py`'de çakışan hatalı bir kopya vardı).
- **flatlib tarih formatı `YYYY/MM/DD`** ister; HTML `type=date` ise `YYYY-MM-DD` verir.
  Dönüşüm `astro_utils._normalize_date` içinde yapılır.
- **Form alan adları:** koordinat/timezone alanları `birth_lat`, `birth_lng`,
  `birth_timezone` adıyla gelir. `create_prompt` bunları (eski `latitude` vb. ile geri
  uyumlu şekilde) okur.
- **El çizgisi renkleri sabittir** ve frontend açıklama kutusuyla eşleşir:
  kalp=kırmızı, yaşam=yeşil, kafa=turuncu, kader=mor (`hand_analysis.LINE_COLORS`).
  Çizgiler MediaPipe avuç ROI'sine göre konum+eğimle sınıflandırılır.
- **Kullanıcı verisi in-memory** (`user_data` dict), 3 dakika sonra otomatik silinir.
  Kalıcılık gerekiyorsa SQLite/Postgres'e taşınmalı.
- Yüklenen ve işlenen görseller **5 dakika sonra** silinir.

## Güvenlik Kuralları (bozma!)

- **LLM API anahtarı (ANTHROPIC_API_KEY) asla tarayıcıya gönderilmez.** Yalnızca
  sunucu tarafında `Anthropic()` istemcisinde kullanılır; anahtar döndüren endpoint yok.
- **Dosya yüklemeleri** `main.save_uploaded_image` üzerinden yapılır: uzantı whitelist'i
  (`.jpg/.jpeg/.png/.webp`), 8 MB sınırı ve **uuid dosya adı** (path traversal koruması).
  Kullanıcının gönderdiği dosya adını doğrudan kullanma.
- Google Maps anahtarı frontend'e verilir (Maps JS için gerekli); Cloud Console'da
  referrer/API kısıtlaması ile sınırlandırılmalıdır.

## Sık Karşılaşılan Sorunlar

- **`mediapipe==0.10.9` bulunamıyor:** İki katmanlı sorun:
  (1) 0.10.9 yeni Python (3.14) için wheel sunmuyor;
  (2) 0.10.30+ sürümleri eski `mp.solutions.hands` API'sini tamamen kaldırdı.
  Çözüm: **`mediapipe==0.10.18`** (hem `solutions` içerir hem protobuf 4.x'e izin verir).
- **`pyswisseph` derlenmiyor / wheel yok (Python 3.14):** Beklenen; Python 3.11 kullan.
- **protobuf çakışması:** `mediapipe` protobuf<5, `google-generativeai` stack'i protobuf 5
  istiyor olabilir. `requirements.txt` bunu `protobuf<5` + `google-api-core<2.20` +
  `grpcio-status<1.63` ile çözer. `pip check` temiz olmalı.
- **`module 'mediapipe' has no attribute 'solutions'`:** Yanlış mediapipe sürümü (0.10.30+).
  0.10.18'e sabitle. Import `from mediapipe.python.solutions import hands` şeklindedir.
- **Windows'ta emoji `print()` 500 veriyor (`UnicodeEncodeError` cp1254):** `main.py`
  başlangıçta stdout/stderr'i UTF-8'e sabitler; bu bloğu silme.
- **Doğum haritası "Bilinmiyor" çıkıyor:** lat/lng/timezone gelmiyordur (Places
  Autocomplete seçilmeden yazıldıysa gizli alanlar boş kalır) veya tarih/saat eksik.
