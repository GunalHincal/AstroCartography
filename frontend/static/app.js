// === Astroline App JS ===

// 🛰️ İstemci (tarayıcı) hatalarını backend'e gönderir → Render loglarında görünür.
function reportClientError(payload) {
    try {
        const body = JSON.stringify(Object.assign({
            url: location.href,
            ua: navigator.userAgent,
            t: new Date().toISOString(),
        }, payload));
        // sendBeacon: sayfa kapanırken bile kaybolmaz
        if (navigator.sendBeacon) {
            navigator.sendBeacon("/client-log", body);
        } else {
            fetch("/client-log", { method: "POST", body, keepalive: true });
        }
    } catch (e) { /* sessiz geç */ }
}

// Global JS hataları ve yakalanmamış promise reddleri
window.addEventListener("error", (e) => {
    reportClientError({ type: "js-error", message: e.message, source: e.filename, line: e.lineno, col: e.colno });
});
window.addEventListener("unhandledrejection", (e) => {
    reportClientError({ type: "promise-reject", message: String(e.reason && e.reason.message || e.reason) });
});

// 🎨 LLM çıktısını temiz HTML'e çevirir: markdown (##, ---, **) temizlenir,
// bölüm başlıkları <h2>/<h3> olur; tablolar ve <b> etiketleri korunur.
function renderAnalysis(text) {
    let html = text || "";
    // Güvenlik ağı: kalan uzun tireleri (— –) daha doğal ayraçlarla değiştir
    html = html.replace(/\s+[—–]\s+/g, ", ");
    // Markdown başlıkları
    html = html.replace(/^\s*#{3,}\s*(.+?)\s*#*\s*$/gm, "<h3>$1</h3>");
    html = html.replace(/^\s*#{1,2}\s*(.+?)\s*#*\s*$/gm, "<h2>$1</h2>");
    // Çift yıldız kalın → <b>
    html = html.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    // Tek başına satır olan <b>...</b> (bölüm başlığı) → <h2>
    html = html.replace(/^\s*<b>\s*(.+?)\s*<\/b>\s*:?\s*$/gm, "<h2>$1</h2>");
    // Yatay çizgi (---, ***, ___)
    html = html.replace(/^\s*([-*_])\1{2,}\s*$/gm, "<hr>");
    // Satır başındaki tek yıldız madde işareti → •
    html = html.replace(/^\s*\*\s+/gm, "• ");
    // Blok başlıkların etrafındaki fazla satır boşluklarını kaldır
    html = html.replace(/\n{3,}/g, "\n\n");
    html = html.replace(/\n*(<h[23]>.*?<\/h[23]>)\n*/g, "$1");
    html = html.replace(/\n*(<hr>)\n*/g, "$1");
    return html.trim();
}

// 📄 Analizi PDF olarak indir — özel print stylesheet ile temiz çıktı
function downloadPdf() {
    const prevTitle = document.title;
    document.title = "Astroline-Analiz-" + new Date().toISOString().slice(0, 10);
    window.print();
    setTimeout(() => { document.title = prevTitle; }, 800);
}


// 💾 Kullanıcı verilerini backend'e kaydeder
async function saveAnswer(key, value) {
    const formData = new FormData();
    formData.append("key", key);
    formData.append("value", value);

    const response = await fetch("/save_answer", {
        method: "POST",
        body: formData
    });

    const result = await response.json();
    console.log("📝 Cevap kaydedildi:", key, value, result);
}

// 🌍 Google Places — yeni PlaceAutocompleteElement API'si
// (Eski google.maps.places.Autocomplete 1 Mart 2025'ten sonra yeni müşterilere kapandı.)
window.initAutocomplete = async function initAutocomplete() {
    const { PlaceAutocompleteElement } = await google.maps.importLibrary("places");
    const FIELDS = ["formattedAddress", "displayName", "location"];

    // Bir konteynere otomatik-tamamlamalı yer alanı ekler
    function addPlaceField(containerId, options, onSelect) {
        const host = document.getElementById(containerId);
        if (!host) return;
        const el = new PlaceAutocompleteElement(options);
        el.style.width = "100%";
        host.appendChild(el);
        el.addEventListener("gmp-select", async ({ placePrediction }) => {
            const place = placePrediction.toPlace();
            await place.fetchFields({ fields: FIELDS });
            onSelect(place);
        });
    }

    // Doğum yeri (Türkiye ile sınırlı) → adres + koordinat + saat dilimi
    addPlaceField("birth_place_container", { includedRegionCodes: ["tr"] }, (place) => {
        const address = place.formattedAddress || place.displayName || "";
        document.getElementById("birth_place").value = address;
        if (place.location) {
            const lat = place.location.lat();
            const lng = place.location.lng();
            document.getElementById("birth_lat").value = lat;
            document.getElementById("birth_lng").value = lng;
            getTimeZoneFromCoords(lat, lng).then((tz) => {
                document.getElementById("birth_timezone").value = tz || "";
                console.log("📍 Doğum yeri:", address, lat, lng, "| ⏰", tz);
            });
        }
    });

    // Şu anki yer (Türkiye ile sınırlı)
    addPlaceField("current_location_container", { includedRegionCodes: ["tr"] }, (place) => {
        document.getElementById("current_location").value =
            place.formattedAddress || place.displayName || "";
    });

    // Sevdiğin ülkeler (dünya geneli)
    ["country1", "country2", "country3"].forEach((id) => {
        addPlaceField(id + "_container", {}, (place) => {
            document.getElementById(id).value =
                place.formattedAddress || place.displayName || "";
        });
    });
};

// 🕓 Google TimeZone API'den saat dilimini al (backend proxy üzerinden)
async function getTimeZoneFromCoords(lat, lng) {
    const timestamp = Math.floor(Date.now() / 1000);
    const response = await fetch(`/api/timezone?lat=${lat}&lng=${lng}&timestamp=${timestamp}`);
    const data = await response.json();
    return data.timezone;
}

// 🚀 Google Maps API'yi güvenli şekilde (loading=async) yükle
async function loadGoogleMaps() {
    try {
        const response = await fetch('/api/get-google-key');
        const data = await response.json();
        const apiKey = data.key;
        if (!apiKey) {
            console.error("⚠️ Google API anahtarı boş geldi. .env'i kontrol et ve uvicorn'u yeniden başlat.");
            return;
        }
        const script = document.createElement('script');
        script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&loading=async&libraries=places&callback=initAutocomplete`;
        script.async = true;
        document.head.appendChild(script);
    } catch (err) {
        console.error("Google Maps API yüklenemedi:", err);
    }
}
window.addEventListener('load', loadGoogleMaps);

// 📍 Tarayıcıdan konum al ve input'a yaz
async function fetchCurrentLocation() {
    if (!navigator.geolocation) return alert("Tarayıcınız konum özelliğini desteklemiyor.");

    navigator.geolocation.getCurrentPosition((position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;

        // Maps JS API zaten yüklü; anahtarı sızdırmadan client-side Geocoder kullan
        if (!(window.google && google.maps && google.maps.Geocoder)) {
            console.warn("Google Maps henüz yüklenmedi.");
            return;
        }
        const geocoder = new google.maps.Geocoder();
        geocoder.geocode({ location: { lat, lng } }, (results, status) => {
            if (status === "OK" && results[0]) {
                document.getElementById("current_location").value = results[0].formatted_address;
            } else {
                console.error("Konum çözümlenemedi:", status);
            }
        });
    }, (error) => {
        console.error("Konum hatası:", error);
    });
}

// 🎯 Maksimum 5 hedef seçme
const goalCheckboxes = document.querySelectorAll('input[name="goals"]');
let selectedGoalsOrder = [];

goalCheckboxes.forEach(checkbox => {
    checkbox.addEventListener('change', (e) => {
        const label = e.target.parentElement;

        if (checkbox.checked) {
            if (selectedGoalsOrder.length >= 5) {
                checkbox.checked = false;
                alert("Sadece 5 hedef seçebilirsiniz!");
                return;
            }
            selectedGoalsOrder.push(checkbox.value);
        } else {
            const index = selectedGoalsOrder.indexOf(checkbox.value);
            if (index > -1) selectedGoalsOrder.splice(index, 1);
        }

        document.querySelectorAll('.goal-order').forEach(span => span.remove());
        selectedGoalsOrder.forEach((goal, i) => {
            const goalCheckbox = [...goalCheckboxes].find(c => c.value === goal);
            const orderSpan = document.createElement('span');
            orderSpan.textContent = ` (${i + 1})`;
            orderSpan.classList.add('goal-order');
            goalCheckbox.parentElement.appendChild(orderSpan);
        });
    });
});

// ⏩ Form Adım Geçişleri
let currentStep = 0;
const formSteps = document.querySelectorAll('.form-step');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const submitBtn = document.getElementById('submit-btn');
const form = document.getElementById('astro-form');

// ⛔ Enter'a basınca formu erken GÖNDERMESİN. Bunun yerine sonraki adıma geçer.
// (Google adres kutusunda Enter ile öneri seçimine karışmaz.)
form.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const tag = (e.target.tagName || "").toUpperCase();
    if (tag === "TEXTAREA" || tag === "GMP-PLACE-AUTOCOMPLETE") return;
    e.preventDefault();
    if (currentStep < formSteps.length - 1) nextBtn.click();
});

function updateButtons() {
    prevBtn.disabled = currentStep === 0;
    nextBtn.style.display = currentStep === formSteps.length - 1 ? 'none' : 'inline-block';
    submitBtn.style.display = currentStep === formSteps.length - 1 ? 'inline-block' : 'none';

    // 📊 İlerleme çubuğunu güncelle
    const total = formSteps.length;
    const bar = document.getElementById('progress-bar');
    const indicator = document.getElementById('step-indicator');
    if (bar) bar.style.width = `${((currentStep + 1) / total) * 100}%`;
    if (indicator) indicator.textContent = `Adım ${currentStep + 1} / ${total}`;
}

nextBtn.addEventListener('click', () => {
    if (currentStep < formSteps.length - 1) {
        formSteps[currentStep].classList.remove('active');
        currentStep++;
        formSteps[currentStep].classList.add('active');
        updateButtons();
    }
});

prevBtn.addEventListener('click', () => {
    if (currentStep > 0) {
        formSteps[currentStep].classList.remove('active');
        currentStep--;
        formSteps[currentStep].classList.add('active');
        updateButtons();
    }
});

// 🚀 Form Gönderimi
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // 🔒 Zorunlu alanlar dolmadan analiz BAŞLAMASIN
    const gender = (document.getElementById("gender").value || "").trim();
    const birthDate = (document.getElementById("birth_date").value || "").trim();
    const birthTime = (document.getElementById("birth_time").value || "").trim();
    const birthLat = (document.getElementById("birth_lat").value || "").trim();
    const missing = [];
    if (!gender) missing.push("cinsiyet");
    if (!birthDate) missing.push("doğum tarihi");
    if (!birthTime) missing.push("doğum saati");
    if (!birthLat) missing.push("doğum yeri (öneri listesinden seçmelisin)");
    if (missing.length) {
        alert("Analiz için lütfen şu alanları tamamla:\n• " + missing.join("\n• "));
        return;
    }

    // ✅ Tüm adımları geçici olarak görünür yap (doğrulama için)
    formSteps.forEach(step => step.classList.add("active"));

    const formData = new FormData(form);
    const resultDiv = document.getElementById('result');
    
    resultDiv.innerHTML = `<div style="display: flex; flex-direction: column; align-items: center;">
        <svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 24 24" fill="yellow" class="spinner">
          <path d="M12 2l2 7h7l-6 4.5 2 7-6-4.5-6 4.5 2-7-6-4.5h7z"/>
        </svg>
        <p style="font-size:18px; margin-top:10px;">⏳ Lütfen bekleyin, analiz yapılıyor...</p>
      </div>`;

    try {
        // 🎯 Cevapları backend'e ayrı ayrı kaydet
        for (let [key, value] of formData.entries()) {
            if (key !== 'hand_image' && key !== 'goals') {
                await saveAnswer(key, value);
            }
        }

        // 🎯 Hedefler varsa onları da gönder
        if (selectedGoalsOrder.length > 0) {
            await saveAnswer("goals", JSON.stringify(selectedGoalsOrder));
            formData.set("goals", JSON.stringify(selectedGoalsOrder));
        }

        // 📡 Sunucuya /analyze isteği gönder
        const analyzeRes = await fetch('/analyze', {
            method: 'POST',
            body: formData
        });

        if (!analyzeRes.ok) {
            const errText = await analyzeRes.text();
            throw new Error(`Sunucu hatası: ${errText}`);
        }

        const analyzeData = await analyzeRes.json();

        // 🧠 Analiz metni (temiz HTML), rapor başlığı ve tabloyu göster
        const today = new Date().toLocaleDateString("tr-TR");
        resultDiv.innerHTML = `
        <div class="report-header">
            <div class="report-brand">🪐 Astroline — Kişisel Analiz</div>
            <div class="report-meta">
                <span class="report-date">${today}</span>
                <button type="button" class="pdf-btn no-print" onclick="downloadPdf()">📄 PDF olarak indir</button>
            </div>
        </div>
        <div class="analysis-body">${renderAnalysis(analyzeData.text)}</div>
        ${analyzeData.table || ''}
        `;

        // 🖼️ El çizgisi görseli varsa göster ve açıklama kutusunu ekle
        if (analyzeData.image_url) {
        const imageWrapper = document.createElement("div");
        imageWrapper.style.cssText = "margin-top: 30px; text-align: center;";

        const imageElement = document.createElement("img");
        imageElement.src = analyzeData.image_url;
        imageElement.alt = "El Çizgileri Analizi";
        imageElement.style.cssText = `
            max-width: 100%;
            border-radius: 12px;
            box-shadow: 0 0 12px rgba(0, 0, 0, 0.2);
            margin-bottom: 10px;
        `;

        // 📘 Açıklama kutusu
        const desc = document.createElement("p");
        desc.innerHTML = "🖐️ Aşağıdaki görselde tespit edilen el çizgileriniz renklendirilmiştir. Her renk farklı bir çizgiyi temsil eder.";
        desc.style.cssText = "font-size: 16px; margin-bottom: 10px;";

        // 📥 İndir butonu
        const downloadBtn = document.createElement("a");
        downloadBtn.href = analyzeData.image_url;
        downloadBtn.download = "el_analizli.jpeg";
        downloadBtn.className = "no-print";
        downloadBtn.textContent = "📥 Görseli İndir";
        downloadBtn.style.cssText = `
            display: inline-block;
            margin: 10px;
            padding: 8px 16px;
            background-color: #008CBA;
            color: white;
            border-radius: 6px;
            text-decoration: none;
        `;

        // ❓ Çizgi açıklamaları
        const legendBox = document.createElement("div");
        legendBox.style.cssText = "margin-top: 20px; text-align: left; font-size: 15px;";
        legendBox.innerHTML = `
            <strong>🔎 Çizgilerin Anlamı:</strong><br>
            <span style="color:red;">💖 Kalp Çizgisi</span>: Duygusal yaşam ve ilişkiler<br>
            <span style="color:green;">💪 Yaşam Çizgisi</span>: Hayat enerjisi ve dayanıklılık<br>
            <span style="color:orange;">🧠 Kafa Çizgisi</span>: Zeka, düşünce yapısı<br>
            <span style="color:purple;">🔮 Kader Çizgisi</span>: Hayat yolu, kariyer yönü<br>
        `;

        imageWrapper.appendChild(desc);
        imageWrapper.appendChild(imageElement);
        imageWrapper.appendChild(downloadBtn);
        imageWrapper.appendChild(legendBox);

        resultDiv.appendChild(imageWrapper);
        }

    } catch (error) {
        resultDiv.innerHTML = "<p style='color:red;'>❌ Bir hata oluştu. Lütfen tekrar deneyin.</p>";
        console.error("🛑 Hata:", error.message);
        reportClientError({ type: "analyze-failed", message: String(error && error.message || error) });
    }
});

// ✨ Dinamik UI: imleç ışıması + kart spotlight'ları (portfolyo tarzı)
(function initGlow() {
    const root = document.documentElement;

    // İmleci takip eden global ışıma
    window.addEventListener("pointermove", (e) => {
        root.style.setProperty("--mx", e.clientX + "px");
        root.style.setProperty("--my", e.clientY + "px");
    }, { passive: true });

    // Kartlara spotlight davranışı ekle (hedef seçiciler)
    function attachSpotlights() {
        document.querySelectorAll(".checkbox-grid label, .intro-box").forEach((el) => {
            if (el.dataset.spot) return;
            el.dataset.spot = "1";
            el.classList.add("spotlight");
            el.addEventListener("pointermove", (e) => {
                const r = el.getBoundingClientRect();
                el.style.setProperty("--cx", (e.clientX - r.left) + "px");
                el.style.setProperty("--cy", (e.clientY - r.top) + "px");
            }, { passive: true });
        });
    }
    attachSpotlights();
    document.addEventListener("DOMContentLoaded", attachSpotlights);
})();

// 👋 Giriş ekranı
document.addEventListener("DOMContentLoaded", () => {
    const startBtn = document.getElementById("start-btn");
    const introBox = document.querySelector(".intro-box");

    if (startBtn) {
        startBtn.addEventListener("click", () => {
            introBox.style.display = "none";
            const progressWrap = document.getElementById("progress-wrap");
            if (progressWrap) progressWrap.style.display = "block";
            if (formSteps.length > 0) formSteps[0].classList.add("active");
            updateButtons();
        });
    }
});