
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib import const

# İngilizce burç adlarını Türkçe'ye çevir (prompt Türkçe olsun diye)
_SIGN_TR = {
    "Aries": "Koç", "Taurus": "Boğa", "Gemini": "İkizler", "Cancer": "Yengeç",
    "Leo": "Aslan", "Virgo": "Başak", "Libra": "Terazi", "Scorpio": "Akrep",
    "Sagittarius": "Yay", "Capricorn": "Oğlak", "Aquarius": "Kova", "Pisces": "Balık",
}

# Yorumlanacak gökcisimleri (Türkçe adlarıyla)
_PLANETS = [
    (const.SUN, "Güneş"), (const.MOON, "Ay"), (const.MERCURY, "Merkür"),
    (const.VENUS, "Venüs"), (const.MARS, "Mars"), (const.JUPITER, "Jüpiter"),
    (const.SATURN, "Satürn"), (const.URANUS, "Uranüs"),
    (const.NEPTUNE, "Neptün"), (const.PLUTO, "Plüton"),
]


def _tr_sign(sign: str) -> str:
    return _SIGN_TR.get(sign, sign)


def _normalize_date(date_str: str) -> str:
    """HTML <input type=date> 'YYYY-MM-DD' verir; flatlib 'YYYY/MM/DD' bekler."""
    return (date_str or "").strip().replace("-", "/")


def empty_chart() -> dict:
    """Eksik bilgi durumunda kullanılan boş harita."""
    return {"ascendant": "Bilinmiyor", "midheaven": "Bilinmiyor", "planets": []}


def calculate_birth_chart(date_str, time_str, latitude, longitude, timezone) -> dict:
    """Doğum haritasını hesaplar: yükselen, MC ve tüm gezegenlerin burç + ev
    (+ retro) bilgisiyle zengin bir sözlük döner."""
    date_str = _normalize_date(date_str)
    time_str = (time_str or "12:00").strip() or "12:00"
    dt = Datetime(date_str, time_str, timezone)
    pos = GeoPos(float(latitude), float(longitude))
    chart = Chart(dt, pos, IDs=const.LIST_OBJECTS)

    planets = []
    for pid, tr_name in _PLANETS:
        try:
            obj = chart.get(pid)
        except Exception:
            continue
        # Gezegenin bulunduğu ev
        house_num = None
        try:
            house = chart.houses.getObjectHouse(obj)
            if house is not None:
                house_num = int(str(house.id).replace("House", ""))
        except Exception:
            house_num = None
        # Retrograde mı?
        try:
            retro = bool(obj.isRetrograde())
        except Exception:
            retro = False
        planets.append({
            "name": tr_name,
            "sign": _tr_sign(obj.sign),
            "house": house_num,
            "retro": retro,
        })

    return {
        "ascendant": _tr_sign(chart.get(const.ASC).sign),
        "midheaven": _tr_sign(chart.get(const.MC).sign),
        "planets": planets,
    }
