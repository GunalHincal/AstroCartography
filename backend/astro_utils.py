
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib.const import SUN, MOON, MARS, MERCURY, VENUS, ASC


def _normalize_date(date_str: str) -> str:
    """HTML <input type=date> 'YYYY-MM-DD' verir; flatlib 'YYYY/MM/DD' bekler."""
    return (date_str or "").strip().replace("-", "/")


def calculate_birth_chart(date_str, time_str, latitude, longitude, timezone):
    """Doğum haritasını hesaplayıp önemli göksel bilgileri döner."""
    date_str = _normalize_date(date_str)
    time_str = (time_str or "12:00").strip() or "12:00"
    dt = Datetime(date_str, time_str, timezone)
    # flatlib GeoPos ondalık dereceleri float olarak kabul eder
    pos = GeoPos(float(latitude), float(longitude))
    chart = Chart(dt, pos)

    astro_data = {
        "ascendant": chart.get(ASC).sign,
        "sun": chart.get(SUN).sign,
        "moon": chart.get(MOON).sign,
        "mars": chart.get(MARS).sign,
        "mercury": chart.get(MERCURY).sign,
        "venus": chart.get(VENUS).sign,
    }
    return astro_data


