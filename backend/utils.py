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

🔭 Analiz Aşamaları (KESİNLİKLE bu SIRAYLA yaz):

<b>1. Doğum Haritası Analizi:</b>
   Yukarıdaki gökyüzü dizilimini EV EV, gezegen gezegen, DETAYLI yorumla. Sıra: önce Yükselen, Güneş, Ay;
   sonra Merkür, Venüs, Mars; sonra Jüpiter, Satürn ve dış gezegenler (Uranüs, Neptün, Plüton); MC'yi (kariyer ekseni) de yorumla.
   Her yerleşim için ŞU FORMATI kullan:
   - Önce o gezegenin/evin GENEL anlamını kısa açıkla.
   - Yerleşimin YANINA neyi simgelediğini parantezle yaz. Örn: "Venüs Yay burcu, 9. ev (aşkta özgürlük, keşif ve yolculuk arzun)",
     "Güneş Oğlak, 10. ev (kariyer, hırs ve toplumsal statün)". Ev anlamları: 1. ev kişilik/beden, 2. ev para/değerler, 3. ev iletişim,
     4. ev yuva/aile, 5. ev aşk/yaratıcılık, 6. ev sağlık/iş rutini, 7. ev ilişkiler/ortaklık, 8. ev dönüşüm/ortak kaynaklar,
     9. ev yolculuk/felsefe/yüksek öğrenim, 10. ev kariyer/statü, 11. ev arkadaşlık/idealler, 12. ev bilinçaltı/geri çekilme.
   - Sonra bu kişiye ÖZEL yorumla: bu yerleşim karakterine, ilişkilerine, kariyerine nasıl yansır?
   - Retro gezegenlere ve dikkat edilecek dönemlere kısa değin.

<b>2. El Falı Analizi (Palmistry):</b> ✋
   "El Fotoğrafı Yüklendi mi" alanı "Evet" ise: bu mesaja EKLİ el fotoğrafındaki çizgilere BAKARAK yorumla.
   Her çizgi için başlığı <h3>💖 Kalp Çizgisi — Duygusal Yaşam ve Bağlanma Biçimin</h3> gibi (çizginin neyi simgelediği başlıkta) yaz;
   önce çizginin GENEL anlamını anlat (neyi temsil eder, uzun/kısa/kesikli/belirgin ne demek), SONRA fotoğrafa dayalı kişisel yorum yap.
   Yaşam (💪), Kalp (💖), Kafa (🧠) ve Kader (🔮) çizgilerini işle.
   Eğer "Hayır" ise bu bölümü kısa geç: el fotoğrafı yüklenmediği için el falı bölümünün atlandığını nazikçe belirt.

<b>3. Astrocartography Analizi (Senin Seçtiğin Ülkeler):</b> 🌍
   Önce astrocartography'nin ne olduğunu 1-2 cümle açıkla (gezegen hatları dünya üzerinde çizilir; bir hatta yakın yaşamak o gezegenin enerjisini yoğunlaştırır).
   Sonra kullanıcının SEÇTİĞİ ülkeleri (yukarıdaki "Favori Şehirler") TEK TEK, dolu birer paragrafta yorumla. Her ülke/şehir için:
   - Yaklaşık ENLEM ve BOYLAM ver. Örn: "🇶🇦 Doha: 25.3°N, 51.5°E".
   - Bu kişinin HANGİ astro çizgisi oradan geçiyor (Güneş, Venüs, Satürn, Mars, Ay, Jüpiter hattı vb.), o çizginin GENEL anlamı ne,
     ve o çizginin oradan geçmesinin bu kişiye NE KATTIĞI.
   - Oraya gitmenin OLUMLU ve OLUMSUZ yönleri; kariyer, aşk ve iç huzur açısından ne kazandırır.
   - Kişinin HEDEFLERİNE uygun mu, orada mutlu olur mu, hedeflerini yakalayabilir mi? Net ve içten değerlendir.
   Aynı bilgiyi tekrar etme; her ülkeyi bütün olarak işle.

<b>4. Astroline'ın Önerisi (Sana Özel Ülkeler):</b> 🌟
   "İşte Astroline'ın sana önerisi..." diye başla. Kişinin doğum haritasının TAMAMINI dikkate alarak DÜNYADAKİ ülkeleri değerlendir ve
   ona en uygun 3-5 ülke/şehri SEÇ. Hep aynı bilindik yerleri (Yunanistan, Portekiz, Japonya) verme; YARATICI ol, haritasına gerçekten
   oturan, beklenmedik ama isabetli yerler öner. Her biri için: bayrak + şehir, hangi astro hat baskın ve ne hissettirir, kültürel/iklimsel
   uyum, oraya gidersen hayatında ne değişir ve neden tam ona göre. Örn: "🇬🇷 Atina: Venüs hattın burada güçlü, Akdeniz'in sıcaklığı
   Ay burcunla örtüşür ve kendini evinde hissedersin."

<b>5. Özet Tablo:</b> 📊
   Tüm bulgulara dayalı özet tabloyu <table> etiketiyle oluştur (başlıklar: Şehir / Ülke, Astro Enerji, Neden Uygun, Etki Alanı).

<b>6. Genel Tavsiyeler ve Kapanış:</b> 🌠
   Kişiye genel yaşam ve yön tavsiyeleri ver, her şeyi toparla. ESPRİLİ, sıcak ve samimi bir dille kişiyi memnun et.
   En sonda, analizi okudukları ve sabırları için içten TEŞEKKÜR ederek kapat.

    ⚠️ Yazım Dili: Samimi, motive edici, ilham verici ve yer yer esprili olsun. Emojilerle destekle (☀️, 💖, 💼, 🧘‍♀️, 🌍).

⚠️ DİL VE YAZIM (ÇOK ÖNEMLİ):
- KUSURSUZ Türkçe yaz: dilbilgisi, imla ve noktalama kurallarına tam uy. Cümle düşüklüğü, tekrar, yarım cümle OLMASIN. Her cümle akıcı ve anlamlı olsun.
- UZUN TİRE (—, –) KULLANMA. Yapay zekâ yazısı izlenimi veriyor ve itici duruyor. Ayırma/vurgu için virgül, nokta, iki nokta (:) veya parantez kullan; cümleleri düzgün kur.
- Burç/gezegen adlarını doğru çekimle kullan (örn. "Oğlak Güneşi", "Güneş'in", "Ay burcun" gibi); "Güneşün", "Güneşü" gibi bozuk ekler YAZMA.

⚠️ ÇIKTI BİÇİMİ (arayüzde düzgün görünmesi için ÇOK ÖNEMLİ):
- Ana bölüm başlıklarını <h2>...</h2>, alt başlıkları <h3>...</h3>, vurguları <b>...</b> ile yaz.
- ÖNEMLİ/çarpıcı cümleleri ve kilit içgörüleri <b>...</b> ile VURGULA (arayüzde altın/sarı renkte parlar).
  Her paragrafta 1-2 kilit ifadeyi vurgula ki okuyucunun ilgisi canlı kalsın; ama her şeyi vurgulama, abartma.
- ASLA markdown kullanma: #, ##, ###, ---, *** ve tek/çift yıldız (*, **) KESİNLİKLE YASAK.
- Akıcı paragraflar yaz, bölümler arasında bir boş satır bırak. Metin arayüzde HTML olarak gösterilecek.
⚠️ UYARI: Analiz kısa olmasın. Minimum 1500 kelime olacak şekilde detaylı, tek seferlik ve kişiye özel yaz.
⚠️ ÇOK ÖNEMLİ: 6 bölümün HEPSİNİ (Doğum Haritası, El Falı, Astrocartography, Astroline'ın Önerisi, Özet Tablo, Genel Tavsiyeler) UZUN ve DETAYLI yaz. Doğum haritasını ev ev (Güneş'in evi, Ay'ın evi... tek tek) yorumla; her bölümü doyurucu ve akıcı işle. Hiçbir bölümü ve cümleyi yarım bırakma; en sonda esprili ve teşekkür eden bir kapanışla bitir.
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

    # El falı bölümü (2. bölüm) artık ana prompt'un içinde ve "El Fotoğrafı Yüklendi mi"
    # bilgisine göre model tarafından koşullu işleniyor; ayrı ek blok gerekmiyor.
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
        max_tokens=16000,  # analizin (kapanış dahil) yarım kalmaması için tavan; model doğal biter
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