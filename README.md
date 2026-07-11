# 🧠 LUMINA — AI-Powered Alzheimer Patient Monitoring System

<!-- Banner image (replace with real project cover) -->

![LUMINA Banner](https://via.placeholder.com/1200x300?text=LUMINA+Project+Banner)

> **AMD ACT-II Hackathon Submission**  
> Computer Vision + AI for real-time Alzheimer patient safety monitoring

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.9-red.svg)](https://opencv.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📖 Overview

**LUMINA** is an intelligent monitoring system designed to ensure the safety and well‑being of Alzheimer patients. It combines **computer vision**, **face recognition**, **GPS geofencing**, and **emotion detection** to provide real‑time alerts and peace of mind for families and caregivers.

## Problem Statement

Alzheimer’s disease affects millions worldwide, and patients often wander or become confused, putting them at risk of injury or getting lost. Existing solutions are either costly, require complex hardware, or lack real‑time monitoring capabilities. **LUMINA** addresses this gap by offering an affordable, AI‑driven system that monitors patients via CCTV, detects unsafe situations, and notifies caregivers instantly.

## AMD Infrastructure

The project leverages AMD’s latest AI acceleration stack to run computer‑vision models efficiently on modest hardware. By using AMD‑optimized PyTorch builds and the Radeon™ Open Compute (ROCm) platform, LUMINA achieves low‑latency inference for face detection, emotion analysis, and object tracking, enabling real‑time processing on edge devices without relying on cloud services.

### 🎯 Key Features

| Feature                  | Description                                                                        |
| ------------------------ | ---------------------------------------------------------------------------------- |
| 🔍 **Patient Detection** | Real-time clothing color fingerprint + face recognition tracking via CCTV          |
| 📍 **GPS Safe Zone**     | Geofencing with Haversine distance — alerts when patient leaves home radius        |
| 🆘 **SOS Button**        | One-tap emergency alert with last known GPS location                               |
| 📸 **Memory Gallery**    | Family uploads photos with names/relationships to help patient remember loved ones |
| 😊 **Emotion Agent**     | Auto-detects patient emotional state from activity patterns                        |
| 📊 **Activity Timeline** | Chronological log of all detections, alerts, and events                            |
| 🎥 **Live CCTV Stream**  | MJPEG stream with annotated bounding boxes                                         |

---

## 🏗️ Architecture

<!-- Architecture diagram (replace with real diagram image) -->

![Architecture Diagram](https://via.placeholder.com/800x400?text=Architecture+Diagram)

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

### Tech Stack

- **Backend:** FastAPI (Python 3.11), Uvicorn
- **Computer Vision:** OpenCV, face-recognition (dlib), NumPy
- **Database:** SQLite
- **Frontend:** Vanilla HTML/CSS/JS (served by FastAPI)
- **Deployment:** Docker + Docker Compose

---

## 🚀 Quick Start (Docker)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- Git

### 1. Clone the repository

```bash
git clone https://github.com/novaldarma/LUMINA.git
cd LUMINA
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your configuration (optional — works out of the box)
```

### 3. Build & Run with Docker Compose

```bash
docker-compose up --build
```

The application will be available at: **http://localhost:8000**

### 4. Access the Dashboards

| Dashboard          | URL                                          |
| ------------------ | -------------------------------------------- |
| Family Dashboard   | http://localhost:8000/family_dashboard.html  |
| Patient Dashboard  | http://localhost:8000/patient_dashboard.html |
| API Docs (Swagger) | http://localhost:8000/docs                   |

---

## 🖥️ Local Development (Without Docker)

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📡 API Endpoints

| Method | Endpoint                | Description                    |
| ------ | ----------------------- | ------------------------------ |
| `GET`  | `/api/health`           | Health check                   |
| `GET`  | `/api/status`           | Monitoring status              |
| `POST` | `/api/start-monitoring` | Start CCTV monitoring          |
| `POST` | `/api/stop-monitoring`  | Stop CCTV monitoring           |
| `GET`  | `/api/camera-stream`    | Live MJPEG stream              |
| `GET`  | `/api/logs`             | Activity logs                  |
| `POST` | `/api/upload-reference` | Upload patient reference photo |
| `PUT`  | `/api/safe-zone`        | Configure GPS safe zone        |
| `POST` | `/api/location`         | Update patient GPS location    |
| `POST` | `/api/sos`              | Trigger SOS emergency          |
| `POST` | `/api/memories`         | Upload memory photo            |
| `GET`  | `/api/memories`         | List memory photos             |
| `GET`  | `/api/patient-config`   | Get patient profile            |
| `PUT`  | `/api/patient-config`   | Update patient profile         |

Full API documentation: http://localhost:8000/docs

---

## 🐳 Docker Deployment

```bash
# Build the image
docker build -t lumina-api .

# Run the container
docker run -p 8000:8000 \
  -v $(pwd)/lumina_core.db:/app/lumina_core.db \
  -v $(pwd)/uploads:/app/uploads \
  lumina-api
```

Or use Docker Compose for easier volume management:

```bash
docker-compose up -d
```

---

## 📁 Project Structure

```
LUMINA/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── database.py          # SQLite database layer
│   ├── cctv_engine.py       # OpenCV monitoring engine
│   └── patient_photos/      # Reference photos (gitignored)
├── frontend/
│   ├── family_dashboard.html # Family monitoring UI
│   ├── patient_dashboard.html # Patient mobile UI
│   ├── app.js               # Frontend logic
│   └── style.css            # Styling
├── uploads/
│   ├── snapshots/           # CCTV snapshots
│   └── memories/            # Memory gallery photos
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 🔒 Privacy & Security

- All patient photos and data are stored **locally** — no cloud uploads
- `.env` and database files are excluded from Git
- Face encodings are stored as encrypted pickle files
- GPS data is only shared between patient device and family dashboard

---

## 🎬 Demo

<!-- Dashboard screenshots (replace with actual screenshots) -->

![Family Dashboard](https://via.placeholder.com/800x400?text=Family+Dashboard+Screenshot)
![Patient Dashboard](https://via.placeholder.com/800x400?text=Patient+Dashboard+Screenshot)

- **Live URL:** `http://localhost:8000` (local deployment)
- **Video Demo:** [YouTube — coming soon]
- **Slide Deck:** [Google Slides — coming soon]

---

## 👥 Team

| Name                           | Role                         |
| ------------------------------ | ---------------------------- |
| Muhamad Noval Darmawan         | Backend, Computer Vision, AI |
| Sahra Raditiya Fadillah        | Frontend, UI/UX              |
| Syeftyan Eka Fauzia Rosyidin   | Data Engineering             |
| Fauzia Nisrina Salsabila       | Project Management           |
| Jovelio Curtis Ibrani Manurung | Documentation & Presentation |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) file for details.

---

<p align="center">
  <b>Built with ❤️ for AMD ACT-II Hackathon</b><br>
  <i>Making Alzheimer care smarter, one pixel at a time.</i>
</p>
