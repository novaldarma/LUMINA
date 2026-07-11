import sys
import os
import sqlite3
import time
from datetime import datetime

# Tambahkan folder backend ke Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import camera_sensor
import ai_agent

# Path absolut ke database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "backend", "lumina_core.db")
def run_lumina_cycle():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n--- Siklus Monitoring: {timestamp} ---")

    # 1. Ambil foto dari kamera
    image_file = camera_sensor.capture_image()
    if not image_file:
        print("⚠️ Kamera tidak tersedia, skip siklus ini.")
        return

    # 2. Kirim gambar nyata ke Vision AI
    analysis_result = ai_agent.analyze_frame(image_file, timestamp)

    print(f"Status   : {analysis_result.get('alert_status', '-')}")
    print(f"Aktivitas: {analysis_result.get('activity_description', '-')}")

    # 3. Simpan ke database
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO daily_logs
            (timestamp, alert_status, activity_description, narrative_report, snapshot_image)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            timestamp,
            analysis_result.get('alert_status', 'Tidak Diketahui'),
            analysis_result.get('activity_description', ''),
            analysis_result.get('narrative_report', ''),
            image_file
        ))
        conn.commit()
        conn.close()
        print("✅ Data tersimpan ke database.")
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    print("🚀 LUMINA Vision System Aktif — Interval 30 detik")
    print(f"📂 Database: {DB_PATH}")
    while True:
        run_lumina_cycle()
        time.sleep(30)