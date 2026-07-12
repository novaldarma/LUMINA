# 🧠 MemoryLink: LUMINA — AI-Powered Alzheimer Patient Monitoring System

<!-- Banner image (replace with real project cover) -->

![LUMINA Banner](docs/screenshots/banner.png)

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

### 1. Why AMD infrastructure is relevant for this project

LUMINA constantly analyses video frames to detect faces, recognise colour‑based clothing patterns and infer emotional state. These workloads are **compute‑intensive** and benefit from the high‑throughput, low‑latency inference that AMD GPUs (via the ROCm stack) provide, especially on edge‑deployed devices where a powerful yet cost‑effective accelerator is required.

### 2. How the system is designed to support AMD deployment

All vision‑related operations are accessed through a **`VisionProvider` abstraction**. The default provider ships a lightweight, CPU‑based implementation, but an alternative provider that uses ROCm‑enabled PyTorch can be selected at runtime. No other module in the code‑base needs to be aware of the underlying hardware.

### 3. Configurable environment variables for AMD integration

- **`AMD_VISION_URL`** – The HTTP endpoint of an AMD‑hosted inference service (e.g., a REST API exposing a model).
- **`AMD_MODEL_NAME`** – The identifier of the specific model deployed on that service.

These variables are read when the application starts and passed to the AMD provider, allowing the same source code to target any compatible AMD inference service simply by changing the environment.

### 4. Provider‑based architecture enables backend replacement

The core application calls the generic `VisionProvider` interface. Concrete implementations (AMD, OpenAI, local ONNX, etc.) fulfil this contract. Swapping the provider does **not** require changes to the business logic, routing, or database layers.

### 5. Development with an alternative compatible endpoint

During development we often do **not** have continuous access to AMD GPU resources. The project therefore defaults to a cloud‑based inference endpoint that mimics the AMD API. By updating `AMD_VISION_URL` and `AMD_MODEL_NAME` developers can instantly switch between the placeholder service and a real AMD‑hosted service.

### 6. Simple deployment on AMD hardware

Deploying on an AMD GPU node is straightforward:

1. Provision a machine with an AMD GPU and the ROCm drivers installed.
2. Set `AMD_VISION_URL` and `AMD_MODEL_NAME` in the `.env` file or container environment.
3. Start the application – the AMD provider is automatically used. No source‑code changes are required.

#### Future Deployment

The project is **deployment‑ready** for AMD infrastructure. When AMD GPU resources become available, connecting the system to an AMD‑hosted inference endpoint is a matter of configuring the two environment variables; the rest of the application remains unchanged.

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

![Family Dashboard](docs/screenshots/family-dashboard.png)
![Patient Dashboard](docs/screenshots/patient-dashboard.png)

- **Live URL:** `http://localhost:8000` (local deployment)
  **Video Demo:** <YOUTUBE_LINK>
  **Slide Deck:** <GOOGLE_SLIDES_LINK>

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
  <i>Designing a smart communication bridge between patients, caregivers, and telemedicine technology.</i>
</p>
