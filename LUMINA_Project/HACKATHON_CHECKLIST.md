# 🏆 AMD DEVELOPER HACKATHON ACT II — SUBMISSION CHECKLIST

> Kirim file ini ke AI Agent VS Code untuk verifikasi compliance satu per satu.

---

## 📋 JUDGING CRITERIA (4 Kriteria — Bobot Sama)

### KRITERIA 1 — CREATIVITY & ORIGINALITY

| #   | Item                                                                                       | Status |
| --- | ------------------------------------------------------------------------------------------ | ------ |
| 1.1 | Face Recognition + Color Fingerprinting hybrid detection berfungsi                         | [ ]    |
| 1.2 | Stage Adaptation (1/2/3) mengubah narasi output secara berbeda per stage                   | [ ]    |
| 1.3 | Emotion Detection otomatis (calm/anxious/confused) berjalan tanpa input manual             | [ ]    |
| 1.4 | `_send_to_ai_server()` di `cctv_engine.py` memanggil AMD Vision API (bukan hanya fallback) | [ ]    |
| 1.5 | `detect_emotion_state()` di `database.py` memiliki logic heuristic yang benar              | [ ]    |
| 1.6 | Fitur tidak duplikat dari proyek hackathon lain (cek uniqueness)                           | [ ]    |

**Cek kode:**

```
cctv_engine.py → _send_to_ai_server() → AMD_VISION_URL dipanggil?
database.py → detect_emotion_state() → logic heuristic benar?
```

---

### KRITERIA 2 — PRODUCT/MARKET POTENTIAL

| #   | Item                                                                         | Status |
| --- | ---------------------------------------------------------------------------- | ------ |
| 2.1 | README.md menjelaskan business case (55M Alzheimer patients, $1.3T market)   | [ ]    |
| 2.2 | Dua user role jelas: Family Mode dan Patient Mode                            | [ ]    |
| 2.3 | Patient Dashboard bisa dipakai lansia (font besar, tombol besar, TTS)        | [ ]    |
| 2.4 | Safe Zone GPS fungsional end-to-end (POST /api/location → haversine → alert) | [ ]    |
| 2.5 | Memories feature: upload foto + tampil di patient dashboard                  | [ ]    |
| 2.6 | Ada demo URL live yang bisa diakses juri                                     | [ ]    |

**Cek kode:**

```
README.md → ada business case? ada demo URL?
patient_dashboard.html → tombol besar? TTS aktif?
frontend/app.js → GPS safe zone → POST /api/location → haversine calculation aktif?
database.py → memories table → insert_memory(), get_memories() berfungsi?
```

---

### KRITERIA 3 — COMPLETENESS

| #   | Item                                                            | Status |
| --- | --------------------------------------------------------------- | ------ |
| 3.1 | Semua endpoint API return 200, tidak ada yang 500               | [ ]    |
| 3.2 | Docker container bisa build tanpa error (`docker build .`)      | [ ]    |
| 3.3 | Docker container bisa run tanpa error (`docker-compose up`)     | [ ]    |
| 3.4 | Live URL bisa diakses dari browser manapun                      | [ ]    |
| 3.5 | GitHub repo publik dengan README lengkap                        | [ ]    |
| 3.6 | Video demo di YouTube (Unlisted) — link aktif                   | [ ]    |
| 3.7 | Slide presentasi (PDF atau Google Slides) — link aktif          | [ ]    |
| 3.8 | `requirements.txt` semua library terinstall tanpa konflik versi | [ ]    |

**Endpoint yang WAJIB return 200:**

```
[ ] GET  /api/health          → {"status": "ok"}
[ ] GET  /api/status          → monitoring status
[ ] POST /api/start-monitoring → sukses start engine
[ ] GET  /api/camera-stream   → MJPEG stream aktif
[ ] POST /api/upload-reference → upload foto berhasil + fingerprint terekstrak
[ ] GET  /api/logs            → return array log (boleh kosong)
[ ] POST /api/sos             → insert emergency log
[ ] GET  /api/memories        → return array memories
[ ] POST /api/location        → insert GPS + haversine calculation
[ ] GET  /api/patient-config  → return patient profile
[ ] GET  /api/safe-zone       → return safe zone config
[ ] PUT  /api/camera-config   → save camera URL + restart engine
[ ] GET  /api/camera-config   → return saved camera config
```

---

### KRITERIA 4 — USE OF AMD PLATFORMS (PALING KRITIS)

| #   | Item                                                             | Status |
| --- | ---------------------------------------------------------------- | ------ |
| 4.1 | `.env` berisi `AMD_VISION_URL` (tidak kosong)                    | [ ]    |
| 4.2 | `.env` berisi `AMD_MODEL_NAME`                                   | [ ]    |
| 4.3 | `cctv_engine.py` → `_send_to_ai_server()` memanggil AMD endpoint | [ ]    |
| 4.4 | README menjelaskan cara deploy ke AMD MI300X                     | [ ]    |
| 4.5 | README menyebut "AMD MI300X", "ROCm", "vLLM"                     | [ ]    |
| 4.6 | Video menyebut "AMD MI300X" minimal 2 kali                       | [ ]    |
| 4.7 | Slide presentasi ada slide khusus AMD integration                | [ ]    |

**Narasi AMD yang harus ada di README:**

```markdown
## AMD Infrastructure

LUMINA Vision Node is architecturally designed for AMD Developer Cloud:

- **Vision AI**: LLaVA multimodal model served via vLLM + ROCm on AMD MI300X
- **Deployment**: Full Docker containerization ready for AMD Developer Cloud
- **API Compatible**: OpenAI-compatible endpoint — drop-in replacement with AMD hardware

To deploy on AMD MI300X:

1. Launch AMD Developer Cloud instance with MI300X
2. Run: `python -m vllm.entrypoints.openai.api_server --model llava-hf/llava-1.5-7b-hf`
3. Update AMD_VISION_URL in .env
4. System automatically routes vision inference to AMD hardware
```

---

## 📦 SUBMISSION REQUIREMENTS FINAL

| #   | Item                                                                     | Status |
| --- | ------------------------------------------------------------------------ | ------ |
| S1  | GitHub repository PUBLIK: `https://github.com/novaldarma/LUMINA`         | [x]    |
| S2  | README.md lengkap (deskripsi, business case, AMD, install, run, demo)    | [ ]    |
| S3  | Live URL aktif: `http://localhost:8000` (atau Cloudflare Tunnel)         | [ ]    |
| S4  | `/family_dashboard.html` bisa dibuka                                     | [ ]    |
| S5  | `/patient_dashboard.html` bisa dibuka                                    | [ ]    |
| S6  | `/api/health` return 200                                                 | [ ]    |
| S7  | Docker build sukses (`docker build .`)                                   | [ ]    |
| S8  | Docker run sukses (`docker-compose up`)                                  | [ ]    |
| S9  | Video demo di YouTube (5 menit, Unlisted)                                | [ ]    |
| S10 | Slide presentasi (8+ slide, PDF/Google Slides)                           | [ ]    |
| S11 | Submission di lablab.ai lengkap (title, description, tags, cover, links) | [ ]    |

---

## 🎯 ESTIMASI PELUANG TOP 10

| Kriteria                 | Nilai (1-10) | Alasan                                                                |
| ------------------------ | ------------ | --------------------------------------------------------------------- |
| Creativity & Originality | **9/10**     | Face Rec + Color Fingerprint hybrid belum pernah ada di hackathon ini |
| Product/Market Potential | **8/10**     | 55M patients, clear business model, dua user role                     |
| Completeness             | **7/10**     | Semua fitur jalan, tapi AMD Vision masih fallback                     |
| Use of AMD Platforms     | **5/10**     | Arsitektur AMD ready tapi belum live di AMD GPU                       |

**Estimasi peluang Top 10: 60-70%**

Naik ke **80%+** jika AMD Vision API aktif dengan narasi yang kuat di README dan video.

---

## 🔧 PRIORITAS PERBAIKAN (URGENT)

1. **[KRITIS]** Aktifkan AMD Vision API di `_send_to_ai_server()` — jangan fallback
2. **[KRITIS]** Tambahkan narasi AMD di README (MI300X, ROCm, vLLM)
3. **[PENTING]** Pastikan semua 13 endpoint return 200
4. **[PENTING]** Docker build & run tanpa error
5. **[PENTING]** Video demo sebut "AMD MI300X" minimal 2 kali
6. **[NORMAL]** Slide presentasi ada slide AMD integration
7. **[NORMAL]** Submission lablab.ai lengkap dengan semua link

---

## 📝 CATATAN UNTUK AI AGENT

Saat verifikasi, cek file-file ini:

- `backend/main.py` — semua endpoint terdefinisi
- `backend/cctv_engine.py` — `_send_to_ai_server()` + AMD URL
- `backend/database.py` — semua fungsi database
- `frontend/family_dashboard.html` — UI family
- `frontend/patient_dashboard.html` — UI patient
- `frontend/app.js` — logic frontend
- `frontend/style.css` — styling
- `Dockerfile` — build instructions
- `docker-compose.yml` — run instructions
- `requirements.txt` — dependencies
- `.env` — AMD_VISION_URL + config
- `README.md` — dokumentasi
- `PRESENTATION.md` — slide content

**JANGAN ubah skema database existing (daily_logs, reference_photos, safe_zone_config).**
**JANGAN ubah fitur Patient Reference Photo yang sudah ada.**
**Jika butuh tabel baru, BUAT TERPISAH tanpa mengganggu yang lama.**
