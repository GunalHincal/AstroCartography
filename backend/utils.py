# backend/utils.py

# Kullanıcı verilerinden prompt hazırlamak, LLM çağrısı yapmak, el fotoğrafı silmek gibi iş mantığı işlemleri yapmak için kullanılacak fonksiyonlar burada tanımlanır.
# Bu sayede main.py dosyası daha sade ve okunabilir olur. Ayrıca ileride farklı analiz türleri eklemek istediğimizde sadece bu dosyayı güncelleyerek işimizi halledebiliriz.

import re
import os
import base64
import asyncio
import cv2
from typing import Tuple, Optional
from anthropic import AsyncAnthropic

# 🖐️ Vision için: yüklenen el görselini modele göndereceğimiz medya tipleri
_IMAGE_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _build_image_block(image_path: str) -> Optional[dict]:
    """El görselini Claude vision formatında (base64) bir içerik bloğuna çevirir.
    Belleği ve token maliyetini düşürmek için görseli max 1400px'e küçültür."""
    ext = os.path.splitext(image_path)[1].lower()
    media_type = _IMAGE_MEDIA_TYPES.get(ext)
    if not media_type or not os.path.exists(image_path):
        return None

    # Küçült + JPEG'e yeniden kodla (8 MB foto -> ~150 KB; hız, bellek ve maliyet kazancı)
    try:
        img = cv2.imread(image_path)
        if img is not None:
            h, w = img.shape[:2]
            longest = max(h, w)
            if longest > 1400:
                scale = 1400 / longest
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                data = base64.standard_b64encode(buf.tobytes()).decode("utf-8")
                return {"type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}
    except Exception:
        pass

    # Yeniden kodlama başarısızsa orijinali gönder
    with open(image_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {"type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data}}


# ⚠️ Doğum haritası hesaplaması tek bir yerde (astro_utils.py) tutulur.
# Buradaki eski, hatalı ikinci tanım kaldırıldı (Datetime'ı eksik argümanla
# çağırıyor ve import edilen doğru fonksiyonu gölgeliyordu).
from backend.astro_utils import calculate_birth_chart, empty_chart
from backend.hand_analysis import detect_palm_lines


def format_goals(goals):
    if not goals:
        return "Belirtilmemiş"
    if isinstance(goals, str):
        return goals
    return "\n".join([f"{i + 1}. {goal}" for i, goal in enumerate(goals)])


_PLANET_SYMBOLS = {
    "Güneş": "☀️", "Ay": "🌙", "Merkür": "☿️", "Venüs": "♀️", "Mars": "♂️",
    "Jüpiter": "♃", "Satürn": "♄", "Uranüs": "♅", "Neptün": "♆", "Plüton": "♇",
}


def format_astro(a: dict) -> str:
    """Zengin doğum haritası sözlüğünü prompt için okunur metne çevirir."""
    lines = [
        f"- ♈ Yükselen Burç: {a.get('ascendant', 'Bilinmiyor')}",
        f"- 🏔️ Tepe Noktası (MC / kariyer ekseni): {a.get('midheaven', 'Bilinmiyor')}",
    ]
    for p in a.get("planets", []):
        sym = _PLANET_SYMBOLS.get(p["name"], "•")
        house = f"{p['house']}. ev" if p.get("house") else "ev bilinmiyor"
        retro = " (retro ♺)" if p.get("retro") else ""
        lines.append(f"- {sym} {p['name']}: {p['sign']} burcu, {house}{retro}")
    return "\n".join(lines)

def create_prompt(user_data: dict) -> str:
    """Kullanıcıdan gelen bilgilerle detaylı astrolojik ve coğrafi analiz promptu oluşturur."""

    # Frontend gizli alanları birth_lat/birth_lng/birth_timezone adıyla gönderir;
    # eski adlarla (latitude/longitude/timezone) da geriye dönük uyum sağlıyoruz.
    latitude = user_data.get("birth_lat") or user_data.get("latitude")
    longitude = user_data.get("birth_lng") or user_data.get("longitude")
    timezone = user_data.get("birth_timezone") or user_data.get("timezone")

    # Gelen verileri ekrana yaz (hata ayıklama için)
    print("📦 Kullanıcı verileri:")
    print("📅 Doğum Tarihi:", user_data.get("birth_date"))
    print("⏰ Doğum Saati:", user_data.get("birth_time"))
    print("🌐 Enlem:", latitude)
    print("🌐 Boylam:", longitude)
    print("🕒 Zaman Dilimi:", timezone)

    # Eksik bilgi varsa "Bilinmiyor" değerleri ata
    if not all([
        user_data.get("birth_date"),
        user_data.get("birth_time"),
        latitude,
        longitude,
        timezone
    ]):
        print("⚠️ Eksik bilgi nedeniyle doğum haritası hesaplanamadı.")
        astro_data = empty_chart()
    else:
        try:
            astro_data = calculate_birth_chart(
                user_data.get("birth_date"),
                user_data.get("birth_time"),
                latitude,
                longitude,
                timezone
            )
            print("✅ Doğum haritası başarıyla hesaplandı.")
        except Exception as e:
            print("❌ Doğum haritası hesaplama hatası:", e)
            astro_data = empty_chart()

    astro_block = format_astro(astro_data)

    prompt = f"""
☀️ Merhaba sevgili dostum! \n
Astroloji, el falı (palmistry) ve astrocartography'nin büyülü dünyasına hoş geldin. \n
Doğum bilgilerini ve hedeflerini paylaştığın için çok teşekkür ederim. \n
Şimdi senin için özel olarak hazırlanmış kişisel analize geçiyoruz. \n
Bu analizde karakter özelliklerinden yaşam enerjine, hangi şehirlerde daha mutlu ve başarılı olabileceğine kadar birçok detayı birlikte keşfedeceğiz. \n
Hazırsan başlayalım... 🚀 \n

🧙‍♀️ ROLÜN: Sen 30 yıllık deneyimli, sezgileri güçlü bir USTA astrolog, astrocartography ve el falı uzmanısın. Yorumların derin, spesifik, sıcak ve kişiyi "bu tam beni anlatıyor" dedirtecek kadar isabetli olacak. Genel geçer klişelerden ("sen özel birisin" gibi boş cümlelerden) KAÇIN; her cümleyi doğum haritasındaki SPESİFİK yerleşimlere (burç + ev + gezegen) dayandır.

🎯 YORUM İLKELERİ (çok önemli):
1. Yorumun TEMELİ doğum tarihi, saati, yeri ve o anki gökyüzü dizilimidir (yukarıdaki harita). Önce haritayı oku, karakteri oradan çıkar.
2. Kullanıcının seçtiği "Yaşadığı Zorluklar"ı, yaşadığı yerin eksikliği gibi DÜZ okuma. Bunları kişinin İÇSEL İHTİYAÇLARI / ÖZLEMLERİ olarak yorumla:
   örn. "ulaşım zorluğu" → hareket, özgürlük ve akış ihtiyacı; "sosyal hayat eksikliği" → topluluk ve ait olma arzusu; "motivasyon düşüklüğü" → anlam ve ilham arayışı.
   Bu ipuçlarını doğum haritasıyla BİRLEŞTİRİP karakter portresi çiz.
3. Ülke/şehir önerirken "şehrinde şu yok, oraya git" DEME. Bunun yerine: "Haritanda X baskın ve içten içe Y'yi arıyorsun, bu yüzden Z kültürü sana ev gibi gelir" mantığıyla, içsel ihtiyaç + astro yerleşim üzerinden gerekçelendir.
4. Dil akıcı, edebi ve tatmin edici olsun; kişiye doğrudan "sen" diye hitap et.

Aşağıdaki bilgilere göre çok kapsamlı, kişiye özel bir analiz yap:

🪐 Astrolojik Analiz İçin Kullanıcı Verileri:
- Cinsiyet: {user_data.get("gender", "Bilinmiyor")}
- 📅 Doğum Tarihi: {user_data.get("birth_date", "Bilinmiyor")}
- ⏰ Doğum Saati: {user_data.get("birth_time", "Bilinmiyor")}
- 📍 Doğum Yeri: {user_data.get("birth_place", "Bilinmiyor")}
- 🌐 Koordinatlar: {latitude or "Bilinmiyor"}, {longitude or "Bilinmiyor"}
- 🕒 Saat Dilimi: {timezone or "Bilinmiyor"}

🌌 Doğum Haritası (bu kişinin gökyüzü dizilimi — yorumun TEMELİ bu olmalı):
{astro_block}

- Şu Anki Yer: {user_data.get("current_location", "Bilinmiyor")}
- İlişki Durumu: {user_data.get("relationship_status", "Bilinmiyor")}
- Hedefleri: \n{format_goals(user_data.get("goals", []))}
- Enerji Değişimi: {user_data.get("energy_change", "Belirtilmemiş")}
- Yaşadığı Zorluklar: {user_data.get("challenges", "Belirtilmemiş")}
- El Fotoğrafı Yüklendi mi: {'Evet' if user_data.get("hand_image") else 'Hayır'}
- Favori Şehirler: {user_data.get("country1", "")}, {user_data.get("country2", "")}, {user_data.get("country3", "")}

🔭 Analiz Aşamaları:

<b>1. Astrokartografi Analizi:</b>
   -🌍 Öncelikle kullanıcının favori şehirleri üzerinden astrocartography çizgilerine göre değerlendirme yap. 
   - Hangi şehirde hangi çizgiler (Sun Line, Venus Line, Saturn Line vs.) var?
   - Bu şehirlerdeki astrolojik etkiler ne olabilir?
   - Hangi tarihlerde hangi gezegenler etki yaratıyor? 
   - Bu etkiler kariyer, aşk, sağlık, para, arkadaşlık gibi alanları nasıl etkiler? Öncelikle kullanıcının favori şehirleri üzerinden astrocartography çizgilerine göre değerlendirme yap. 
   - Hangi şehirde hangi çizgiler (Sun Line, Venus Line, Saturn Line vs.) var?
   - Bu şehirlerdeki astrolojik etkiler ne olabilir?
   - Hangi tarihlerde hangi gezegenler etki yaratıyor? 
   - Bu etkiler kariyer, aşk, sağlık, para, arkadaşlık gibi alanları nasıl etkiler?

<b>2. El Falı Analizi (Palmistry): ✋</b>
   - El fotoğrafı yüklendiyse, palmistry analizi yap:
   - Life line, Heart line, Head line, Fate line hakkında yorum yap.
   - Bu çizgilerdeki belirgin özelliklere göre kullanıcının ruhsal ve fiziksel eğilimlerini açıkla.

<b>3. Doğum Haritası Analizi:</b>
   - Kullanıcının doğum haritasını detaylı yorumla:
   - Lütfen bu verilere göre doğum haritası hesapla ve astrolojik analizini yap. Önce teknik hesaplamaları yap (yükselen, evler, burçlar), sonra kişisel yorumla.
   - Yükselen burcu, Güneş burcu, Ay burcu nedir?
   - Güneş, Ay, Mars, Merkür, Venüs gibi gezegenlerin ev konumlarını yaz (örneğin: Güneş 10. evde).
   - Ev konumlarına göre hayatın hangi alanlarında daha güçlü etkiler olduğunu anlat.
   - Özellikle dikkat edilmesi gereken transit dönemlere (yıl, ay, olay) dair uyarı ver.

<b>4. Ülke ve Şehir Önerileri:</b>
   Bu bölümü İKİ ayrı parça halinde yaz:

   🧳 Senin Seçtiğin Ülkeler: Kullanıcının seçtiği ülkeleri (yukarıdaki "Favori Şehirler")
   TEK TEK ve DOYURUCU biçimde değerlendir (her biri için en az bir dolu paragraf). Her ülke için şunları anlat:
   hangi astrocartography hattı etkili ve bu kişiye ne hissettirir; oraya gitmenin OLUMLU yönleri neler,
   dikkat edilmesi gereken OLUMSUZ yönleri neler; kısa vadede mi yoksa uzun vadede mi uygun; kariyer, aşk ve
   iç huzur açısından ne beklenir. Sonunda NET bir yargı ver: bu kişi oraya taşınmalı mı, hangi şartlarda gitmeli,
   bir atılım yapmalı mı yoksa temkinli mi olmalı? Kişiyi karar verdirecek kadar somut, gerekçeli ve içten yaz.

   🌟 Astroline'ın Önerisi: Cümleye "İşte Astroline'ın sana önerisi..." diye başla. Kullanıcının
   doğum haritasına, içsel ihtiyaçlarına ve hedeflerine göre SEN dünyadaki herhangi bir ülke/şehri öner
   (seçtiklerinden farklı olabilir). 3-5 ülke/şehir seç. Her biri için dolu bir paragraf yaz:
   ülke bayrağı emojisi ve şehir, hangi astro hattı baskın ve ne hissettirir, kültürel/iklimsel uyum,
   oraya gidersen hayatında ne değişir (kariyer, aşk, huzur) ve bu kişiye ne kadar uygun olduğu.
   Sadece turistik değil, karaktere oturan içten bir kültürel aidiyet önerisi yap.
   Örnek üslup: "🇬🇷 Atina: Venüs hattın burada güçlü, Akdeniz'in sıcaklığı Ay burcunla örtüşür ve kendini evinde hissedersin."


<b>5. Özet Analiz:</b>
  - Finalde aşağıdaki başlıklarla özet bir analiz oluştur:
  - 📊 Şehir / Ülke | Astro Enerji | Neden Uygun | Etki Alanı (kariyer, sağlık, aşk)
  - Tüm bulgulara dayalı özet tabloyu <table> etiketiyle oluştur.
  - Tablo sonunda motive edici kapanış yaz.


   - Kullanıcının doğum haritası, hedefleri ve enerjisine göre LLM olarak senin önerdiğin şehirleri ver.
   - Bu kısımda cümleye işte Astroline'ın sana önerisi diye başla.
   - Bu şehirler, kullanıcının doğum haritasına göre en uygun olanlar olmalı.
   - Bu şehirlerin astrocartography çizgilerini ve etkilerini yaz.
   - Hangi etkiler hangi alanlarda avantaj sağlar?
   - Kullanıcının hedefleriyle nasıl örtüşüyor?
   - Her şehir,ülke bilgisinin başına ülke bayrağı emojisini ekle. Metin içinde yıldız (*) kullanma. Tabloları HTML formatında dön.


    ⚠️ Yazım Dili: Samimi, motive edici, ilham verici olmalı. Emojilerle destekle (☀️, 💖, 💼, 🧘‍♀️, 🌍).
    - Sıralama yaptığında bu sırlamaların başında ülke adlarının başında * işaretini kullanma güzel gözükmüyor,
    - * işareti yerine uygun emojilerle destekle ki okunaklı olsun ve okuyucunun dikkatini çeksin, göze hitap etsin.
    - UI açısından kullanıcıya hitap etsin yani analiz rahat okunabilir olsun.

⚠️ DİL VE YAZIM (ÇOK ÖNEMLİ):
- KUSURSUZ Türkçe yaz: dilbilgisi, imla ve noktalama kurallarına tam uy. Cümle düşüklüğü, tekrar, yarım cümle OLMASIN. Her cümle akıcı ve anlamlı olsun.
- UZUN TİRE (—, –) KULLANMA. Yapay zekâ yazısı izlenimi veriyor ve itici duruyor. Ayırma/vurgu için virgül, nokta, iki nokta (:) veya parantez kullan; cümleleri düzgün kur.
- Burç/gezegen adlarını doğru çekimle kullan (örn. "Oğlak Güneşi", "Güneş'in", "Ay burcun" gibi); "Güneşün", "Güneşü" gibi bozuk ekler YAZMA.

⚠️ ÇIKTI BİÇİMİ (arayüzde düzgün görünmesi için ÇOK ÖNEMLİ):
- Ana bölüm başlıklarını <h2>...</h2>, alt başlıkları <h3>...</h3>, vurguları <b>...</b> ile yaz.
- ASLA markdown kullanma: #, ##, ###, ---, *** ve tek/çift yıldız (*, **) KESİNLİKLE YASAK.
- Akıcı paragraflar yaz, bölümler arasında bir boş satır bırak. Metin arayüzde HTML olarak gösterilecek.
⚠️ UYARI: Analiz kısa olmasın. Minimum 1500 kelime olacak şekilde detaylı, tek seferlik ve kişiye özel yaz.
⚠️ ÇOK ÖNEMLİ: 5 bölümün HEPSİNİ (Astrokartografi, El Falı, Doğum Haritası, Ülke Önerileri, Özet Tablo) eksiksiz TAMAMLA. Hiçbir bölümü ve hiçbir cümleyi yarım bırakma; en sonda motive edici bir kapanış cümlesiyle bitir.
⚠️ Yazarken lütfen şu kurallara dikkat et:

- Hiçbir yerde yıldız işareti (* veya **) kullanma.
- Yerine uygun emojilerle görsel vurgular yap:
  - 🌍 Şehir isimlerinin başında bu emoji olsun. Uygunsa ülke bayrağı ekle (örn: 🇶🇦 Doha, 🇦🇪 Dubai, 🇺🇸 San Francisco).
  - ✋ El falı başlığı altında:
    - 💪 Yaşam Çizgisi
    - 💖 Kalp Çizgisi
    - 🧠 Kafa Çizgisi
    - 🔮 Kader Çizgisi
- Tüm bölümleri sırasıyla önce genel olarak ne anlama geldilerini açıkla, sonra kullanıcıya özel el görseline göre sizin bu çizginiz böyle bu nedenle şu anlama geliyor şeklinde analiz et. Örnek veri yazma.
- Örneğin: "Yaşam Çizgisi: Bu çizgi, yaşam enerjisini ve sağlığı temsil eder. Eğer bu çizgi belirgin ve uzun ise, bu kişinin sağlıklı bir yaşam sürdüğünü gösterir. Ancak kısa veya kesikse, sağlık sorunları yaşayabilir. Sizin el görselinize dayanarak yaşam çizginiz şu şekilde ve anlamı şu..." şeklinde yaz.
- Çıktının sonunda “5. Özet Analiz” tablosunu <table> etiketiyle HTML biçiminde ver (önceki direktife uygun şekilde) 
- Her kullanıcı için şehirleri doğum haritası, hedefleri ve seçtiği ülkeler doğrultusunda kendin belirle.

Bu tablo başlıkları şöyle olacak:

<table>
  <thead>
    <tr>
      <th>Şehir / Ülke</th>
      <th>Astro Enerji</th>
      <th>Neden Uygun</th>
      <th>Etki Alanı</th>
    </tr>
  </thead>
  <tbody>
    <!-- Kullanıcının verilerine göre sen doldur -->
  </tbody>
</table>

- Tablonun altına da Özetle kısmı açıp moral ve motivasyon verici kısa bir konuşma yaz.
    """

    # 2️⃣ El FOTOĞRAFI yüklendiyse palmistry bölümü ekle. Not: foto, MediaPipe el
    # tespit etsin etmesin vision modele gönderiliyor; bu yüzden mesajı hand_image'e
    # göre veriyoruz (palm_analysis'e değil) — aksi halde "yüklenmedi" yanlış çıkıyordu.
    if user_data.get("hand_image"):
        prompt += """

    <b>2. El Falı Analizi (Palmistry): ✋</b>

    Bu mesaja kullanıcının EL FOTOĞRAFI eklendi. Fotoğraftaki avuç çizgilerine BAKARAK yorum yap
    (çizgilerin konumu, uzunluğu, derinliği, kesikli/belirgin oluşu). Her çizgi türü için önce
    genel anlamını açıkla, sonra bu kişinin fotoğrafına dayalı, kişiye özel sezgisel bir yorum yap:
    - 💪 Yaşam Çizgisi (yeşil): yaşam enerjisi, dayanıklılık ve sağlık.
    - 💖 Kalp Çizgisi (kırmızı): duygusal yaşam, ilişkiler ve bağlanma biçimi.
    - 🧠 Kafa Çizgisi (turuncu): düşünce tarzı, mantık ve karar verme.
    - 🔮 Kader Çizgisi (mor): kariyer yolu ve hayat yönü.

    Not: Görsel bulanık veya çizgiler net değilse elinden geldiğince fotoğrafa dayalı yorumla;
    "fotoğraf yüklenmedi" DEME (fotoğraf ekli). Her çizgiyi özgün ve pozitif değerlendir, şablon yazma.
    """
    else:
        prompt += """
    ✋ El çizgileri üzerine genel bilgi verildi ancak kişisel analiziniz yapılamadı çünkü el görseliniz yüklenmedi.
    📸 Lütfen el fotoğrafınızı yüklerseniz, Astroline sizin için özel bir palmistry (el falı) analizi oluşturabilir.
    """

    print("🧠 Prompt:", prompt)
    return prompt


#  Kullandığımız model. Ucuz + hızlı + vision (el fotoğrafını okur).
#  Uygulama büyüyünce tek satır: "claude-sonnet-5" yapılır.
CLAUDE_MODEL = "claude-haiku-4-5"


async def analyze_user(user_data: dict, client: AsyncAnthropic) -> Optional[str]:
    prompt = create_prompt(user_data)
    if not prompt or not prompt.strip():
        return None

    print("🧠 Oluşturulan prompt:", prompt[:300])

    # 🖐️ El görseli varsa modele gerçekten "gösteriyoruz" (vision) — böylece
    # el falı yorumu uydurma değil, fotoğrafa dayalı olur.
    content = []
    # Görseli küçültme (cv2) bloklayıcı → thread'e al, olay döngüsünü meşgul etme
    image_block = await asyncio.to_thread(_build_image_block, user_data.get("hand_image") or "")
    if image_block:
        content.append(image_block)
    content.append({"type": "text", "text": prompt})

    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=12000,  # 8192 uzun analizlerde yarım bırakıyordu; tamamlanması için artırıldı
        messages=[{"role": "user", "content": content}],
    )

    result_text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    print(f"✅ Analiz üretildi (model={response.model}, "
          f"girdi={response.usage.input_tokens} / çıktı={response.usage.output_tokens} token)")
    return result_text


def extract_table_from_analysis(analysis_text: str) -> Tuple[str, str]:
    """
    LLM'den gelen analizdeki tablo kısmını hem temizler hem HTML tabloya çevirir.
    Analiz metninden tabloyu ayırır, kalan metni döndürür.
    """
    lines = analysis_text.splitlines()
    table_lines = []
    clean_lines = []
    capturing = False

    for line in lines:
        if re.match(r"\|\s*Şehir\s*/\s*Ülke", line):
            capturing = True
            continue
        if capturing:
            if not line.strip().startswith("|"):
                capturing = False
                continue
            table_lines.append(line.strip())
        elif not capturing:
            clean_lines.append(line)

    # HTML tablo oluştur
    html = ""
    if table_lines:
        html += '<table class="result-table">\n<thead><tr>'
        headers = [cell.strip() for cell in table_lines[0].split("|")[1:-1]]
        for h in headers:
            html += f"<th>{h}</th>"
        html += "</tr></thead>\n<tbody>"

        for row in table_lines[1:]:
            if "---" in row:
                continue
            cells = [cell.strip() for cell in row.split("|")[1:-1]]
            html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>\n"

        html += "</tbody></table>"

    return "\n".join(clean_lines).strip(), html