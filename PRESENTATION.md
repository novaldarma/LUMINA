# 🧠 LUMINA — Presentasi Hackathon AMD ACT-II

## Slide 1: Cover

**LUMINA — AI-Powered Alzheimer Patient Monitoring System**

- AMD ACT-II Hackathon Submission
- Computer Vision + AI untuk keselamatan pasien Alzheimer secara real-time
- Tim: Noval Darma (Backend, Computer Vision, AI)

---

## Slide 2: Masalah (Problem Statement)

### Alzheimer di Indonesia

- **1.2+ juta** orang hidup dengan demensia di Indonesia (Alzheimer's Disease International)
- **60-70%** kasus demensia adalah Alzheimer
- Pasien sering **wandering** (berjalan tanpa tujuan) — risiko hilang & cedera tinggi
- Keluarga **tidak bisa mengawasi 24/7** — butuh solusi otomatis

### Pain Points Keluarga:

- ❌ Tidak tahu posisi pasien saat tidak di rumah
- ❌ CCTV biasa tidak bisa bedakan pasien dengan orang lain
- ❌ Pasien lupa wajah keluarga — butuh pengingat visual
- ❌ Tidak ada sistem terintegrasi untuk monitoring + memories

---

## Slide 3: Solusi — LUMINA

### Satu platform, tiga dashboard:

1. **Family Dashboard** — Monitoring center untuk keluarga
2. **Patient Dashboard** — Tampilan mobile-friendly untuk pasien
3. **AI Engine** — Computer vision + face recognition di backend

### Value Proposition:

> "Keluarga bisa memonitor pasien Alzheimer dari mana saja, kapan saja — dengan AI yang mengenali pasien secara visual, melacak lokasi GPS, dan membantu pasien mengingat orang tercinta."

---

## Slide 4: Fitur Utama (6 Pilar)

| #   | Fitur                 | Teknologi                                                |
| --- | --------------------- | -------------------------------------------------------- |
| 1   | **Patient Detection** | Color fingerprint + Face recognition via CCTV            |
| 2   | **GPS Safe Zone**     | Geofencing Haversine — alert jika pasien keluar radius   |
| 3   | **SOS Button**        | One-tap emergency dengan GPS location                    |
| 4   | **Memory Gallery**    | Upload foto + nama/hubungan — tampil di dashboard pasien |
| 5   | **Emotion Agent**     | Auto-deteksi kondisi emosional dari pola aktivitas       |
| 6   | **Activity Timeline** | Log kronologis semua deteksi, alert, event               |

---

## Slide 5: Arsitektur Teknis

```
┌──────────────────────────────────────────────────────┐
│                    LUMINA System                      │
├───────────────┬──────────────┬───────────────────────┤
│  Family       │  Patient     │  Backend (FastAPI)     │
│  Dashboard    │  Dashboard   │  ├─ CCTV Engine        │
│  (Web UI)     │  (Mobile)    │  ├─ Face Recognition   │
│               │              │  ├─ GPS Geofencing     │
│               │              │  ├─ Emotion Agent      │
│               │              │  └─ SQLite Database    │
└───────────────┴──────────────┴───────────────────────┘
```

### Tech Stack:

- **Backend:** FastAPI (Python 3.11) + Uvicorn
- **Computer Vision:** OpenCV 4.9 + face-recognition (dlib) + NumPy
- **Database:** SQLite (lightweight, no setup)
- **Frontend:** Vanilla HTML/CSS/JS (zero dependencies)
- **Deployment:** Docker + Docker Compose

---

## Slide 6: Cara Kerja — Patient Detection

### Dual-Layer Detection:

1. **Color Fingerprint** (Cepat — <50ms)
   - Ekstrak histogram HSV dominan dari baju pasien
   - Cocokkan dengan referensi yang di-upload keluarga
   - Bekerja meskipun wajah tidak terlihat (belakang, samping)

2. **Face Recognition** (Akurat — <200ms)
   - 128-dimensi face encoding dengan dlib
   - Hanya trigger jika color fingerprint match dulu (hemat CPU)
   - Multi-face: bisa deteksi pasien di antara banyak orang

### Flow:

```
CCTV Frame → Color Fingerprint Match? → Face Recognition? → LOG + ALERT
                ↓ No                          ↓ No
             Skip frame                   Log "unknown person"
```

---

## Slide 7: Cara Kerja — GPS Safe Zone

### Geofencing dengan Haversine Formula:

- Keluarga set titik pusat (home) + radius (meter)
- Patient device kirim GPS secara periodik
- Backend hitung jarak dengan rumus Haversine (akurat untuk bumi bulat)
- Jika jarak > radius → **ALERT** ke family dashboard

### Rumus Haversine:

```
a = sin²(Δlat/2) + cos(lat1)·cos(lat2)·sin²(Δlon/2)
c = 2·atan2(√a, √(1−a))
d = R·c  (R = 6371000 m)
```

---

## Slide 8: Cara Kerja — Memory Gallery

### Untuk membantu pasien mengingat:

1. Keluarga upload foto + isi form:
   - Nama orang di foto
   - Hubungan dengan pasien (anak, cucu, suami/istri, dll)
   - Deskripsi memori (opsional)
2. Foto tampil di **Patient Dashboard** dalam grid yang rapi
3. Pasien bisa lihat kapan saja — membantu stimulasi memori

### Teknis:

- Upload via `POST /api/memories` (multipart form)
- Disimpan di `uploads/memories/`
- Metadata di SQLite table `memories`
- Ditampilkan real-time tanpa reload

---

## Slide 9: Demo Flow (Live)

### Skenario Demo:

1. **Setup Camera** → Input URL CCTV (RTSP/HTTP MJPEG) di Family Dashboard
2. **Upload Reference** → Upload foto pasien untuk color fingerprint + face encoding
3. **Start Monitoring** → Sistem mulai deteksi real-time
4. **Simulasi Deteksi** → Pasien terdeteksi → log muncul + bounding box di stream
5. **Upload Memory** → Upload foto keluarga + nama → tampil di Patient Dashboard
6. **GPS Alert** → Simulasi pasien keluar safe zone → alert muncul
7. **SOS** → Tekan SOS button → emergency alert dengan lokasi

---

## Slide 10: API Endpoints

| Method   | Endpoint                | Description          |
| -------- | ----------------------- | -------------------- |
| GET      | `/api/health`           | Health check         |
| GET      | `/api/status`           | Monitoring status    |
| POST     | `/api/start-monitoring` | Start CCTV           |
| POST     | `/api/stop-monitoring`  | Stop CCTV            |
| GET      | `/api/camera-stream`    | Live MJPEG stream    |
| GET/PUT  | `/api/camera-config`    | Get/set camera URL   |
| GET      | `/api/logs`             | Activity logs        |
| POST     | `/api/upload-reference` | Upload patient photo |
| PUT      | `/api/safe-zone`        | GPS safe zone config |
| POST     | `/api/location`         | Update GPS           |
| POST     | `/api/sos`              | SOS emergency        |
| POST/GET | `/api/memories`         | Memory gallery CRUD  |
| GET/PUT  | `/api/patient-config`   | Patient profile      |

---

## Slide 11: Keunggulan Kompetitif

| Aspek          | LUMINA                    | Solusi Lain                                 |
| -------------- | ------------------------- | ------------------------------------------- |
| **Deteksi**    | Dual-layer (color + face) | Face-only (gagal jika wajah tidak terlihat) |
| **Deployment** | Docker, 1 command         | Setup rumit                                 |
| **Database**   | SQLite (zero-config)      | PostgreSQL (perlu setup)                    |
| **Frontend**   | Vanilla JS (ringan)       | React/Vue (berat)                           |
| **Privacy**    | 100% local, no cloud      | Cloud-dependent                             |
| **Cost**       | Free, open-source         | Subscription-based                          |
| **Memories**   | Integrated gallery        | Tidak ada                                   |

---

## Slide 12: Roadmap

### v1.0 (Hackathon) ✅

- [x] Patient detection (color + face)
- [x] GPS safe zone
- [x] SOS button
- [x] Memory gallery
- [x] Activity timeline
- [x] Docker deployment

### v1.1 (Next)

- [ ] Notifikasi WhatsApp/Telegram
- [ ] Multi-camera support
- [ ] Fall detection (pose estimation)
- [ ] Weekly report PDF

### v2.0 (Future)

- [ ] Mobile app (Flutter)
- [ ] Cloud dashboard untuk multiple patients
- [ ] AI-powered anomaly detection
- [ ] Integrasi dengan smart home (IoT)

---

## Slide 13: Penutup

### LUMINA = Lighthouse untuk keluarga Alzheimer

> "Seperti mercusuar yang memandu kapal di kegelapan, LUMINA memandu keluarga menjaga orang tercinta."

### Kenapa LUMINA?

- ✅ **Akurat** — Dual-layer detection (color + face)
- ✅ **Mudah** — Docker, 1 command deploy
- ✅ **Aman** — 100% local, privacy-first
- ✅ **Terjangkau** — Open source, gratis
- ✅ **Lengkap** — Monitoring + memories + GPS + SOS

### Try it now:

```bash
git clone https://github.com/novaldarma/LUMINA.git
cd LUMINA
docker-compose up --build
```

---

## 🎬 Video Demo Script (3-5 menit)

### [0:00-0:30] Intro

> "Halo, saya Noval dari tim LUMINA. Hari ini saya akan mendemokan LUMINA — sistem monitoring pasien Alzheimer berbasis AI menggunakan computer vision."

### [0:30-1:00] Problem

> "Di Indonesia, lebih dari 1.2 juta orang hidup dengan demensia. Pasien Alzheimer sering wandering — berjalan tanpa tujuan dan berisiko hilang. Keluarga tidak bisa mengawasi 24/7. Di sinilah LUMINA hadir."

### [1:00-1:30] Arsitektur

> "LUMINA terdiri dari 3 komponen: Family Dashboard untuk monitoring, Patient Dashboard untuk pasien, dan AI Engine di backend yang menjalankan computer vision."

### [1:30-2:30] Demo: Setup & Detection

> [Tampilkan layar]
> "Pertama, kita setup CCTV. Saya input URL kamera di Family Dashboard — bisa RTSP atau HTTP MJPEG. Klik save, sistem langsung connect."
> "Sekarang upload foto referensi pasien. Sistem akan ekstrak color fingerprint dari baju dan face encoding dari wajah."
> "Klik Start Monitoring. Lihat — pasien terdeteksi! Bounding box hijau muncul, dan log tercatat di timeline."

### [2:30-3:30] Demo: GPS & SOS

> "Fitur GPS Safe Zone: keluarga set titik pusat rumah dan radius. Jika pasien keluar radius, alert muncul."
> [Simulasi GPS di luar radius]
> "Alert! Pasien keluar safe zone."
> "SOS Button: pasien tinggal tekan satu tombol, emergency alert dengan lokasi GPS langsung terkirim."

### [3:30-4:30] Demo: Memory Gallery

> "Fitur Memories: keluarga upload foto dengan nama dan hubungan. Foto ini tampil di Patient Dashboard — membantu pasien mengingat orang tercinta."
> [Upload foto, tampilkan di patient dashboard]

### [4:30-5:00] Penutup

> "LUMINA — membuat perawatan Alzheimer lebih cerdas, satu piksel dalam satu waktu. Terima kasih."

---

## 📊 Slide Deck — One-Pager untuk Print

```
╔══════════════════════════════════════════════════════════╗
║  🧠 LUMINA — AI Alzheimer Patient Monitoring             ║
║  AMD ACT-II Hackathon | github.com/novaldarma/LUMINA     ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  PROBLEM: 1.2M+ demensia di Indonesia                    ║
║  Pasien wandering → risiko hilang & cedera               ║
║  Keluarga tidak bisa awasi 24/7                          ║
║                                                          ║
║  SOLUTION: LUMINA — monitoring + memories + GPS + SOS    ║
║                                                          ║
║  TECH: FastAPI + OpenCV + face-recognition + SQLite      ║
║  DEPLOY: docker-compose up --build (1 command)           ║
║                                                          ║
║  FEATURES:                                               ║
║  🔍 Patient Detection (color fingerprint + face recog)   ║
║  📍 GPS Safe Zone (Haversine geofencing)                 ║
║  🆘 SOS Button (one-tap emergency)                       ║
║  📸 Memory Gallery (foto + nama + hubungan)              ║
║  😊 Emotion Agent (auto-detect dari pola)                ║
║  📊 Activity Timeline (log kronologis)                   ║
║                                                          ║
║  API: 15+ endpoints | Swagger: /docs                     ║
║  PRIVACY: 100% local, no cloud, encrypted                ║
║  LICENSE: MIT (open source)                              ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
```
