"""
LUMINA Vision Node — Color Tracking Diagnostic Tool (v3)
=========================================================
Tests clothing-color-based patient detection using webcam.
Shows back-projection, range mask, skin exclusion, combined,
and contour scoring in real-time.

Usage:
    cd backend
    python test_match.py

Controls:
    q  = quit
    1  = toggle back-projection mask
    2  = toggle range mask
    3  = toggle combined + cleaned mask
    4  = toggle skin exclusion mask
    5  = toggle all masks
"""

import os
import sys
import json
from pathlib import Path

import cv2
import numpy as np

# ── Paths ───────────────────────────────────────────────────────────────────
PATIENT_PHOTO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patient_photos")
MIN_CONTOUR_AREA = 5000

# ── Skin Color Range (HSV) ─────────────────────────────────────────────────
SKIN_H_LOW  = 0
SKIN_H_HIGH = 30
SKIN_S_LOW  = 10
SKIN_S_HIGH = 170
SKIN_V_LOW  = 50
SKIN_V_HIGH = 255


def make_skin_mask(hsv):
    return cv2.inRange(
        hsv,
        (SKIN_H_LOW, SKIN_S_LOW, SKIN_V_LOW),
        (SKIN_H_HIGH, SKIN_S_HIGH, SKIN_V_HIGH),
    )


def load_fingerprint():
    hist_path = os.path.join(PATIENT_PHOTO_DIR, "color_hist.npy")
    fp_path = os.path.join(PATIENT_PHOTO_DIR, "color_fingerprint.json")

    if not os.path.exists(hist_path) or not os.path.exists(fp_path):
        return None, None

    try:
        hist = np.load(hist_path)
        with open(fp_path, "r") as f:
            meta = json.load(f)
        return hist, meta
    except Exception as e:
        print(f"Error loading fingerprint: {e}")
        return None, None


def find_patient(frame, hist, meta):
    """
    Precision color-based patient detection.
    Returns (bbox, centroid, masks_dict).
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    fh, fw = frame.shape[:2]

    # ── A: Histogram back-projection ──
    back_proj = cv2.calcBackProject([hsv], [0, 1], hist, [0, 180, 0, 256], 1)
    _, mask_a = cv2.threshold(back_proj, 50, 255, cv2.THRESH_BINARY)

    # ── B: Multi-peak range mask ──
    h_center = meta["h_center"]
    s_center = meta["s_center"]
    h_range = meta.get("h_range", 20)
    s_range = meta.get("s_range", 70)

    h_low = max(0, h_center - h_range)
    h_high = min(180, h_center + h_range)
    s_low = max(0, s_center - s_range)
    s_high = min(255, s_center + s_range)
    mask_b = cv2.inRange(hsv, (h_low, s_low, 30), (h_high, s_high, 255))

    for peak in meta.get("peaks", [])[1:3]:
        if peak["weight"] < 0.25:
            continue
        extra = cv2.inRange(
            hsv,
            (max(0, peak["h"] - h_range), max(0, peak["s"] - s_range), 30),
            (min(180, peak["h"] + h_range), min(255, peak["s"] + s_range), 255),
        )
        mask_b = cv2.bitwise_or(mask_b, extra)

    # ── C: Skin exclusion ──
    skin_mask = make_skin_mask(hsv)
    skin_dilated = cv2.dilate(skin_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    mask_a = cv2.bitwise_and(mask_a, cv2.bitwise_not(skin_dilated))
    mask_b = cv2.bitwise_and(mask_b, cv2.bitwise_not(skin_dilated))

    # ── Combine ──
    combined = cv2.bitwise_or(mask_a, mask_b)

    # ── D: Morphological cleanup ──
    k_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    k_med = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    k_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))

    cleaned = cv2.morphologyEx(combined, cv2.MORPH_OPEN, k_small)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, k_large)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, k_med)

    # ── E & F: Find + score contours ──
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None, None, {
            "backproj": mask_a, "range": mask_b, "skin": skin_dilated,
            "combined": combined, "cleaned": cleaned,
        }

    best_score = 0.0
    best_bbox = None
    best_centroid = None

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_CONTOUR_AREA:
            continue

        x, y, w, h = cv2.boundingRect(cnt)

        # Aspect ratio filter
        ar = w / max(h, 1)
        if ar < 0.35 or ar > 2.9:
            continue

        # Solidity filter
        hull_area = cv2.contourArea(cv2.convexHull(cnt))
        solidity = area / max(hull_area, 1)
        if solidity < 0.28:
            continue

        # Position sanity
        if (w * h) / (fw * fh) < 0.015:
            continue

        score = area * solidity
        if score > best_score:
            best_score = score
            best_bbox = (x, y, w, h)
            best_centroid = (x + w // 2, y + h // 2)

    return best_bbox, best_centroid, {
        "backproj": mask_a, "range": mask_b, "skin": skin_dilated,
        "combined": combined, "cleaned": cleaned,
    }


def main():
    print("=" * 60)
    print("  LUMINA — Color Tracking Diagnostic Tool (v3)")
    print("=" * 60)

    hist, meta = load_fingerprint()
    if hist is None:
        print("\n❌ TIDAK ADA COLOR FINGERPRINT!")
        print("   Upload foto full-body pasien dulu via web UI.\n")
        sys.exit(1)

    print(f"\n✅ Fingerprint:")
    print(f"   H_center = {meta['h_center']}  (±{meta.get('h_range','?')})")
    print(f"   S_center = {meta['s_center']}  (±{meta.get('s_range','?')})")
    print(f"   Peaks    = {len(meta.get('peaks',[]))} ditemukan")
    for i, p in enumerate(meta.get("peaks", [])):
        print(f"     #{i+1}: H={p['h']} S={p['s']} (w={p['weight']:.2f})")
    print(f"   Clothing ratio = {meta.get('clothing_pixel_ratio','?')}")
    print(f"   Sumber         = {meta.get('source_photo', 'unknown')}")
    print(f"\n   q=quit  1=backproj  2=range  3=combined  4=skin  5=all")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Tidak bisa membuka webcam!")
        sys.exit(1)

    # Set webcam resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    show_backproj = False
    show_range = False
    show_combined = False
    show_skin = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        bbox, centroid, masks = find_patient(frame, hist, meta)
        display = frame.copy()

        if bbox is not None:
            x, y, w, h = bbox
            cx, cy = centroid
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.circle(display, (cx, cy), 6, (0, 255, 0), -1)
            cv2.putText(display, f"PASIEN (AR={w/max(h,1):.2f})",
                        (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            cv2.putText(display, "MENCARI...",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # Status bar
        cv2.putText(display, "LUMINA v3 | q=quit 1=backproj 2=range 3=combined 4=skin 5=all",
                    (10, display.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        cv2.imshow("LUMINA — Color Tracking", display)

        if show_backproj:
            cv2.imshow("A: Back-Projection (after skin removal)", masks["backproj"])
        if show_range:
            cv2.imshow("B: Range Mask (after skin removal)", masks["range"])
        if show_combined:
            cv2.imshow("Combined", masks["combined"])
            cv2.imshow("Cleaned (Open+Close+Open)", masks["cleaned"])
        if show_skin:
            cv2.imshow("Skin Exclusion Mask", masks["skin"])

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("1"):
            show_backproj = not show_backproj
            if not show_backproj:
                cv2.destroyWindow("A: Back-Projection (after skin removal)")
        elif key == ord("2"):
            show_range = not show_range
            if not show_range:
                cv2.destroyWindow("B: Range Mask (after skin removal)")
        elif key == ord("3"):
            show_combined = not show_combined
            if not show_combined:
                cv2.destroyWindow("Combined")
                cv2.destroyWindow("Cleaned (Open+Close+Open)")
        elif key == ord("4"):
            show_skin = not show_skin
            if not show_skin:
                cv2.destroyWindow("Skin Exclusion Mask")
        elif key == ord("5"):
            show_backproj = not show_backproj
            show_range = not show_range
            show_combined = not show_combined
            show_skin = not show_skin
            if not show_backproj:
                cv2.destroyWindow("A: Back-Projection (after skin removal)")
                cv2.destroyWindow("B: Range Mask (after skin removal)")
                cv2.destroyWindow("Combined")
                cv2.destroyWindow("Cleaned (Open+Close+Open)")
                cv2.destroyWindow("Skin Exclusion Mask")

    cap.release()
    cv2.destroyAllWindows()
    print("\nSelesai.\n")


if __name__ == "__main__":
    main()