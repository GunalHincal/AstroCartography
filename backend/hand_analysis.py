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
    points, thumb_on_left = _palm_landmarks(image)

    if points is not None:
        roi = _palm_roi(points, image.shape)
    else:
        # El bulunamazsa tüm görseli ROI kabul et; sınıflandırma sezgisel kalır
        h, w = image.shape[:2]
        roi = (0, 0, w, h)
        thumb_on_left = True

    x0, y0, x1, y1 = roi
    palm = image[y0:y1, x0:x1]
    if palm.size == 0:
        palm = image
        x0 = y0 = 0

    # Çizgileri (crease) belirginleştir: gri + CLAHE + morfolojik blackhat
    gray = cv2.cvtColor(palm, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    blurred = cv2.GaussianBlur(blackhat, (3, 3), 0)
    edges = cv2.Canny(blurred, 20, 70)

    # Daha az ama daha uzun/temiz çizgi için yüksek eşik + uzun minLineLength
    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180, threshold=55,
        minLineLength=max(40, (x1 - x0) // 4), maxLineGap=8,
    )

    # Her çizgi türü için en uzun birkaç segmenti seçiyoruz — böylece görsel
    # "karalama" gibi değil, temiz birkaç renkli çizgi olarak görünür.
    MAX_PER_KIND = 5
    segments = {"heart": [], "head": [], "life": [], "fate": []}
    if lines is not None:
        for line in lines:
            lx1, ly1, lx2, ly2 = line[0]
            # ROI koordinatlarını tam görsele taşı
            gx1, gy1, gx2, gy2 = lx1 + x0, ly1 + y0, lx2 + x0, ly2 + y0
            mx, my = (gx1 + gx2) / 2, (gy1 + gy2) / 2
            dx, dy = gx2 - gx1, gy2 - gy1
            angle = abs(math.degrees(math.atan2(dy, dx))) % 180

            kind = _classify_line(mx, my, roi, thumb_on_left, angle)
            if kind is None:
                continue
            length = (dx * dx + dy * dy) ** 0.5
            segments[kind].append((length, (gx1, gy1, gx2, gy2)))

    counts = {}
    for kind, segs in segments.items():
        segs.sort(key=lambda s: s[0], reverse=True)
        chosen = segs[:MAX_PER_KIND]
        counts[kind] = len(chosen)
        for _, (a, b, c, d) in chosen:
            cv2.line(output, (a, b), (c, d), LINE_COLORS[kind], 3, cv2.LINE_AA)

    # Kaydet
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    name = f"palm_{uuid4().hex}.jpeg"
    out_path = os.path.join(PROCESSED_DIR, name)
    cv2.imwrite(out_path, output)
    web_path = f"/static/processed/{name}"
    print(f"[palm] Cizgiler tespit edildi ({counts}) -> {out_path}")
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
