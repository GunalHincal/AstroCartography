# backend/hand_analysis.py

import os
import math
from uuid import uuid4

import cv2
import numpy as np

# mediapipe 0.10.x'te `mp.solutions` her zaman otomatik yüklenmez; açıkça import et.
from mediapipe.python.solutions import hands as mp_hands

# 📁 Proje kök dizinine göre klasörleri tanımla
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "frontend", "static", "uploads")
PROCESSED_DIR = os.path.join(BASE_DIR, "frontend", "static", "processed")

# 🎨 Çizgi türlerine göre SABİT renkler (BGR) — frontend açıklama kutusuyla birebir uyumlu
LINE_COLORS = {
    "heart": (60, 60, 235),    # 💖 Kırmızı  — Kalp çizgisi
    "head": (0, 165, 255),     # 🧠 Turuncu — Kafa çizgisi
    "life": (60, 200, 90),     # 💪 Yeşil    — Yaşam çizgisi
    "fate": (200, 80, 160),    # 🔮 Mor      — Kader çizgisi
}


def _bezier(p0, p1, p2, n=28):
    """İki uç ve bir kontrol noktasından kuadratik bezier eğrisi noktaları üretir."""
    p0, p1, p2 = np.array(p0, float), np.array(p1, float), np.array(p2, float)
    t = np.linspace(0, 1, n).reshape(-1, 1)
    pts = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2
    return pts.astype(np.int32)


def _palm_landmarks(image):
    """MediaPipe ile avuç landmark'larını (px) ve el yönünü döner.

    Dönen: (points, thumb_on_left) veya bulunamazsa (None, None).
    points: 21x2 numpy dizisi (x, y) piksel cinsinden.
    """
    h, w = image.shape[:2]
    with mp_hands.Hands(
        static_image_mode=True, max_num_hands=1, min_detection_confidence=0.5
    ) as hands:
        results = hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    if not results.multi_hand_landmarks:
        return None, None

    lm = results.multi_hand_landmarks[0].landmark
    points = np.array([[p.x * w, p.y * h] for p in lm], dtype=np.float32)

    # Başparmak, avuç içi görselinde solda mı sağda mı? (yaşam çizgisi başparmağı sarar)
    thumb_on_left = points[4][0] < points[20][0]
    return points, thumb_on_left


def _palm_roi(points, shape):
    """Landmark'lardan avuç içi dikdörtgenini (x0, y0, x1, y1) hesaplar."""
    h, w = shape[:2]
    # Avucu tanımlayan noktalar: bilek + parmak dip eklemleri (MCP)
    idx = [0, 1, 5, 9, 13, 17]
    pts = points[idx]
    x0, y0 = pts[:, 0].min(), pts[:, 1].min()
    x1, y1 = pts[:, 0].max(), pts[:, 1].max()
    # Biraz genişlet
    pad_x = (x1 - x0) * 0.12
    pad_y = (y1 - y0) * 0.12
    x0 = int(max(0, x0 - pad_x))
    y0 = int(max(0, y0 - pad_y))
    x1 = int(min(w, x1 + pad_x))
    y1 = int(min(h, y1 + pad_y))
    return x0, y0, x1, y1


def _classify_line(mx, my, roi, thumb_on_left, angle_deg):
    """Bir çizgi parçasını konum + eğime göre avuç çizgisi türüne atar."""
    x0, y0, x1, y1 = roi
    rw = max(1, x1 - x0)
    rh = max(1, y1 - y0)
    u = (mx - x0) / rw          # 0 (sol) .. 1 (sağ)
    v = (my - y0) / rh          # 0 (parmaklar/üst) .. 1 (bilek/alt)

    horizontal = angle_deg < 35 or angle_deg > 145
    vertical = 55 < angle_deg < 125

    # Yaşam çizgisi: başparmak tarafında, alt-dış bölgede kavis çizer
    thumb_side = u < 0.42 if thumb_on_left else u > 0.58
    if thumb_side and v > 0.30:
        return "life"

    # Kader çizgisi: dikey, avucun ortasında, alt yarıda
    if vertical and 0.30 < u < 0.72 and v > 0.35:
        return "fate"

    # Kalp çizgisi: üst bölge, yatay
    if horizontal and v < 0.42:
        return "heart"

    # Kafa çizgisi: orta bölge, yatay
    if horizontal and 0.38 <= v < 0.72:
        return "head"

    return None


def detect_palm_lines(image_path: str):
    """El görselindeki çizgileri tespit eder, türlerine göre SABİT renklerle
    çizer ve işlenmiş görseli kaydeder.

    Döner: (mutlak_dosya_yolu, web_yolu)  örn: (".../processed/ab12.jpeg", "/static/processed/ab12.jpeg")
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Görsel okunamadı: {image_path}")

    output = image.copy()
    points, _ = _palm_landmarks(image)

    drawn = {}
    if points is not None:
        # Avuç landmark'larına göre 4 klasik el çizgisini anatomik konumlarına
        # oturan DÜZGÜN KAVİSLER olarak çizeriz (rastgele sopalar değil).
        P = points.astype(np.float64)
        wrist, thumb_cmc, thumb_mcp = P[0], P[1], P[2]
        idx, mid, pinky = P[5], P[9], P[17]
        center = P[[0, 5, 9, 13, 17]].mean(axis=0)

        def L(a, b, t):
            return a + (b - a) * t

        up = mid - wrist  # avucun "yukarı" (parmaklara doğru) yönü

        # 💪 Yaşam çizgisi (yeşil): başparmağı saran geniş kavis
        life_a = L(idx, thumb_mcp, 0.30)
        life_b = L(wrist, thumb_cmc, 0.30)
        life_c = L(life_a, life_b, 0.5) + (thumb_mcp - center) * 0.55

        # 🧠 Kafa çizgisi (turuncu): kalbin altında, avucu ortadan yatay geçer
        head_a = L(idx, thumb_mcp, 0.32) - up * 0.06
        head_b = L(pinky, wrist, 0.40)
        head_c = L(head_a, head_b, 0.5) - up * 0.05

        # 💖 Kalp çizgisi (kırmızı): parmak diplerinin hemen altında, yüksekte
        heart_a = pinky + up * 0.10
        heart_b = L(idx, mid, 0.55) + up * 0.05
        heart_c = L(heart_a, heart_b, 0.5) + up * 0.16

        # 🔮 Kader çizgisi (mor): bilekten orta parmağa dikey
        fate_a = L(wrist, center, 0.05)
        fate_b = L(mid, center, 0.10)
        fate_c = L(fate_a, fate_b, 0.5) + (thumb_mcp - center) * 0.05

        curves = {
            "life": (life_a, life_c, life_b),
            "head": (head_a, head_c, head_b),
            "heart": (heart_a, heart_c, heart_b),
            "fate": (fate_a, fate_c, fate_b),
        }

        for kind, (p0, p1, p2) in curves.items():
            pts = _bezier(p0, p1, p2)
            # Cilt üzerinde okunur olsun diye önce koyu dış hat, sonra renk
            cv2.polylines(output, [pts], False, (0, 0, 0), 6, cv2.LINE_AA)
            cv2.polylines(output, [pts], False, LINE_COLORS[kind], 3, cv2.LINE_AA)
            drawn[kind] = True

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    name = f"palm_{uuid4().hex}.jpeg"
    out_path = os.path.join(PROCESSED_DIR, name)
    cv2.imwrite(out_path, output)
    web_path = f"/static/processed/{name}"
    print(f"[palm] Cizgiler cizildi ({list(drawn) or 'el bulunamadi'}) -> {out_path}")
    return out_path, web_path


def analyze_hand_image(image_path: str) -> dict:
    """El görselini doğrular (MediaPipe ile el var mı) ve LLM'e verilecek
    yönerge metnini döner. Görsel üretimi detect_palm_lines() ile yapılır.
    """
    if not os.path.exists(image_path):
        return {"error": "❌ El fotoğrafı bulunamadı."}

    image = cv2.imread(image_path)
    if image is None:
        return {"error": "❌ El fotoğrafı okunamadı."}

    points, _ = _palm_landmarks(image)
    if points is None:
        return {"error": "❌ El üzerinde yeterli landmark tespit edilemedi."}

    return {
        "instruction": (
            "Aşağıdaki görselde el üzerindeki çizgileri analiz et: "
            "Yaşam çizgisi (life line), kalp çizgisi (heart line), kafa çizgisi (head line) ve kader çizgisi (fate line). "
            "Çizgilerin yerlerine, uzunluklarına, derinliklerine ve eğriliklerine göre kişiye özel bir analiz yap. "
            "Bu analizi kişinin sağlığı, aşk hayatı, düşünce yapısı ve kariyer yönelimi açısından değerlendir. "
            "Varsayımlarda bulunabilirsin ama her yorum özgün olmalı ve görsele dayalı olmalı."
        )
    }
