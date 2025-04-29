# backend/utils.py

# Kullanıcı verilerinden prompt hazırlamak, LLM çağrısı yapmak, el fotoğrafı silmek gibi iş mantığı işlemleri yapmak için kullanılacak fonksiyonlar burada tanımlanır.
# Bu sayede main.py dosyası daha sade ve okunabilir olur. Ayrıca ileride farklı analiz türleri eklemek istediğimizde sadece bu dosyayı güncelleyerek işimizi halledebiliriz.

import re
import os
from typing import Tuple
from google.generativeai import GenerativeModel

def format_goals(goals):
    if not goals:
        return "Belirtilmemiş"
    if isinstance(goals, str):
        return goals
    return "\n".join([f"{i + 1}. {goal}" for i, goal in enumerate(goals)])

def create_prompt(user_data: dict) -> str:
    """Kullanıcıdan gelen bilgilerle detaylı astrolojik ve coğrafi analiz promptu oluşturur."""
    prompt = f"""
🌟 Sevgili dostum, merhaba! \n
Astroloji, el falı (palmistry) ve astrocartography'nin büyülü dünyasına hoş geldin. \n
Doğum bilgilerini ve hedeflerini paylaştığın için çok teşekkür ederim. \n
Şimdi senin için özel olarak hazırlanmış kişisel analize geçiyoruz. \n
Bu analizde karakter özelliklerinden yaşam enerjine, hangi şehirlerde daha mutlu ve başarılı olabileceğine kadar birçok detayı birlikte keşfedeceğiz. \n
Hazırsan başlayalım... 🚀 \n

🧙‍♀️ Lütfen aşağıdaki bilgilere göre çok kapsamlı, uzman bir astrolog, astrocartography ve palmistry uzmanı olarak kişisel analiz yap:

📌 Kullanıcı Bilgileri:
- Cinsiyet: {user_data.get("gender", "Bilinmiyor")}
- Doğum Tarihi: {user_data.get("birth_date", "Bilinmiyor")}
- Doğum Saati: {user_data.get("birth_time", "Bilinmiyor")}
- Doğum Yeri: {user_data.get("birth_place", "Bilinmiyor")}
- Şu Anki Yer: {user_data.get("current_location", "Bilinmiyor")}
- İlişki Durumu: {user_data.get("relationship_status", "Bilinmiyor")}
- Hedefleri: \n{format_goals(user_data.get("goals", []))}
- Enerji Değişimi: {user_data.get("energy_change", "Belirtilmemiş")}
- Yaşadığı Zorluklar: {user_data.get("challenges", "Belirtilmemiş")}
- El Fotoğrafı Yüklendi mi: {'Evet' if user_data.get("hand_image") else 'Hayır'}
- Favori Şehirler: {user_data.get("country1", "")}, {user_data.get("country2", "")}, {user_data.get("country3", "")}

🔭 Analiz Aşamaları:

1. Öncelikle kullanıcının favori şehirleri üzerinden astrocartography çizgilerine göre değerlendirme yap. 
   - Hangi şehirde hangi çizgiler (Sun Line, Venus Line, Saturn Line vs.) var?
   - Bu şehirlerdeki astrolojik etkiler ne olabilir?
   - Hangi tarihlerde hangi gezegenler etki yaratıyor? 
   - Bu etkiler kariyer, aşk, sağlık, para, arkadaşlık gibi alanları nasıl etkiler?

2. El fotoğrafı yüklendiyse, palmistry analizi yap:
   - Life line, Heart line, Head line, Fate line hakkında yorum yap.
   - Bu çizgilerdeki belirgin özelliklere göre kullanıcının ruhsal ve fiziksel eğilimlerini açıkla.

3. Kullanıcının doğum haritasını detaylı yorumla:
   - Yükselen burcu, Güneş burcu, Ay burcu nedir?
   - Güneş, Ay, Mars, Merkür, Venüs gibi gezegenlerin ev konumlarını yaz (örneğin: Güneş 10. evde).
   - Ev konumlarına göre hayatın hangi alanlarında daha güçlü etkiler olduğunu anlat.
   - Özellikle dikkat edilmesi gereken transit dönemlere (yıl, ay, olay) dair uyarı ver.

4. Kullanıcının doğum haritası, hedefleri ve enerjisine göre LLM olarak senin önerdiğin şehirleri ver.
   - Bu kısımda cümleye işte Astroline'ın sana önerisi diye başla.
   - Bu şehirlerin astrocartography çizgilerini ve etkilerini yaz.
   - Hangi etkiler hangi alanlarda avantaj sağlar?
   - Kullanıcının hedefleriyle nasıl örtüşüyor?
   - Her şehir,ülke bilgisinin başına ülke bayrağı emojisini ekle. Metin içinde yıldız (*) kullanma. Tabloları HTML formatında dön.


5. Finalde aşağıdaki başlıklarla özet bir analiz oluştur:
📊 Şehir / Ülke | Astro Enerji | Neden Uygun | Etki Alanı (kariyer, sağlık, aşk)

<b>1. Astrokartografi Analizi:</b>

<b>2. El Falı Analizi (Palmistry): ✋</b>

<b>3. Doğum Haritası Analizi:</b>

<b>4. Astroline'ın Önerisi:</b>

<b>5. Özet Analiz:</b>

Başlıkları <b> etiketiyle kalın (bold) olarak yaz. Markdown kullanma, yıldız (*) işareti kullanma.

6. Yazım dili: samimi, motive edici, ilham verici olsun. Gerektiğinde emojilerle destekle (☀️, 💖, 💼, 🧘‍♀️, 🌍). 
    - Sıralama yaptığında bu sırlamaların başında ülke adlarının başında * işaretini kullanma güzel gözükmüyor,
    - * işareti yerine uygun emojilerle destekle ki okunaklı olsun ve okuyucunun dikkatini çeksin, göze hitap etsin.
    - UI açısından kullanıcıya hitap etsin yani analiz rahat okunabilir olsun.
    

⚠️ UYARI: Analiz kısa olmasın. Minimum 1000 kelime olacak şekilde detaylı, tek seferlik ve kişiye özel yaz.
⚠️ Yazarken lütfen şu kurallara dikkat et:

- **Hiçbir yerde çift yıldız (**) veya yıldız (*) kullanma.**
- Yerine uygun emojilerle görsel vurgular yap:
  - 🌍 Şehir isimlerinin başında bu emoji olsun. Uygunsa ülke bayrağı ekle (örn: 🇶🇦 Doha, 🇦🇪 Dubai, 🇺🇸 San Francisco).
  - ✋ El falı başlığı altında:
    - 💪 Yaşam Çizgisi
    - 💖 Kalp Çizgisi
    - 🧠 Kafa Çizgisi
    - 🔮 Kader Çizgisi
- Tüm bölümleri kullanıcıya özel analiz et. Örnek veri yazma.
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
    return prompt

def analyze_user(user_data: dict, model: GenerativeModel) -> str:
    prompt = create_prompt(user_data)
    response = model.generate_content(prompt)
    result_text = response.text

    hand_image_path = user_data.get("hand_image")
    if hand_image_path and os.path.exists(hand_image_path):
        os.remove(hand_image_path)
        print(f"🧹 El fotoğrafı silindi: {hand_image_path}")

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

