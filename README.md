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
- **AI Model**: Anthropic Claude Haiku 4.5 (vision — el fotoğrafını okur)
- **Deployment**: Render.com
- **API Entegrasyonu**: Google Places API

---

## 🛠️ Kurulum (Lokal Çalıştırmak İsteyenler İçin)

```bash
# 1. Repo'yu klonla
git clone https://github.com/kullaniciadi/astroline-app.git
cd astroline-app

# 2. Ortamı oluştur ve aktif et  (⚠️ Python 3.11 kullan — 3.14 desteklenmiyor)
py -3.11 -m venv venv            # Windows
# python3.11 -m venv venv        # macOS/Linux
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Gereksinimleri yükle (kökteki requirements.txt)
pip install -r requirements.txt

# 4. Ortam değişkenlerini ayarla (.env.example'ı kopyalayıp .env oluştur)
#    ANTHROPIC_API_KEY=sk-ant-...
#    GOOGLE_PLACES_API_KEY=your_google_places_key

# 5. Uygulamayı PROJE KÖKÜNDEN başlat (cd backend YAPMA — importlar kırılır)
uvicorn backend.main:app --reload
```

> ⚠️ Uygulama `from backend...` mutlak importları kullandığı için mutlaka proje
> kökünden çalıştırılmalıdır. `cd backend && uvicorn main:app` import hatası verir.

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
