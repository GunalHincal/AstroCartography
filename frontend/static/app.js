// === Astroline App JS ===

let currentStep = 0;
const formSteps = document.querySelectorAll('.form-step');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const submitBtn = document.getElementById('submit-btn');
const form = document.getElementById('astro-form');

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

// Butonları güncelle
function updateButtons() {
    prevBtn.disabled = currentStep === 0;
    nextBtn.style.display = currentStep === formSteps.length - 1 ? 'none' : 'inline-block';
    submitBtn.style.display = currentStep === formSteps.length - 1 ? 'inline-block' : 'none';
}

// Maksimum 5 hedef seçme ve seçme sırasına göre numara verme
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

            const orderSpan = document.createElement('span');
            orderSpan.textContent = ` (${selectedGoalsOrder.length})`;
            orderSpan.classList.add('goal-order');
            label.appendChild(orderSpan);
        } else {
            const index = selectedGoalsOrder.indexOf(checkbox.value);
            if (index > -1) selectedGoalsOrder.splice(index, 1);
            // Tüm numaraları sıfırla
            document.querySelectorAll('.goal-order').forEach(span => span.remove());
            // Yeniden numaralandır
            selectedGoalsOrder.forEach((goal, i) => {
                const goalCheckbox = [...goalCheckboxes].find(c => c.value === goal);
                const goalLabel = goalCheckbox.parentElement;
                const orderSpan = document.createElement('span');
                orderSpan.textContent = ` (${i + 1})`;
                orderSpan.classList.add('goal-order');
                goalLabel.appendChild(orderSpan);
            });
        }
    });
});

// 🌍 Konumdan Şehir/İlçe Getir (Nominatim OpenStreetMap API)
async function fetchCurrentLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            try {
                const response = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`, {
                    headers: { 'User-Agent': 'astroline-app/1.0 (example@example.com)' }
                });
                const data = await response.json();
                const city = data.address.city || data.address.town || data.address.village || '';
                const district = data.address.suburb || data.address.county || '';
                document.getElementById('current_location').value = `${city}, ${district}`;
            } catch (error) {
                alert("Konum verisi alınamadı. Lütfen tekrar deneyin.");
                console.error(error);
                document.getElementById('current_location').value = '';
            }
        }, (error) => {
            alert("Konum alınamadı. Lütfen tarayıcıdan izin verin!");
            console.error(error);
            document.getElementById('current_location').value = '';
        });
    } else {
        alert("Tarayıcınız konum erişimini desteklemiyor.");
    }
}

// 🎯 Google Places Autocomplete
function initAutocomplete() {
    // Şehirler için autocomplete
    const cityOptions = {
        types: ['(cities)']
    };

    const birthInput = document.getElementById("birth_place");
    const currentInput = document.getElementById("current_location");

    if (birthInput) new google.maps.places.Autocomplete(birthInput, cityOptions);
    if (currentInput) new google.maps.places.Autocomplete(currentInput, cityOptions);

    // Ülkeler için autocomplete (regions seçmek yerine geocode daha iyi çalışır)
    const countryInputs = document.querySelectorAll('.country-input');
    const countryOptions = {
        types: ['geocode'],  // 🌍 Bu, şehir ve ülke aramasına izin verir
        fields: ['formatted_address'] // Gerekli bilgi sadece adres
    };

    countryInputs.forEach(input => {
        const autocomplete = new google.maps.places.Autocomplete(input, countryOptions);

        autocomplete.addListener('place_changed', () => {
            const place = autocomplete.getPlace();
            if (place.formatted_address) {
                input.value = place.formatted_address;
            }
        });
    });
}

// 🚀 Google Maps API yükle
async function loadGoogleMaps() {
    const response = await fetch('/api/get-google-key');
    const data = await response.json();
    const apiKey = data.key;

    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places&callback=initAutocomplete`;
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
}

window.onload = loadGoogleMaps;

// Form gönderildiğinde
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(form);
    const resultDiv = document.getElementById('result');

    resultDiv.innerHTML = `<div style="display: flex; flex-direction: column; align-items: center;">
        <svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 24 24" fill="yellow" class="spinner">
          <path d="M12 2l2 7h7l-6 4.5 2 7-6-4.5-6 4.5 2-7-6-4.5h7z"/>
        </svg>
        <p style="font-size:18px; margin-top:10px;">⏳ Lütfen bekleyin, analiz yapılıyor...</p>
      </div>`;

    try {
        for (let [key, value] of formData.entries()) {
            if (key !== 'hand_image' && key !== 'goals') {
                await fetch('/save_answer', {
                    method: 'POST',
                    body: new URLSearchParams({ key, value })
                });
            }
        }

        if (selectedGoalsOrder.length > 0) {
            await fetch('/save_answer', {
                method: 'POST',
                body: new URLSearchParams({ key: 'goals', value: JSON.stringify(selectedGoalsOrder) })
            });
        }

        const handImage = formData.get('hand_image');
        if (handImage) {
            const uploadData = new FormData();
            uploadData.append('file', handImage);

            await fetch('/upload_hand_image', {
                method: 'POST',
                body: uploadData
            });
        }

        const analyzeRes = await fetch('/analyze', { method: 'POST' });
        const analyzeData = await analyzeRes.json();
        resultDiv.innerHTML = `<p style="white-space: pre-wrap;">${analyzeData.analysis}</p>`;

    } catch (error) {
        resultDiv.innerHTML = "<p style='color:red;'>❌ Bir hata oluştu. Lütfen tekrar deneyin.</p>";
        console.error(error);
    }
});
