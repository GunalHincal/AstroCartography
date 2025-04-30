# 🪐 Astroline: Astrocartography, El Falı ve Doğum Haritası Destekli Kişisel Yorumlama Uygulaması

🔗 [Canlı Uygulamayı Görüntüle](https://astrocartography.onrender.com)

Astroline, kullanıcıdan alınan doğum bilgileri, favori şehirler, gelecek hedefleri ve el fotoğrafı gibi kişisel veriler ışığında **astrolojik analizler, astrocartography yorumu, el falı (palmistry) analizi** ve doğum haritası değerlendirmesi sunar.

---

## 🌟 Özellikler

- 📍 **Astrocartography Analizi**Favori şehirleriniz üzerinden Venüs, Güneş, Mars gibi çizgilerin etkilerini analiz eder.
- ✋ **El Falı Analizi (Palmistry)**Yüklenen sol el fotoğrafından yaşam çizgisi, kalp çizgisi, kader çizgisi gibi alanlara özel yorumlar yapılır.
- 🌌 **Doğum Haritası Yorumu**Güneş burcu, Ay burcu, Yükselen burç ve ev konumları üzerinden kişisel bir değerlendirme yapılır.
- 🌍 **Şehir Öneri Sistemi (LLM Destekli)**Hedefleriniz ve haritanıza göre AI tarafından sizin için en uygun şehirler önerilir.
- 🧠 **Gemini API ile Kapsamlı LLM Analizi**
  Google Gemini Pro 1.5 modeli ile 1000+ kelimelik kişisel analizler oluşturulur.

---

## 🖼️ Kullanıcıdan Alınan Veriler

- Doğum tarihi, saati ve yeri
- Mevcut yaşadığı yer
- Gelecek hedefleri (maks. 5 adet)
- Yaşam zorlukları (opsiyonel)
- Sol el fotoğrafı (isteğe bağlı)
- Favori şehirler / ülkeler

---

## 🚀 Teknolojiler

- **Frontend**: HTML, CSS, JS (Vanilla)
- **Backend**: FastAPI (Python)
- **AI Model**: Google Gemini 1.5 Pro
- **Deployment**: Render.com
- **API Entegrasyonu**: Google Places API

---

## 🛠️ Kurulum (Lokal Çalıştırmak İsteyenler İçin)

```bash
# 1. Repo'yu klonla
git clone https://github.com/kullaniciadi/astroline-app.git
cd astroline-app

# 2. Ortamı oluştur ve aktif et
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Gereksinimleri yükle
pip install -r backend/requirements.txt

# 4. Ortam değişkenlerini ayarla (.env dosyası oluştur)
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_PLACES_API_KEY=your_google_places_key

# 5. Uygulamayı başlat
cd backend
uvicorn main:app --reload
```

https://astrocartography.onrender.com/

## 🎭 Sorumluluk Reddi

> **Astroline** uygulaması eğlence ve kişisel farkındalık amacıyla geliştirilmiştir. Yapay zekâ destekli astrolojik analizler, el falı ve doğum haritası yorumları bilimsel bir dayanağa sahip değildir.
>
> Uygulama; kullanıcıların kendilerini keşfetmelerine, düşünmelerine ve eğlenceli bir deneyim yaşamalarına katkı sağlamak için tasarlanmıştır.
>
> Lütfen bu yorumları yaşamınızda önemli kararlar alırken **tek ve mutlak kaynak** olarak değerlendirmeyin.



Her türlü geri bildiriminiz için ulaşabilirsiniz. Projeyi beğenip desteklemeyi unutmayın! 😊

**✨ Teşekkürler!**


## 🚀 Follow Me for More Updates

Stay connected and follow me for updates on my projects, insights, and tutorials:

* **LinkedIn:** **[Connect with me professionally to learn more about my work and collaborations](https://www.linkedin.com/in/gunalhincal)**
* **Medium:** **[Check out my blog for articles on technology, data science, and more!](https://medium.com/@hincalgunal)**

Feel free to reach out or follow for more updates! 😊 Have Fun!
