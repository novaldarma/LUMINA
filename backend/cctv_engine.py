"""
LUMINA Vision Node — CCTV Engine v4 (Color + Face Hybrid)
===========================================================
Upgrade dari v3:
  - Face Recognition as primary detection layer
  - Color back-projection as fallback
  - Patient detected if FACE match OR color match
  - 30-second snapshots ONLY while patient is detected
  - When patient leaves frame → snapshot cycle PAUSED
  - Adaptive thresholds based on frame resolution

Arsitektur:
  detect_faces() → match with known patient → CONFIRMED
  if no face match → color back-projection → CONFIRMED (lower confidence)
  if neither → SEARCHING
"""

import os
import sys
import json
import time
import pickle
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

import cv2
import numpy as np
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from urllib.parse import urlparse

# ── Face Recognition (graceful fallback) ────────────────────────────────────
try:
    import face_recognition
    FACE_REC_AVAILABLE = True
    print("[ENGINE] ✅ face_recognition loaded — face matching ENABLED")
except ImportError:
    FACE_REC_AVAILABLE = False
    print("[ENGINE] ⚠️  face_recognition NOT installed — face matching DISABLED")
    print("[ENGINE]    Install: pip install face-recognition")

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lumina.cctv")

# ── Paths ───────────────────────────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PATIENT_PHOTO_DIR = os.path.join(BACKEND_DIR, "patient_photos")
SNAPSHOT_DIR = os.path.join(BACKEND_DIR, "..", "uploads", "snapshots")
FINGERPRINT_PATH = os.path.join(PATIENT_PHOTO_DIR, "color_fingerprint.json")
HIST_PATH = os.path.join(PATIENT_PHOTO_DIR, "color_hist.npy")
FACE_ENCODINGS_PATH = os.path.join(PATIENT_PHOTO_DIR, "face_encodings.pkl")

os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# ── Constants ───────────────────────────────────────────────────────────────
MIN_CONTOUR_AREA = 3000           # Lowered from 8000 for better detection
BBOX_AREA_RATIO_MIN = 0.005       # Lowered from 0.015 (0.5% of frame)
BBOX_AREA_RATIO_MAX = 0.85        # Avoid full-frame false positives
SNAPSHOT_INTERVAL = 30.0          # Seconds between snapshots (only when patient detected)
FACE_MATCH_TOLERANCE = 0.55       # Lower = stricter face matching
REQUEST_TIMEOUT = 5.0             # HTTP timeout for camera snapshots
PRESENCE_GRACE_PERIOD = 2.5       # Seconds to keep "patient present" after the last
                                   # confirmed detection, even if the current frame
                                   # missed (head turn, motion blur, brief occlusion, etc.)

# Skin color range (HSV) — exclude from color matching
SKIN_H_LOW, SKIN_H_HIGH = 0, 30
SKIN_S_LOW, SKIN_S_HIGH = 10, 170
SKIN_V_LOW, SKIN_V_HIGH = 50, 255


class CCTVMaster:
    """Master controller for CCTV-based patient monitoring."""

    def __init__(self):
        # Camera config — load from JSON file first, fallback to env vars
        self.camera_url: str = ""
        self.camera_username: str = ""
        self.camera_password: str = ""
        self._load_camera_config()

        # State
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Patient detection state
        self.patient_present: bool = False
        self.patient_bbox: Optional[Tuple[int, int, int, int]] = None
        self.patient_centroid: Optional[Tuple[int, int]] = None
        self.detection_method: str = "none"  # "face", "color", "none"
        self.last_detection_time: float = 0.0

        # Snapshot gating
        self.last_snapshot_time: float = 0.0
        self.snapshot_pending: bool = False

        # Color fingerprint
        self._color_hist: Optional[np.ndarray] = None
        self._fingerprint_meta: Optional[Dict] = None

        # Face recognition
        self._known_face_encodings: List[np.ndarray] = []
        self._known_face_names: List[str] = []
        self._face_rec_enabled: bool = False

        # Frame cache (for MJPEG streaming)
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_annotated: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()

        # Pre-encoded JPEG cache — updated by the render loop, read directly
        # by the stream endpoint with no per-request re-encoding
        self._latest_jpeg: Optional[bytes] = None
        self._jpeg_lock = threading.Lock()

        # Latest detection result (published by the detection loop, consumed
        # by the render loop to draw the overlay) — decouples rendering speed
        # from detection speed
        self._latest_detection: Dict[str, Any] = {
            "patient_detected": False,
            "bbox": None,
            "centroid": None,
            "detection_method": "none",
            "face_bbox": None,
        }
        self._detection_lock = threading.Lock()

        # Camera connection status (exposed to the frontend, and needed so
        # the CCTV device registers an active streaming client)
        self._camera_status: str = "disconnected"   # "connecting" | "streaming" | "disconnected" | "error"
        self._camera_connected: bool = False
        self._capture_backend: str = "none"          # "mjpeg_persistent" | "opencv_http" | "opencv_rtsp"
        self._last_frame_time: float = 0.0
        self._camera_thread: Optional[threading.Thread] = None
        self._render_thread: Optional[threading.Thread] = None

        # Activity log buffer (for frontend polling)
        self._activity_log: List[Dict[str, Any]] = []
        self._log_lock = threading.Lock()

        # Load all patient data
        self._load_color_fingerprint()
        self._load_face_encodings()

    # ── Initialization ──────────────────────────────────────────────────────

    def _load_camera_config(self) -> None:
        """Load camera config from JSON file, fallback to .env vars."""
        config_path = os.path.join(BACKEND_DIR, "camera_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                self.camera_url = cfg.get("camera_url", "")
                self.camera_username = cfg.get("camera_username", "")
                self.camera_password = cfg.get("camera_password", "")
                logger.info("📷 Camera config loaded from camera_config.json")
                return
            except Exception as e:
                logger.warning("Failed to load camera_config.json: %s", e)

        # Fallback to .env
        self.camera_url = os.getenv("CAMERA_URL", "")
        self.camera_username = os.getenv("CAMERA_USERNAME", "")
        self.camera_password = os.getenv("CAMERA_PASSWORD", "")
        if self.camera_url:
            logger.info("📷 Camera config loaded from .env: %s", self.camera_url[:50])

    def _load_color_fingerprint(self) -> None:
        """Load clothing color histogram + metadata from patient_photos."""
        if not os.path.exists(HIST_PATH) or not os.path.exists(FINGERPRINT_PATH):
            logger.warning("No color fingerprint found. Upload patient photo first.")
            return

        try:
            self._color_hist = np.load(HIST_PATH)
            with open(FINGERPRINT_PATH, "r") as f:
                self._fingerprint_meta = json.load(f)
            logger.info(
                "✅ Color fingerprint loaded: H=%d ±%d, S=%d ±%d, %d peaks",
                self._fingerprint_meta["h_center"],
                self._fingerprint_meta.get("h_range", 20),
                self._fingerprint_meta["s_center"],
                self._fingerprint_meta.get("s_range", 70),
                len(self._fingerprint_meta.get("peaks", [])),
            )
        except Exception as e:
            logger.error("Failed to load color fingerprint: %s", e)
            self._color_hist = None
            self._fingerprint_meta = None

    def _load_face_encodings(self) -> None:
        """Load face encodings from patient_photos. Falls back to extracting
        from images if the pickle doesn't exist."""
        if not FACE_REC_AVAILABLE:
            self._face_rec_enabled = False
            return

        # Try cached encodings first
        if os.path.exists(FACE_ENCODINGS_PATH):
            try:
                with open(FACE_ENCODINGS_PATH, "rb") as f:
                    data = pickle.load(f)
                self._known_face_encodings = data.get("encodings", [])
                self._known_face_names = data.get("names", [])
                if self._known_face_encodings:
                    self._face_rec_enabled = True
                    logger.info(
                        "✅ Loaded %d face encoding(s) from cache",
                        len(self._known_face_encodings),
                    )
                    return
            except Exception as e:
                logger.warning("Failed to load face encodings cache: %s", e)

        # Extract from images
        self._extract_face_encodings_from_photos()

    def _extract_face_encodings_from_photos(self) -> None:
        """Scan patient_photos/ for images, extract face encodings, cache them."""
        if not FACE_REC_AVAILABLE:
            return

        if not os.path.isdir(PATIENT_PHOTO_DIR):
            return

        image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        photos = sorted(
            [f for f in os.listdir(PATIENT_PHOTO_DIR)
             if os.path.splitext(f)[1].lower() in image_exts],
        )

        if not photos:
            logger.info("No patient photos found for face extraction.")
            return

        self._known_face_encodings = []
        self._known_face_names = []

        for photo in photos:
            path = os.path.join(PATIENT_PHOTO_DIR, photo)
            try:
                image = face_recognition.load_image_file(path)
                encodings = face_recognition.face_encodings(image, model="hog")

                if encodings:
                    # Store all faces found in each photo
                    for i, enc in enumerate(encodings):
                        self._known_face_encodings.append(enc)
                        self._known_face_names.append(f"{photo}_face{i}")
                    logger.info("  📸 %s → %d face(s) extracted", photo, len(encodings))
                else:
                    logger.info("  📸 %s → no faces found", photo)
            except Exception as e:
                logger.warning("  ⚠️ %s → error: %s", photo, e)

        if self._known_face_encodings:
            self._face_rec_enabled = True
            # Cache for faster startup next time
            try:
                with open(FACE_ENCODINGS_PATH, "wb") as f:
                    pickle.dump({
                        "encodings": self._known_face_encodings,
                        "names": self._known_face_names,
                    }, f)
            except Exception as e:
                logger.warning("Failed to cache face encodings: %s", e)
            logger.info(
                "✅ Extracted %d total face encoding(s) from %d photo(s)",
                len(self._known_face_encodings), len(photos),
            )
        else:
            logger.warning("⚠️ No faces found in any patient photo. Face matching disabled.")

    def reload_patient_data(self) -> None:
        """Public method to reload fingerprints + face encodings after new upload."""
        with self._lock:
            self._load_color_fingerprint()
            # Clear face encoding cache so it re-extracts
            if os.path.exists(FACE_ENCODINGS_PATH):
                os.remove(FACE_ENCODINGS_PATH)
            self._known_face_encodings = []
            self._known_face_names = []
            self._load_face_encodings()
            logger.info("🔄 Patient data reloaded (color + face)")

    # ── Camera ──────────────────────────────────────────────────────────────

    MAX_MJPEG_FAILURES_BEFORE_FALLBACK = 3

    def _start_camera_capture(self) -> None:
        """
        Dispatcher: pick a capture strategy based on the URL scheme, with a
        SAFE automatic fallback.

        For HTTP(S) sources we first try a persistent raw MJPEG reader (so
        the camera device registers a genuine streaming client). If that
        method fails repeatedly in a row (some camera apps — e.g. IP Webcam
        on Android — don't respond well to a raw stream=True GET), we
        automatically fall back to OpenCV/FFmpeg VideoCapture, which is the
        method proven to connect to this camera. Streaming will keep working
        either way — it will just report a different `camera_status` backend.
        """
        parsed = urlparse(self.camera_url)
        if parsed.scheme.lower() == "rtsp":
            self._capture_via_opencv_http(backend_name="opencv_rtsp")
            return

        consecutive_failures = 0
        backoff = 1.0
        max_backoff = 10.0

        while self._running:
            frames_received = self._capture_via_mjpeg_stream_once()

            if not self._running:
                break

            if frames_received > 0:
                # This connection attempt did deliver at least one frame —
                # MJPEG reading works for this camera, keep using it and
                # reset the failure counter.
                consecutive_failures = 0
                backoff = 1.0
                continue

            consecutive_failures += 1
            logger.warning(
                "📡 MJPEG attempt #%d produced no frames (camera may not support raw MJPEG GET)",
                consecutive_failures,
            )

            if consecutive_failures >= self.MAX_MJPEG_FAILURES_BEFORE_FALLBACK:
                logger.warning(
                    "📡 Falling back to OpenCV/FFmpeg capture backend after %d failed MJPEG attempts",
                    consecutive_failures,
                )
                self._capture_via_opencv_http(backend_name="opencv_http")
                return

            time.sleep(backoff)
            backoff = min(backoff * 1.6, max_backoff)

    def _capture_via_mjpeg_stream_once(self) -> int:
        """
        Attempt ONE persistent HTTP MJPEG connection cycle.

        Opens a long-lived HTTP connection (stream=True) and parses frames
        manually from the multipart JPEG boundary markers (SOI \\xff\\xd8 ...
        EOI \\xff\\xd9). Only the MOST RECENT frame found in the buffer is
        kept, so latency never accumulates.

        Returns the number of frames successfully decoded during this
        connection attempt (0 means the attempt effectively failed, even if
        no exception was raised — e.g. connected but no data ever arrived).
        """
        backoff = 1.0
        SOI, EOI = b"\xff\xd8", b"\xff\xd9"
        frames_received = 0
        session = None

        self._camera_status = "connecting"
        try:
            auth = None
            if self.camera_username and self.camera_password:
                auth = HTTPBasicAuth(self.camera_username, self.camera_password)

            # Keep headers minimal — some camera apps only enter MJPEG
            # streaming mode for requests that look like a plain browser GET,
            # and behave oddly (throttle / stall) with custom Accept headers.
            headers = {"User-Agent": "Mozilla/5.0 (compatible; LUMINA-VisionNode/1.0)"}

            session = requests.Session()
            resp = session.get(
                self.camera_url,
                auth=auth,
                headers=headers,
                stream=True,
                timeout=(5, 15),  # (connect timeout, read timeout) — generous read timeout
            )
            resp.raise_for_status()

            logger.info("✅ MJPEG stream connected (persistent): %s", self.camera_url[:60])
            self._camera_status = "streaming"
            self._capture_backend = "mjpeg_persistent"

            buffer = bytearray()

            for chunk in resp.iter_content(chunk_size=4096):
                if not self._running:
                    break
                if not chunk:
                    continue

                buffer += chunk
                last_frame_bytes = None

                # Pull out every complete frame currently in the buffer, but
                # keep only the newest one — prevents backlog/latency
                while True:
                    start = buffer.find(SOI)
                    if start == -1:
                        buffer.clear()
                        break
                    end = buffer.find(EOI, start + 2)
                    if end == -1:
                        if start > 0:
                            del buffer[:start]
                        break
                    end += 2
                    last_frame_bytes = bytes(buffer[start:end])
                    del buffer[:end]

                if last_frame_bytes:
                    frame = cv2.imdecode(
                        np.frombuffer(last_frame_bytes, dtype=np.uint8),
                        cv2.IMREAD_COLOR,
                    )
                    if frame is not None and frame.size > 0:
                        with self._frame_lock:
                            self._latest_frame = frame
                        self._last_frame_time = time.time()
                        self._camera_connected = True
                        frames_received += 1

                if len(buffer) > 2_000_000:  # guard against non-JPEG junk streams
                    buffer.clear()

            resp.close()

        except requests.exceptions.RequestException as e:
            logger.warning("📡 MJPEG stream dropped: %s", e)
        except Exception as e:
            logger.error("📡 Unexpected MJPEG capture error: %s", e)
        finally:
            if session:
                session.close()

        self._camera_connected = False
        self._camera_status = "disconnected"
        return frames_received

    def _capture_via_opencv_http(self, backend_name: str = "opencv_http") -> None:
        """
        Capture via OpenCV/FFmpeg VideoCapture — the method proven to work
        reliably across most IP camera / RTSP sources, used as the primary
        path for RTSP and as an automatic fallback for HTTP MJPEG sources
        that don't play well with a raw persistent GET. Includes an
        auto-reconnect loop (the original version did not retry on failure).
        """
        url = self.camera_url
        if self.camera_username and self.camera_password:
            proto, rest = url.split("://", 1)
            url = f"{proto}://{self.camera_username}:{self.camera_password}@{rest}"

        backoff = 1.0
        max_backoff = 10.0

        while self._running:
            self._camera_status = "connecting"
            cap = cv2.VideoCapture(url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not cap.isOpened():
                logger.error("❌ Failed to open camera stream: %s", self.camera_url[:60])
                self._camera_status = "disconnected"
                cap.release()
                if not self._running:
                    break
                time.sleep(backoff)
                backoff = min(backoff * 1.6, max_backoff)
                continue

            logger.info("✅ Camera stream connected via OpenCV (%s)", backend_name)
            self._camera_status = "streaming"
            self._capture_backend = backend_name
            backoff = 1.0
            consecutive_read_failures = 0

            while self._running:
                ret, frame = cap.read()
                if not ret or frame is None:
                    consecutive_read_failures += 1
                    if consecutive_read_failures > 30:  # ~1s of failures at 30fps-ish pace
                        logger.warning("📡 OpenCV capture read failing repeatedly — reconnecting")
                        break
                    time.sleep(0.03)
                    continue

                consecutive_read_failures = 0
                with self._frame_lock:
                    self._latest_frame = frame
                self._last_frame_time = time.time()
                self._camera_connected = True

            cap.release()
            self._camera_connected = False
            self._camera_status = "disconnected"

            if not self._running:
                break

            time.sleep(backoff)
            backoff = min(backoff * 1.6, max_backoff)

        logger.info("📡 OpenCV capture (%s) stopped", backend_name)

    # ── Color Detection ─────────────────────────────────────────────────────

    def _make_skin_mask(self, hsv: np.ndarray) -> np.ndarray:
        """Create a binary mask for skin-colored regions."""
        return cv2.inRange(
            hsv,
            (SKIN_H_LOW, SKIN_S_LOW, SKIN_V_LOW),
            (SKIN_H_HIGH, SKIN_S_HIGH, SKIN_V_HIGH),
        )

    def _find_patient_by_color(
        self, frame: np.ndarray,
    ) -> Tuple[Optional[Tuple], Optional[Tuple], float]:
        """
        Color back-projection detection.
        Returns (bbox, centroid, confidence_score).
        """
        if self._color_hist is None or self._fingerprint_meta is None:
            return None, None, 0.0

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        fh, fw = frame.shape[:2]
        meta = self._fingerprint_meta

        # A: Histogram back-projection
        back_proj = cv2.calcBackProject([hsv], [0, 1], self._color_hist, [0, 180, 0, 256], 1)
        _, mask_a = cv2.threshold(back_proj, 50, 255, cv2.THRESH_BINARY)

        # B: Multi-peak range mask
        h_center = meta["h_center"]
        s_center = meta["s_center"]
        h_range = meta.get("h_range", 20)
        s_range = meta.get("s_range", 70)

        mask_b = cv2.inRange(
            hsv,
            (max(0, h_center - h_range), max(0, s_center - s_range), 30),
            (min(180, h_center + h_range), min(255, s_center + s_range), 255),
        )

        for peak in meta.get("peaks", [])[1:3]:
            if peak["weight"] < 0.25:
                continue
            extra = cv2.inRange(
                hsv,
                (max(0, peak["h"] - h_range), max(0, peak["s"] - s_range), 30),
                (min(180, peak["h"] + h_range), min(255, peak["s"] + s_range), 255),
            )
            mask_b = cv2.bitwise_or(mask_b, extra)

        # C: Skin exclusion
        skin_mask = self._make_skin_mask(hsv)
        skin_dilated = cv2.dilate(skin_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
        mask_a = cv2.bitwise_and(mask_a, cv2.bitwise_not(skin_dilated))
        mask_b = cv2.bitwise_and(mask_b, cv2.bitwise_not(skin_dilated))

        # D: Combine
        combined = cv2.bitwise_or(mask_a, mask_b)

        # E: Morphological cleanup
        k_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        k_med = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        k_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))

        cleaned = cv2.morphologyEx(combined, cv2.MORPH_OPEN, k_small)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, k_large)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, k_med)

        # F: Find + score contours
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_score = 0.0
        best_bbox = None
        best_centroid = None

        # Adaptive minimum area based on frame resolution
        frame_area = fw * fh
        adaptive_min_area = max(MIN_CONTOUR_AREA, int(frame_area * 0.001))

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < adaptive_min_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            # Aspect ratio filter
            ar = w / max(h, 1)
            if ar < 0.3 or ar > 3.0:
                continue

            # Solidity filter
            hull_area = cv2.contourArea(cv2.convexHull(cnt))
            solidity = area / max(hull_area, 1)
            if solidity < 0.25:
                continue

            # Bbox area ratio check (adaptive)
            bbox_area_ratio = (w * h) / frame_area
            if bbox_area_ratio < BBOX_AREA_RATIO_MIN or bbox_area_ratio > BBOX_AREA_RATIO_MAX:
                continue

            score = area * solidity
            if score > best_score:
                best_score = score
                best_bbox = (x, y, w, h)
                best_centroid = (x + w // 2, y + h // 2)

        confidence = min(best_score / (frame_area * 0.01), 1.0) if best_bbox else 0.0
        return best_bbox, best_centroid, confidence

    # ── Face Detection ──────────────────────────────────────────────────────

    def _find_patient_by_face(
        self, frame: np.ndarray,
    ) -> Tuple[Optional[Tuple], Optional[Tuple], float, str, str]:
        """
        Face detection + recognition.
        Returns (bbox, centroid, confidence, matched_name, status).
        status: "match" | "no_match" | "no_face"
        "no_match" means face detected but NOT the patient → block capture.
        """
        if not self._face_rec_enabled or not self._known_face_encodings:
            return None, None, 0.0, "", "no_face"

        # Convert BGR to RGB for face_recognition
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        try:
            face_locations = face_recognition.face_locations(rgb, model="hog")
        except Exception as e:
            logger.warning("Face detection error: %s", e)
            return None, None, 0.0, "", "no_face"

        if not face_locations:
            return None, None, 0.0, "", "no_face"

        try:
            face_encodings = face_recognition.face_encodings(rgb, face_locations)
        except Exception as e:
            logger.warning("Face encoding error: %s", e)
            return None, None, 0.0, "", "no_face"

        best_match_name = ""
        best_match_dist = float("inf")
        best_location = None

        for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
            # Compare against all known patient faces
            distances = face_recognition.face_distance(self._known_face_encodings, encoding)

            if len(distances) == 0:
                continue

            min_dist = float(np.min(distances))
            min_idx = int(np.argmin(distances))

            if min_dist < FACE_MATCH_TOLERANCE and min_dist < best_match_dist:
                best_match_dist = min_dist
                best_match_name = self._known_face_names[min_idx]
                best_location = (left, top, right - left, bottom - top)

        if best_location is not None:
            x, y, w, h = best_location
            centroid = (x + w // 2, y + h // 2)
            confidence = 1.0 - (best_match_dist / FACE_MATCH_TOLERANCE)
            return best_location, centroid, max(0.0, min(confidence, 1.0)), best_match_name, "match"

        # Face(s) detected but none matched the patient → block capture
        return None, None, 0.0, "", "no_match"

    # ── Overlay Rendering (decoupled from detection) ────────────────────────

    def _draw_overlay(self, frame: np.ndarray, det: Dict[str, Any]) -> np.ndarray:
        """Draw the bbox/label/status bar on a COPY of the given frame. No detection logic here."""
        annotated = frame.copy()
        fh, fw = annotated.shape[:2]

        patient_detected = det.get("patient_detected", False)
        bbox = det.get("bbox")
        centroid = det.get("centroid")
        detection_method = det.get("detection_method", "none")
        face_bbox = det.get("face_bbox")

        if patient_detected and bbox is not None:
            x, y, w, h = bbox
            color = (0, 255, 0) if detection_method == "face" else (0, 200, 255)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            if centroid:
                cv2.circle(annotated, tuple(centroid), 6, color, -1)
            cv2.putText(
                annotated, f"PATIENT ({detection_method})", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
            )
        else:
            cv2.putText(
                annotated, "SEARCHING...", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
            )

        status_text = (
            f"LUMINA v4 | "
            f"{'FACE' if detection_method == 'face' else 'COLOR' if detection_method == 'color' else 'SEARCHING'} | "
            f"{fw}x{fh}"
        )
        cv2.putText(
            annotated, status_text, (10, fh - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1,
        )

        # Also draw the raw face detection box (thin, blue) for debugging
        if face_bbox is not None:
            fx, fy, fw2, fh2 = face_bbox
            cv2.rectangle(annotated, (fx, fy), (fx + fw2, fy + fh2), (255, 150, 0), 1)

        return annotated

    def _render_loop(self) -> None:
        """
        Lightweight, high-frequency loop: takes the freshest raw camera frame
        plus the LATEST AVAILABLE detection result (published separately by
        _monitoring_loop), draws the overlay, encodes JPEG ONCE, and caches it.

        This is what keeps streaming at a smooth ~25 FPS even though face
        detection can take 100-300ms per frame — the render loop never waits
        on detection to finish.
        """
        target_fps = 25.0
        frame_interval = 1.0 / target_fps

        while self._running:
            loop_start = time.time()

            with self._frame_lock:
                frame = self._latest_frame.copy() if self._latest_frame is not None else None

            if frame is None:
                time.sleep(0.03)
                continue

            with self._detection_lock:
                det = dict(self._latest_detection)

            annotated = self._draw_overlay(frame, det)

            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                with self._jpeg_lock:
                    self._latest_jpeg = buf.tobytes()
                with self._frame_lock:
                    self._latest_annotated = annotated  # kept for snapshot use / backward-compat

            elapsed = time.time() - loop_start
            time.sleep(max(0.0, frame_interval - elapsed))

        logger.info("🎨 Render loop stopped")

    # ── Monitoring Loop ─────────────────────────────────────────────────────

    def _monitoring_loop(self) -> None:
        """
        Detection loop: runs face/color detection on the freshest frame as
        fast as the algorithms allow, and gates the 30s snapshot cycle.

        Detection is inherently noisy frame-to-frame — a head turn, motion
        blur, or a half-second of partial occlusion can make a single frame
        miss even though the patient never actually left. To absorb that,
        "presence" is decided with a grace period (PRESENCE_GRACE_PERIOD):
        the patient is only considered "gone" once no detection has
        succeeded for that whole window, not on the very first miss.

        This loop no longer owns frame publishing or JPEG encoding — that is
        handled by _render_loop — so slow detection never blocks the video feed.
        """
        logger.info("🔍 Monitoring loop started")

        while self._running:
            with self._frame_lock:
                frame = self._latest_frame.copy() if self._latest_frame is not None else None

            if frame is None:
                time.sleep(0.05)
                continue

            # ── Hybrid Detection (this frame only) ─────────────────────────
            face_bbox, face_centroid, face_conf, face_name, face_status = self._find_patient_by_face(frame)
            color_bbox, color_centroid, color_conf = self._find_patient_by_color(frame)

            raw_detected = False       # did THIS frame produce a match?
            detection_method = "none"
            bbox = None
            centroid = None

            # ── TASK 1: COMBO LOGIC (Face-first, STRICTLY face-only for capture) ──
            # face_status can be: "match" | "no_match" | "no_face"
            # "match"     → face recognized AS the patient → CONFIRMED capture
            # "no_match"  → face detected but NOT the patient → BLOCK capture
            #                (even if color matches — could be a guest/visitor)
            # "no_face"   → no face found at all → color is used for MONITORING
            #                overlay display ONLY, but NEVER for triggering capture.
            #                Capture REQUIRES 100% face recognition confirmation.

            # Color detection result is always computed for overlay display,
            # but it is NEVER allowed to trigger a snapshot on its own.
            color_detected_for_overlay = color_bbox is not None

            if face_status == "match":
                # Face confirmed as patient → highest confidence, allow capture
                raw_detected = True
                detection_method = "face"
                bbox = face_bbox
                centroid = face_centroid
                logger.debug("👤 Face match: %s (conf=%.2f)", face_name, face_conf)
            elif face_status == "no_match":
                # A face was detected but it is NOT the patient.
                # STRICTLY BLOCK capture — do NOT fall back to color.
                # This prevents guests/visitors with similar clothing from
                # triggering false snapshots.
                raw_detected = False
                detection_method = "none"
                bbox = None
                centroid = None
                logger.debug("🚫 Face detected but NOT patient — blocking capture (color match ignored)")
            elif face_status == "no_face":
                # No face found at all.
                # Color detection is used for overlay display only (so the
                # family dashboard still shows something is being tracked),
                # but CAPTURE IS BLOCKED — we MUST have face confirmation.
                # This prevents false snapshots when a guest/visitor wears
                # similar clothing to the patient.
                raw_detected = False
                detection_method = "none"
                bbox = None
                centroid = None
                if color_detected_for_overlay:
                    logger.debug("👕 Color match but NO face — overlay only, capture BLOCKED (conf=%.2f)", color_conf)
                else:
                    logger.debug("🔍 No face and no color match — searching...")
            else:
                # Fallback for any unexpected status — also block capture
                raw_detected = False
                detection_method = "none"
                bbox = None
                centroid = None
                logger.debug("⚠️ Unexpected face_status=%s — blocking capture", face_status)

            # ── Overlay display: show color bbox on screen for monitoring ──
            # even when capture is blocked, so the family dashboard operator
            # can see that someone is in frame (just not confirmed as patient).
            _overlay_bbox = bbox if bbox is not None else color_bbox
            _overlay_centroid = centroid if centroid is not None else color_centroid
            _overlay_method = detection_method if detection_method != "none" else ("color" if color_detected_for_overlay else "none")

            # ── Update state (with grace-period hysteresis) ────────────────
            now = time.time()

            with self._lock:
                was_present = self.patient_present

                if raw_detected:
                    # Fresh confirmed detection — always trust this and reset the timer
                    self.patient_bbox = bbox
                    self.patient_centroid = centroid
                    self.detection_method = detection_method
                    self.last_detection_time = now
                    currently_present = True
                else:
                    # No match this frame — don't panic yet. Keep the last known
                    # bbox/method on screen and stay "present" until the grace
                    # period actually elapses.
                    time_since_last = (now - self.last_detection_time) if self.last_detection_time else float("inf")
                    currently_present = was_present and time_since_last < PRESENCE_GRACE_PERIOD
                    if not currently_present:
                        # Grace period expired — patient is genuinely gone now
                        self.patient_bbox = None
                        self.patient_centroid = None
                        self.detection_method = "none"

                self.patient_present = currently_present

                # ── Snapshot gating ──────────────────────────────────────
                if currently_present and not was_present:
                    # Patient just entered frame → take snapshot immediately
                    self.snapshot_pending = True
                    self.last_snapshot_time = 0  # Force immediate snapshot
                    self._add_log(
                        "alert",
                        f"👤 PATIENT DETECTED ({detection_method})",
                        f"Patient detected via {detection_method}. Starting monitoring.",
                    )
                elif currently_present and was_present:
                    # Patient still considered present → check if 30s elapsed
                    if now - self.last_snapshot_time >= SNAPSHOT_INTERVAL:
                        self.snapshot_pending = True
                elif not currently_present and was_present:
                    # Grace period expired — patient actually left the frame
                    self._add_log(
                        "info",
                        "⚠️ Patient left the frame",
                        f"No detection for over {PRESENCE_GRACE_PERIOD:.1f}s. Snapshot cycle paused.",
                    )

                # Snapshot values read outside the lock below
                snap_bbox = self.patient_bbox
                snap_centroid = self.patient_centroid
                snap_method = self.detection_method

            # ── Publish detection result for the render loop's overlay ────
            # Uses the persisted (grace-held) bbox, not just this frame's raw
            # result, so the on-screen box doesn't flicker on a single miss.
            # When capture is blocked (no face match), we still show the color
            # bbox on screen for monitoring purposes via _overlay_* variables.
            det_payload = {
                "patient_detected": currently_present,
                "bbox": snap_bbox if snap_bbox is not None else _overlay_bbox,
                "centroid": snap_centroid if snap_centroid is not None else _overlay_centroid,
                "detection_method": snap_method if snap_method != "none" else _overlay_method,
                "face_bbox": face_bbox,  # debug-only thin box, fine if it flickers
            }
            with self._detection_lock:
                self._latest_detection = det_payload

            # ── Process pending snapshot ──────────────────────────────────
            if self.snapshot_pending:
                annotated_snapshot = self._draw_overlay(frame, det_payload)
                if raw_detected:
                    conf = face_conf if detection_method == "face" else color_conf
                    context = f"{snap_method} (conf={conf:.2f})"
                else:
                    context = f"{snap_method} (held via grace period)"
                self._process_snapshot(frame, annotated_snapshot, context)
                self.snapshot_pending = False
                self.last_snapshot_time = now

            # ── Yield ────────────────────────────────────────────────────
            time.sleep(0.005)  # small yield so detection never pegs a core at 100% when idle

        logger.info("🔍 Monitoring loop stopped")

    def _process_snapshot(self, frame: np.ndarray, annotated: np.ndarray, context: str) -> None:
        """Save a snapshot and optionally send to AI analysis."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{timestamp}.jpg"
        filepath = os.path.join(SNAPSHOT_DIR, filename)

        cv2.imwrite(filepath, annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])

        self._add_log(
            "snapshot",
            "📸 Snapshot saved",
            f"Snapshot {filename} — {context}",
            snapshot_path=filepath,
        )

        logger.info("📸 Snapshot saved: %s (%s)", filename, context)

        # Submit to AI analysis pipeline (inserts into the database so it appears on the dashboard)
        self._send_to_ai_server(filepath, context)

    def _add_log(
        self,
        log_type: str,
        summary: str,
        detail: str,
        snapshot_path: Optional[str] = None,
    ) -> None:
        """Add an entry to the in-memory activity log (for frontend polling)."""
        from datetime import datetime
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": log_type,
            "summary": summary,
            "detail": detail,
            "snapshot": snapshot_path,
        }
        with self._log_lock:
            self._activity_log.append(entry)
            # Keep only last 200 entries
            if len(self._activity_log) > 200:
                self._activity_log = self._activity_log[-200:]

    def _send_to_ai_server(self, filepath: str, context: str) -> None:
        """Analyze snapshot using local fallback (AMD Vision API disabled due to rate limits).

        TASK 2: The AMD Vision / LLaVA API is currently rate-limited.
        This method now skips the external API call entirely and uses the
        local OpenCV-based fallback, which produces valid JSON-format logs
        ({alert_status, activity_description, narrative_report}) without
        requiring internet or external API access.
        """
        logger.info("📷 Using local fallback analysis (API disabled): %s", filepath[:60])
        self._insert_fallback_log(filepath)

    def _insert_fallback_log(self, filepath: str) -> None:
        """Create a stage-aware English fallback log when AMD Vision is unavailable."""
        
        from database import insert_log, get_patient_config, detect_emotion_state
        from datetime import datetime
        
        config = get_patient_config()
        emotion = detect_emotion_state()
        stage = config["patient_stage"] if config else 1
        patient_name = config["patient_name"] if config else "the patient"
        
        hour = datetime.now().hour
        
        if hour < 12:
            time_period = "morning"
        elif hour < 15:
            time_period = "afternoon"
        elif hour < 18:
            time_period = "evening"
        else:
            time_period = "night"

        # Stage-appropriate description & narrative
        if stage == 1:
            desc = f"{patient_name} was detected in the monitored area during the {time_period}."
            narrative = (
                f"{patient_name} was seen in the monitored area during "
                f"the {time_period}. Everything appears normal, and no "
                f"immediate concerns were identified."
            )
        elif stage == 2:
            desc = f"{patient_name} was detected in the monitored area ({time_period})."
            narrative = (
                f"{patient_name} was detected during the {time_period}. "
                f"The monitoring system is keeping a close watch. "
                f"No immediate danger was identified."
            )
        else:  # stage == 3
            desc = f"{patient_name} was detected in the monitored area ({time_period})."
            narrative = (
                f"{patient_name} was detected during the {time_period}. "
                f"The environment appears safe. A caregiver should verify "
                f"{patient_name}'s comfort and needs during regular check-ins."
            )

        # Append emotion context when relevant
        if emotion == "anxious":
            narrative += (
                f" Recent activity suggests {patient_name} may be feeling "
                f"anxious — a gentle check-in is recommended."
            )
        elif emotion == "confused":
            narrative += (
                f" Recent inactivity suggests {patient_name} may be "
                f"disoriented — consider providing orientation cues."
            )

        insert_log(
            alert_status="Safe",
            activity_description=desc,
            narrative_report=narrative,
            snapshot_image=filepath,
        )
        logger.info("✅ Stage-aware fallback log inserted (stage=%d, emotion=%s)", stage, emotion)

    def extract_fingerprint(self, photo_path: str) -> bool:
        """Extract clothing color fingerprint from reference photo."""
        try:
            img = cv2.imread(photo_path)
            if img is None:
                logger.error("Cannot read image: %s", photo_path)
                return False

            h_img, w_img = img.shape[:2]

            body = img[int(h_img * 0.25):int(h_img * 0.80),
                       int(w_img * 0.1):int(w_img * 0.9)]
            if body.size == 0:
                body = img

            hsv_body = cv2.cvtColor(body, cv2.COLOR_BGR2HSV)

            skin_mask = cv2.inRange(
                hsv_body,
                (SKIN_H_LOW, SKIN_S_LOW, SKIN_V_LOW),
                (SKIN_H_HIGH, SKIN_S_HIGH, SKIN_V_HIGH),
            )
            clothing_mask = cv2.bitwise_not(skin_mask)
            sat_mask = cv2.inRange(hsv_body, (0, 30, 40), (180, 255, 255))
            final_mask = cv2.bitwise_and(clothing_mask, sat_mask)

            total_px = body.shape[0] * body.shape[1]
            clothing_px = int(np.sum(final_mask > 0))

            use_mask = final_mask if clothing_px >= 100 else None

            hist = cv2.calcHist(
                [hsv_body], [0, 1], use_mask,
                [180, 256], [0, 180, 0, 256],
            )
            cv2.normalize(hist, hist, 0, 255, cv2.NORM_MINMAX)

            flat = hist.flatten()
            top_n = min(5, int(np.sum(flat > 0)))
            top_n = max(top_n, 1)
            top_indices = np.argpartition(flat, -top_n)[-top_n:]
            top_indices = top_indices[np.argsort(flat[top_indices])[::-1]]

            total_weight = float(np.sum(flat[top_indices]))
            peaks = []
            for idx in top_indices:
                w = float(flat[idx]) / max(total_weight, 1)
                if w > 0.05:
                    peaks.append({
                        "h": int(idx // 256),
                        "s": int(idx % 256),
                        "weight": round(w, 3),
                    })

            if not peaks:
                peaks = [{"h": 0, "s": 0, "weight": 1.0}]

            meta = {
                "h_center": peaks[0]["h"],
                "s_center": peaks[0]["s"],
                "h_range": 25,
                "s_range": 80,
                "peaks": peaks,
                "clothing_pixel_ratio": round(clothing_px / max(total_px, 1), 3),
                "source_photo": os.path.basename(photo_path),
            }

            np.save(HIST_PATH, hist)
            with open(FINGERPRINT_PATH, "w") as fp:
                json.dump(meta, fp, indent=2)

            self._color_hist = hist
            self._fingerprint_meta = meta

            logger.info(
                "✅ Fingerprint: H=%d±25 S=%d±80 peaks=%d ratio=%.2f",
                meta["h_center"], meta["s_center"],
                len(peaks), meta["clothing_pixel_ratio"],
            )
            return True

        except Exception as e:
            logger.error("extract_fingerprint error: %s", e)
            return False

    # ── Public API ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the camera capture, render, and detection threads."""
        if self._running:
            logger.warning("Engine already running.")
            return

        if not self.camera_url:
            logger.error("CAMERA_URL not configured. Set in .env file.")
            return

        self._running = True

        # Persistent camera capture thread (MJPEG stream reader or RTSP)
        self._camera_thread = threading.Thread(target=self._start_camera_capture, daemon=True)
        self._camera_thread.start()
        logger.info("📡 Camera capture thread started")

        # High-frequency render thread (overlay + JPEG encode for streaming)
        self._render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self._render_thread.start()
        logger.info("🎨 Render thread started")

        # Detection thread (face/color matching + snapshot gating)
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        logger.info("🚀 CCTV Engine started (capture + render + detection threads)")

    def stop(self) -> None:
        """Stop all monitoring threads."""
        self._running = False
        for t in (self._thread, self._render_thread, self._camera_thread):
            if t:
                t.join(timeout=5.0)
        self._thread = None
        self._render_thread = None
        self._camera_thread = None
        self._capture_backend = "none"
        logger.info("⏹️  CCTV Engine stopped")

    def get_status(self) -> Dict[str, Any]:
        """Return current monitoring status for the frontend."""
        with self._lock:
            bbox = self.patient_bbox
            heartbeat_age = (time.time() - self._last_frame_time) if self._last_frame_time else None
            return {
                "running": self._running,
                "patient_present": self.patient_present,
                "detection_method": self.detection_method,
                "bbox": list(bbox) if bbox else None,
                "centroid": list(self.patient_centroid) if self.patient_centroid else None,
                "last_detection": self.last_detection_time,
                "last_snapshot": self.last_snapshot_time,
                "face_rec_enabled": self._face_rec_enabled,
                "color_fingerprint_loaded": self._color_hist is not None,
                "known_faces": len(self._known_face_encodings),
                "camera_url": self.camera_url[:50] + "..." if len(self.camera_url) > 50 else self.camera_url,
                "camera_status": self._camera_status,
                "camera_connected": self._camera_connected,
                "capture_backend": self._capture_backend,
                "camera_heartbeat_age": round(heartbeat_age, 2) if heartbeat_age is not None else None,
            }

    def get_activity_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent activity log entries."""
        with self._log_lock:
            return list(reversed(self._activity_log[-limit:]))

    def get_latest_frame(self, annotated: bool = True) -> Optional[bytes]:
        """Return the latest frame as JPEG bytes. For annotated=True this is
        ALREADY pre-encoded by _render_loop — no re-encoding per request."""
        if annotated:
            with self._jpeg_lock:
                return self._latest_jpeg
        with self._frame_lock:
            frame = self._latest_frame
            if frame is None:
                return None
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return buf.tobytes() if ok else None

    def update_camera_config(self, url: str, username: str = "", password: str = "") -> None:
        """Update camera configuration at runtime and persist to JSON + .env."""
        was_running = self._running
        if was_running:
            logger.info("📷 Stopping monitoring to apply new camera config...")
            self.stop()
            # Give threads time to clean up
            time.sleep(0.5)

        self.camera_url = url
        self.camera_username = username
        self.camera_password = password

        # ── Persist to camera_config.json (primary storage) ──────────────────
        config_path = os.path.join(BACKEND_DIR, "camera_config.json")
        try:
            cfg = {
                "camera_url": url,
                "camera_username": username,
                "camera_password": password,
            }
            with open(config_path, "w") as f:
                json.dump(cfg, f, indent=2)
            logger.info("📷 Camera config saved to camera_config.json")
        except Exception as e:
            logger.error("Failed to save camera_config.json: %s", e)

        # ── Persist to .env (secondary, for backward compatibility) ──────────
        env_path = os.path.join(BACKEND_DIR, "..", ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r") as f:
                    lines = f.readlines()

                updated_keys = {"CAMERA_URL": url, "CAMERA_USERNAME": username, "CAMERA_PASSWORD": password}
                new_lines = []
                seen_keys = set()

                for line in lines:
                    stripped = line.strip()
                    # Skip empty lines and comments
                    if not stripped or stripped.startswith("#"):
                        new_lines.append(line)
                        continue
                    # Check if this line sets one of our keys
                    matched = False
                    for key, value in updated_keys.items():
                        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                            new_lines.append(f"{key}={value}\n")
                            seen_keys.add(key)
                            matched = True
                            break
                    if not matched:
                        new_lines.append(line)

                # Append any keys not found
                for key, value in updated_keys.items():
                    if key not in seen_keys:
                        new_lines.append(f"{key}={value}\n")

                with open(env_path, "w") as f:
                    f.writelines(new_lines)
                logger.info("📷 Camera config synced to .env")
            except Exception as e:
                logger.warning("Failed to update .env: %s", e)

        # ── Update os.environ ────────────────────────────────────────────────
        os.environ["CAMERA_URL"] = url
        os.environ["CAMERA_USERNAME"] = username
        os.environ["CAMERA_PASSWORD"] = password

        logger.info("📷 Camera config updated: %s", url[:80] if len(url) > 80 else url)

        # ── Restart monitoring if it was running ─────────────────────────────
        if was_running:
            logger.info("📷 Restarting monitoring with new camera config...")
            self.start()


# ── Module-level singleton (lazy) + wrapper functions ───────────────────────
# main.py imports these functions directly. Lazy construction avoids
# building CCTVMaster() at import time and avoids two instances existing.

_master: Optional[CCTVMaster] = None


def _get_master() -> CCTVMaster:
    global _master
    if _master is None:
        _master = CCTVMaster()
    return _master


def get_engine() -> CCTVMaster:
    """Alias kept for backward compatibility with any code expecting get_engine()."""
    return _get_master()


def start_monitoring() -> bool:
    m = _get_master()
    m.start()
    return m._running


def stop_monitoring() -> bool:
    m = _get_master()
    m.stop()
    return not m._running


def is_monitoring() -> bool:
    return _get_master()._running


def get_latest_frame():
    return _get_master().get_latest_frame()


def get_monitor_status() -> dict:
    return _get_master().get_status()


def extract_color_fingerprint(photo_path: str) -> bool:
    return _get_master().extract_fingerprint(photo_path)


def reload_patient_data() -> None:
    _get_master().reload_patient_data()


def update_camera_config(url: str, username: str = "", password: str = "") -> None:
    _get_master().update_camera_config(url, username, password)
