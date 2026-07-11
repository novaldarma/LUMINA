"""
LUMINA Vision Node — FastAPI Backend
REST API for Alzheimer patient monitoring system.
"""

import math 
import os
import io
import shutil
import base64
import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# ── Project paths ──────────────────────────────────────────────────────────
BASE_DIR          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR      = os.path.join(BASE_DIR, "frontend")
SNAPSHOT_DIR      = os.path.join(BASE_DIR, "uploads", "snapshots")
PATIENT_PHOTO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patient_photos")

os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs(PATIENT_PHOTO_DIR, exist_ok=True)

# ── Local imports (after env loaded) ───────────────────────────────────────
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import (
     init_db,
    insert_log,
    get_all_logs,
    get_today_logs,
    get_log_count,
    delete_log,
    delete_all_logs,
    insert_reference_photo,
    get_reference_photos,
    get_reference_photo_paths,
    set_safe_zone,
    get_safe_zone,
    insert_patient_location,
    get_last_patient_location,
    insert_memory,
    get_memories,
    delete_memory,
    insert_sos,
    set_patient_config,
    get_patient_config,
    detect_emotion_state,
)
from cctv_engine import (
    start_monitoring,
    stop_monitoring,
    is_monitoring,
    get_latest_frame,
    get_monitor_status,
    extract_color_fingerprint,
    reload_patient_data,
    update_camera_config,
)

import cv2

# ── FastAPI App ────────────────────────────────────────────────────────────
app = FastAPI(
    title="LUMINA Vision Node",
    description="AI-Powered Alzheimer Patient Monitoring — Computer Vision + AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Models ────────────────────────────────────────────────────────

class MonitorResponse(BaseModel):
    success: bool
    message: str
    monitoring_active: bool


class StatusResponse(BaseModel):
    # Data wajib untuk Frontend React
    monitoring_active: bool
    mode: str
    patient_lost_count: int
    patient_detected: bool
    has_fingerprint: bool

class SafeZoneRequest(BaseModel):
    home_latitude: float
    home_longitude: float
    radius_meters: float = 100.0
    enabled: bool = True


class PatientLocationRequest(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    device_id: str = "patient-browser"


class SOSRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Data bawaan Engine v4
    running: bool
    patient_present: bool
    detection_method: str
    bbox: Optional[list] = None
    centroid: Optional[list] = None
    last_detection: float
    last_snapshot: float
    face_rec_enabled: bool
    color_fingerprint_loaded: bool
    known_faces: int
    camera_url: str

    # Camera connection state (for the frontend's connection indicator)
    camera_status: str = "disconnected"
    camera_connected: bool = False
    camera_heartbeat_age: Optional[float] = None


class PatientConfigRequest(BaseModel):
    patient_name: Optional[str] = None
    patient_stage: Optional[int] = None
    emotion_state: Optional[str] = None
    caregiver_notes: Optional[str] = None


class CameraConfigRequest(BaseModel):
    camera_url: str
    camera_username: str = ""
    camera_password: str = ""


# ── Static file mount for patient reference photos ─────────────────────────
if os.path.isdir(PATIENT_PHOTO_DIR):
    app.mount("/patient_photos", StaticFiles(directory=PATIENT_PHOTO_DIR), name="patient_photos")

# ── API Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/logs")
async def api_get_logs(limit: int = 100, offset: int = 0):
    """
    Retrieve AI monitoring logs, newest first.
    Includes snapshot images as Base64 for inline display.
    """
    logs = get_all_logs(limit=limit, offset=offset)
    total = get_log_count()

    enriched = []
    for log in logs:
        entry = dict(log)
        snapshot_path = entry.get("snapshot_image", "")
        if snapshot_path and os.path.isfile(snapshot_path):
            try:
                with open(snapshot_path, "rb") as f:
                    img_bytes = f.read()
                entry["snapshot_base64"] = base64.b64encode(img_bytes).decode("utf-8")
            except Exception:
                entry["snapshot_base64"] = None
        else:
            entry["snapshot_base64"] = None
        enriched.append(entry)

    return JSONResponse({"logs": enriched, "total": total, "limit": limit, "offset": offset})


@app.get("/api/logs/{log_id}/image")
async def api_get_log_image(log_id: int):
    """Serve a specific log's snapshot image directly."""
    logs = get_all_logs(limit=1000)
    for log in logs:
        if log["id"] == log_id:
            snapshot_path = log.get("snapshot_image", "")
            if snapshot_path and os.path.isfile(snapshot_path):
                return FileResponse(snapshot_path, media_type="image/jpeg")
            break
    raise HTTPException(status_code=404, detail="Image not found")


@app.delete("/api/logs/{log_id}")
async def api_delete_log(log_id: int):
    """Delete a single activity log by ID."""
    ok = delete_log(log_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Log not found.")
    return JSONResponse({"success": True, "message": "Log deleted."})


@app.delete("/api/logs")
async def api_delete_all_logs():
    """Delete all activity logs."""
    count = delete_all_logs()
    return JSONResponse({"success": True, "message": f"Deleted {count} log(s).", "deleted_count": count})


@app.post("/api/upload-reference")
async def api_upload_reference(file: UploadFile = File(...)):
    """
    Upload a full-body photo of the patient.
    System auto-extracts clothing color fingerprint for tracking.
    Photo saved to backend/patient_photos/ and recorded in the database.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_ext = {".jpg", ".jpeg", ".png", ".bmp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Please use: {', '.join(allowed_ext)}",
        )

    safe_name = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    file_path = os.path.join(PATIENT_PHOTO_DIR, safe_name)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    photo_id = insert_reference_photo(safe_name, file_path)

    # Auto-extract clothing color fingerprint from the uploaded photo
    fingerprint_ok = extract_color_fingerprint(file_path)

    return JSONResponse({
        "success": True,
        "message": "Reference photo uploaded successfully." + (
            " Clothing color fingerprint extracted successfully."
            if fingerprint_ok else
            " But color fingerprint extraction failed — try uploading a full-body photo."
        ),
        "photo_id": photo_id,
        "filename": safe_name,
        "fingerprint_ok": fingerprint_ok,
    })


@app.post("/api/reload-patient-data")
async def api_reload_patient_data():
    """Reload the engine's color fingerprint and face encodings from disk."""
    reload_patient_data()
    return JSONResponse({"success": True, "message": "Patient data reloaded in engine."})


@app.get("/api/reference-photos")
async def api_get_reference_photos():
    """List all uploaded reference photos."""
    photos = get_reference_photos()
    return JSONResponse({"photos": photos})


@app.delete("/api/reference-photos/{photo_id}")
async def api_delete_reference_photo(photo_id: int):
    """Delete a reference photo by ID."""
    import sqlite3
    from database import DB_PATH

    photos = get_reference_photos()
    target = None
    for p in photos:
        if p["id"] == photo_id:
            target = p
            break

    if target is None:
        raise HTTPException(status_code=404, detail="Reference photo not found.")

    filepath = target["filepath"]
    if os.path.isfile(filepath):
        os.remove(filepath)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM reference_photos WHERE id = ?", (photo_id,))
    conn.commit()
    conn.close()

    return JSONResponse({"success": True, "message": "Reference photo deleted."})


@app.get("/api/camera-stream")
async def api_camera_stream():
    """
    MJPEG stream endpoint — serves the live, pre-annotated frames produced
    by the CCTV engine's render loop as a multipart MJPEG stream.

    Frames are already JPEG-encoded by the engine (see cctv_engine.py
    _render_loop), so this endpoint just pushes bytes as fast as new frames
    become available — no per-request encoding here. This is a plain
    (synchronous) generator, which Starlette automatically runs in a thread
    pool, so it never blocks the asyncio event loop.
    """
    import numpy as np
    import time
    import cv2

    TARGET_FPS = 25
    FRAME_INTERVAL = 1.0 / TARGET_FPS

    def generate_frames():
        last_sent = time.time()
        while True:
            frame_bytes = get_latest_frame()
            if frame_bytes is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + frame_bytes
                    + b"\r\n"
                )
            else:
                # Send a placeholder frame when no camera is active
                blank = 255 * np.ones((360, 640, 3), dtype=np.uint8)
                cv2.putText(
                    blank, "Waiting for camera...", (140, 190),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 255), 2,
                )
                cv2.putText(
                    blank, 'Click "Start Monitoring"', (120, 230),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 150, 255), 2,
                )
                ret, jpeg = cv2.imencode(".jpg", blank, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ret:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + jpeg.tobytes()
                        + b"\r\n"
                    )

            # Pace by elapsed time instead of a fixed sleep, so a single slow
            # iteration doesn't compound into growing delay over time
            now = time.time()
            time.sleep(max(0.0, FRAME_INTERVAL - (now - last_sent)))
            last_sent = time.time()

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",  # disable buffering if proxied behind nginx
        },
    )

@app.post("/api/start-monitoring")
async def api_start_monitoring():
    """Start the background OpenCV monitoring loop."""
    if is_monitoring():
        return MonitorResponse(
            success=False,
            message="Monitoring is already running.",
            monitoring_active=True,
        )

    ok = start_monitoring()
    if ok:
        return MonitorResponse(
            success=True,
            message="Monitoring started. System searching for patient...",
            monitoring_active=True,
        )
    else:
        return MonitorResponse(
            success=False,
            message="Failed to start monitoring.",
            monitoring_active=False,
        )


@app.post("/api/stop-monitoring")
async def api_stop_monitoring():
    """Stop the background OpenCV monitoring loop."""
    ok = stop_monitoring()
    return MonitorResponse(
        success=ok,
        message="Monitoring stopped." if ok else "Monitoring is not currently running.",
        monitoring_active=is_monitoring(),
    )


@app.get("/api/status")
async def api_status():
    """Get the current monitoring status."""
    data = get_monitor_status()

    # Bridge: map backend field names to what the frontend expects
    data["monitoring_active"] = data.get("running", False)
    data["mode"] = data.get("detection_method", "none")
    data["patient_lost_count"] = 0
    data["patient_detected"] = data.get("patient_present", False)
    data["has_fingerprint"] = data.get("color_fingerprint_loaded", False) or data.get("face_rec_enabled", False)
    
    return StatusResponse(**data)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "LUMINA Vision Node", "version": "1.0.0"}

# =========================================================
# PATIENT DASHBOARD AND GPS SAFE ZONE
# =========================================================

def calculate_distance_meters(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """
    Calculate the distance between two GPS coordinates
    using the Haversine formula.
    """

    earth_radius = 6_371_000

    lat_1 = math.radians(latitude_1)
    lat_2 = math.radians(latitude_2)

    delta_latitude = math.radians(
        latitude_2 - latitude_1
    )

    delta_longitude = math.radians(
        longitude_2 - longitude_1
    )

    haversine_value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(lat_1)
        * math.cos(lat_2)
        * math.sin(delta_longitude / 2) ** 2
    )

    central_angle = 2 * math.atan2(
        math.sqrt(haversine_value),
        math.sqrt(1 - haversine_value),
    )

    return earth_radius * central_angle


@app.get("/api/safe-zone")
async def api_get_safe_zone():
    """Return the configured home safe zone."""

    safe_zone = get_safe_zone()

    configured = bool(
        safe_zone
        and safe_zone.get("home_latitude") is not None
        and safe_zone.get("home_longitude") is not None
    )

    return {
        "success": True,
        "configured": configured,
        "safe_zone": safe_zone,
    }


@app.put("/api/safe-zone")
async def api_set_safe_zone(
    payload: SafeZoneRequest,
):
    """Set the home location and safe-zone radius."""

    if payload.radius_meters <= 0:
        raise HTTPException(
            status_code=400,
            detail="Safe-zone radius must be greater than zero.",
        )

    safe_zone = set_safe_zone(
        home_latitude=payload.home_latitude,
        home_longitude=payload.home_longitude,
        radius_meters=payload.radius_meters,
        enabled=payload.enabled,
    )

    insert_log(
        alert_status="Safe",
        activity_description=(
            "The home safe zone was configured with a "
            f"{payload.radius_meters:.0f}-meter radius."
        ),
        narrative_report=(
            "The family updated the patient's home safe-zone configuration."
        ),
        snapshot_image="",
    )

    return {
        "success": True,
        "message": "The safe zone was saved successfully.",
        "safe_zone": safe_zone,
    }


@app.post("/api/location")
async def api_update_patient_location(
    payload: PatientLocationRequest,
):
    """
    Receive the patient's device location and determine
    whether it is inside the home safe zone.
    """

    safe_zone = get_safe_zone()
    previous_location = get_last_patient_location()

    safe_zone_configured = bool(
        safe_zone
        and safe_zone.get("enabled")
        and safe_zone.get("home_latitude") is not None
        and safe_zone.get("home_longitude") is not None
    )

    distance_from_home = None
    inside_safe_zone = None

    if safe_zone_configured:
        distance_from_home = calculate_distance_meters(
            safe_zone["home_latitude"],
            safe_zone["home_longitude"],
            payload.latitude,
            payload.longitude,
        )

        inside_safe_zone = (
            distance_from_home
            <= float(safe_zone["radius_meters"])
        )

    location_id = insert_patient_location(
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy=payload.accuracy,
        distance_from_home=distance_from_home,
        inside_safe_zone=inside_safe_zone,
        device_id=payload.device_id,
    )

    previous_inside_status = None

    if previous_location is not None:
        previous_inside_status = previous_location.get(
            "inside_safe_zone"
        )

    # Only create a timeline log when the zone status changes.
    if inside_safe_zone is not None:
        if (
            previous_inside_status is None
            and not inside_safe_zone
        ):
            insert_log(
                alert_status="Attention",
                activity_description=(
                    "The patient's device was detected outside "
                    f"the safe zone, approximately "
                    f"{distance_from_home:.0f} meters from home."
                ),
                narrative_report=(
                    "LUMINA detected that the patient's device "
                    "is outside the configured home radius. "
                    "The family should verify the patient's location."
                ),
                snapshot_image="",
            )

        elif (
            previous_inside_status is not None
            and bool(previous_inside_status)
            != inside_safe_zone
        ):
            if inside_safe_zone:
                insert_log(
                    alert_status="Safe",
                    activity_description=(
                        "The patient's device returned "
                        "to the home safe zone."
                    ),
                    narrative_report=(
                        "The patient's device is now back "
                        "inside the configured home radius."
                    ),
                    snapshot_image="",
                )
            else:
                insert_log(
                    alert_status="Attention",
                    activity_description=(
                        "The patient's device left the safe zone. "
                        f"Current distance from home is approximately "
                        f"{distance_from_home:.0f} meters."
                    ),
                    narrative_report=(
                        "LUMINA detected that the patient may have "
                        "left the safe area. The family should verify "
                        "the patient's location."
                    ),
                    snapshot_image="",
                )

    return {
        "success": True,
        "location_id": location_id,
        "safe_zone_configured": safe_zone_configured,
        "inside_safe_zone": inside_safe_zone,
        "distance_from_home": (
            round(distance_from_home, 2)
            if distance_from_home is not None
            else None
        ),
        "radius_meters": (
            safe_zone.get("radius_meters")
            if safe_zone
            else None
        ),
        "accuracy": payload.accuracy,
    }


@app.get("/api/location/latest")
async def api_get_latest_location():
    """Return the latest patient-device location."""

    return {
        "success": True,
        "location": get_last_patient_location(),
        "safe_zone": get_safe_zone(),
    }


@app.get("/api/patient/today")
async def api_patient_today():
    """Create a simple recap of today's recorded activities."""

    logs = get_today_logs()

    events = []
    known_descriptions = set()

    for log in logs:
        description = (
            log.get("activity_description") or ""
        ).strip()

        if not description:
            continue

        normalized_description = description.lower()

        if normalized_description in known_descriptions:
            continue

        known_descriptions.add(normalized_description)

        events.append({
            "timestamp": log.get("timestamp"),
            "status": log.get("alert_status"),
            "activity": description,
        })

    if not events:
        answer = (
            "No activities have been recorded today. "
            "LUMINA will update this summary after a verified "
            "activity is recorded."
        )
    else:
        recent_events = events[-5:]

        activity_sentences = [
            event["activity"]
            for event in recent_events
        ]

        answer = (
            "Here is what LUMINA recorded today: "
            + " ".join(activity_sentences)
        )

    return {
        "success": True,
        "answer": answer,
        "total_events": len(events),
        "events": events[-10:],
    }


@app.post("/api/sos")
async def api_patient_sos(
    payload: SOSRequest,
):
    """Create an emergency SOS event."""

    latitude = payload.latitude
    longitude = payload.longitude

    if latitude is None or longitude is None:
        latest_location = get_last_patient_location()

        if latest_location:
            latitude = latest_location.get("latitude")
            longitude = latest_location.get("longitude")

    sos_id = insert_sos(
        latitude=latitude,
        longitude=longitude,
    )

    location_description = ""

    if latitude is not None and longitude is not None:
        location_description = (
            f" Last known location: "
            f"{latitude:.6f}, {longitude:.6f}."
        )

    insert_log(
        alert_status="Emergency",
        activity_description=(
            "The patient pressed the SOS button."
            + location_description
        ),
        narrative_report=(
            "The patient requested immediate assistance through "
            "the LUMINA SOS button. The family should contact or "
            "check on the patient immediately."
        ),
        snapshot_image="",
    )

    return {
        "success": True,
        "status": "SOS_SENT",
        "sos_id": sos_id,
        "message": "The emergency request was sent successfully.",
        "latitude": latitude,
        "longitude": longitude,
    }

# =========================================================
# PATIENT CONFIG — Stage Adaptation & Emotion Agent
# =========================================================

@app.get("/api/patient-config")
async def api_get_patient_config():
    """Return the current patient configuration (stage, emotion, name)."""
    config = get_patient_config()
    auto_emotion = detect_emotion_state()

    return {
        "success": True,
        "config": config,
        "auto_detected_emotion": auto_emotion,
    }


@app.put("/api/patient-config")
async def api_update_patient_config(payload: PatientConfigRequest):
    """
    Update the patient profile.
    Any unset field will keep its current value.
    """
    updated = set_patient_config(
        patient_name=payload.patient_name,
        patient_stage=payload.patient_stage,
        emotion_state=payload.emotion_state,
        caregiver_notes=payload.caregiver_notes,
    )

    return {
        "success": True,
        "message": "Patient configuration updated.",
        "config": updated,
    }


# =========================================================
# MEMORIES — Family-to-Patient Photo Memories (TASK 3)
# =========================================================

MEMORIES_DIR = os.path.join(BASE_DIR, "uploads", "memories")
os.makedirs(MEMORIES_DIR, exist_ok=True)


class MemoryCreateRequest(BaseModel):
    person_name: str
    relationship: str


@app.post("/api/memories")
async def api_create_memory(
    person_name: str = "",
    relationship: str = "",
    file: UploadFile = File(...),
):
    """
    Upload a guest/relative photo for the patient's Memories feature.
    This is SEPARATE from the face recognition system.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_ext = {".jpg", ".jpeg", ".png", ".bmp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Please use: {', '.join(allowed_ext)}",
        )

    safe_name = f"memory_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    file_path = os.path.join(MEMORIES_DIR, safe_name)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    memory_id = insert_memory(
        photo_path=file_path,
        person_name=person_name,
        relationship=relationship,
    )

    return JSONResponse({
        "success": True,
        "message": "Memory saved successfully.",
        "memory_id": memory_id,
        "filename": safe_name,
    })


@app.get("/api/memories")
async def api_get_memories(limit: int = 20):
    """Return recent memory entries with Base64-encoded photos."""
    memories = get_memories(limit=limit)

    enriched = []
    for mem in memories:
        entry = dict(mem)
        photo_path = entry.get("photo_path", "")
        if photo_path and os.path.isfile(photo_path):
            try:
                with open(photo_path, "rb") as f:
                    img_bytes = f.read()
                entry["photo_base64"] = base64.b64encode(img_bytes).decode("utf-8")
            except Exception:
                entry["photo_base64"] = None
        else:
            entry["photo_base64"] = None
        enriched.append(entry)

    return JSONResponse({"memories": enriched, "total": len(enriched)})


@app.delete("/api/memories/{memory_id}")
async def api_delete_memory(memory_id: int):
    """Delete a memory entry by ID."""
    ok = delete_memory(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return JSONResponse({"success": True, "message": "Memory deleted."})


# =========================================================
# CAMERA CONFIG — Dynamic CCTV URL / Username / Password
# =========================================================

@app.get("/api/camera-config")
async def api_get_camera_config():
    """Return the current camera configuration (URL, username). Password is masked."""
    import json
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            return {
                "success": True,
                "camera_url": cfg.get("camera_url", ""),
                "camera_username": cfg.get("camera_username", ""),
                "camera_password": "••••••" if cfg.get("camera_password") else "",
                "has_password": bool(cfg.get("camera_password")),
            }
        except Exception:
            pass

    # Fallback to env
    return {
        "success": True,
        "camera_url": os.getenv("CAMERA_URL", ""),
        "camera_username": os.getenv("CAMERA_USERNAME", ""),
        "camera_password": "••••••" if os.getenv("CAMERA_PASSWORD") else "",
        "has_password": bool(os.getenv("CAMERA_PASSWORD")),
    }


@app.put("/api/camera-config")
async def api_update_camera_config(payload: CameraConfigRequest):
    """
    Update the CCTV camera URL, username, and password.
    Saves to camera_config.json and updates the running engine.
    """
    if not payload.camera_url:
        raise HTTPException(status_code=400, detail="Camera URL is required.")

    # Save to JSON config file
    import json
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_config.json")
    cfg = {
        "camera_url": payload.camera_url,
        "camera_username": payload.camera_username,
        "camera_password": payload.camera_password,
    }
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)

    # Update the running engine
    update_camera_config(
        url=payload.camera_url,
        username=payload.camera_username,
        password=payload.camera_password,
    )

    insert_log(
        alert_status="Safe",
        activity_description="Camera configuration updated.",
        narrative_report="The family updated the CCTV camera connection settings.",
        snapshot_image="",
    )

    return {
        "success": True,
        "message": "Camera configuration saved. Restart monitoring to apply.",
        "camera_url": payload.camera_url,
    }


# ── Serve Frontend ─────────────────────────────────────────────────────────

@app.get("/")
async def serve_frontend():
    """Serve the main dashboard HTML."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(html_content)
    return HTMLResponse("<h1>LUMINA Vision Node — Frontend not found</h1>", status_code=404)


# Mount frontend static assets (CSS, JS, etc.)
if os.path.isdir(FRONTEND_DIR):
    @app.get("/{filename:path}")
    async def serve_static(filename: str):
        """Serve static files from frontend directory (CSS, JS, images)."""
        # Skip API routes
        if filename.startswith("api/") or filename.startswith("patient_photos/"):
            raise HTTPException(status_code=404)

        file_path = os.path.join(FRONTEND_DIR, filename)
        if os.path.isfile(file_path):
            # Determine media type
            ext = Path(filename).suffix.lower()
            media_types = {
                ".css": "text/css",
                ".js": "application/javascript",
                ".html": "text/html",
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".ico": "image/x-icon",
            }
            media_type = media_types.get(ext, "application/octet-stream")
            return FileResponse(file_path, media_type=media_type)

        # Fallback to index.html for SPA-style routing
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.isfile(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())

        raise HTTPException(status_code=404, detail="File not found")


# ── Startup ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")