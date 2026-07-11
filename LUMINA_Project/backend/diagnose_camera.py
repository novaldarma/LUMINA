"""
LUMINA — Camera Diagnostic Tool
Tests multiple snapshot URL patterns and auth methods.
Run: python backend/diagnose_camera.py
"""
import requests
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

CAMERA_BASE   = "http://192.68.1.6:8080"
USERNAME      = os.getenv("CAMERA_USERNAME", "HOME")
PASSWORD      = os.getenv("CAMERA_PASSWORD", "")

# All known snapshot paths for various IP camera brands
SNAPSHOT_PATHS = [
    "/shot.jpg",
    "/snapshot.jpg",
    "/snap.jpg",
    "/SnapshotJPEG",
    "/tmpfs/auto.jpg",
    "/webcapture.jpg",
    "/image.jpg",
    "/capture.jpg",
    "/still.jpg",
    "/photo.jpg",
    "/cgi-bin/snapshot.cgi?chn=0",
    "/cgi-bin/snapshot.cgi?chn=1",
    "/cgi-bin/snapshot.cgi",
    "/goform/video",
    "/onvif-http/snapshot",
    "/jpg/image.jpg",
    "/snapshot.cgi",
    "/img/snapshot.cgi",
    "/cgi-bin/camera",
    "/cgi-bin/video.jpg",
    "/Streaming/channels/1/picture",
    "/ISAPI/Streaming/channels/1/picture",
    "/snapshot.jpeg",
]


def test_url(url: str, use_auth: bool = True) -> tuple[int, int]:
    """Test a URL with multiple auth methods. Returns (status_code, content_length)."""
    session = requests.Session()

    # Method 1: No auth
    try:
        r = session.get(url, timeout=5)
        if r.status_code == 200 and len(r.content) > 1000:
            return (200, len(r.content))
    except Exception:
        pass

    # Method 2: Basic auth
    if use_auth:
        try:
            r = session.get(url, auth=(USERNAME, PASSWORD), timeout=5)
            if r.status_code == 200 and len(r.content) > 1000:
                return (200, len(r.content))
        except Exception:
            pass

    # Method 3: Digest auth
    if use_auth:
        try:
            r = session.get(
                url,
                auth=requests.auth.HTTPDigestAuth(USERNAME, PASSWORD),
                timeout=5,
            )
            if r.status_code == 200 and len(r.content) > 1000:
                return (200, len(r.content))
        except Exception:
            pass

    # Method 4: URL-embedded credentials
    if use_auth:
        try:
            proto, rest = url.split("://", 1)
            host_path = rest.split("/", 1)
            host = host_path[0]
            path = "/" + host_path[1] if len(host_path) > 1 else "/"
            embedded = f"{proto}://{USERNAME}:{PASSWORD}@{host}{path}"
            r = session.get(embedded, timeout=5)
            if r.status_code == 200 and len(r.content) > 1000:
                return (200, len(r.content))
        except Exception:
            pass

    # Method 5: Session login + cookie
    if use_auth:
        try:
            sess = requests.Session()
            # Try common login endpoints
            for login_path in [
                "/login.cgi",
                "/cgi-bin/api.cgi?cmd=Login",
                "/goform/login",
                "/api/login",
            ]:
                try:
                    sess.post(
                        f"{CAMERA_BASE}{login_path}",
                        data={"username": USERNAME, "password": PASSWORD, "user": USERNAME, "pwd": PASSWORD},
                        timeout=5,
                    )
                except Exception:
                    continue
            r = sess.get(url, timeout=5)
            if r.status_code == 200 and len(r.content) > 1000:
                return (200, len(r.content))
        except Exception:
            pass

    # Just return last known status
    try:
        r = session.get(url, timeout=5)
        return (r.status_code, len(r.content))
    except Exception as e:
        return (0, 0)


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║    LUMINA — Camera Snapshot URL Diagnostic       ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║ Camera Base : {CAMERA_BASE:<35s} ║")
    print(f"║ Username    : {USERNAME:<35s} ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    # First: test if camera is reachable at all
    print("[1/3] Testing camera reachability...")
    try:
        r = requests.get(CAMERA_BASE, timeout=5)
        print(f"      ✓ Camera reachable (HTTP {r.status_code}, {len(r.content)} bytes)")
    except Exception as e:
        print(f"      ✗ Camera NOT reachable: {e}")
        return

    # Second: try all snapshot paths
    print("\n[2/3] Scanning snapshot URLs (looking for JPEG images > 1KB)...")
    found = []
    for path in SNAPSHOT_PATHS:
        url = f"{CAMERA_BASE}{path}"
        status, size = test_url(url, use_auth=True)
        if status == 200 and size > 1000:
            found.append((url, size))
            print(f"      ✓ HIT!  {url}  →  {size} bytes")
        elif status == 200:
            print(f"      · 200 but small ({size}B): {url}")
        elif status in (401, 403):
            print(f"      · Auth required ({status}): {url}")
        elif status == 0:
            print(f"      ✗ No response: {url}")
        else:
            print(f"      · HTTP {status}: {url}")

    # Third: try session-based approach with web form
    print("\n[3/3] Trying session-based login + snapshot...")
    try:
        sess = requests.Session()

        # First, access the main page to get any cookies
        r = sess.get(CAMERA_BASE, timeout=5)
        print(f"      GET / → {r.status_code}, cookies: {dict(sess.cookies)}")

        # Try to find the login form action
        import re
        form_action = None
        for match in re.finditer(r'action=["\']([^"\']*)["\']', r.text):
            action = match.group(1)
            if 'login' in action.lower():
                form_action = action
                print(f"      Found login form action: {form_action}")
                break

        if form_action:
            login_url = form_action if form_action.startswith("http") else f"{CAMERA_BASE}{form_action if form_action.startswith('/') else '/' + form_action}"
        else:
            login_url = f"{CAMERA_BASE}/login.cgi"

        # Attempt login
        login_data = {
            "username": USERNAME,
            "password": PASSWORD,
            "user": USERNAME,
            "pwd": PASSWORD,
            "usr": USERNAME,
            "pass": PASSWORD,
        }
        r = sess.post(login_url, data=login_data, timeout=5, allow_redirects=True)
        print(f"      POST login → {r.status_code}, cookies: {dict(sess.cookies)}")

        # Now try snapshot URLs with the session
        for path in ["/shot.jpg", "/snapshot.jpg", "/tmpfs/auto.jpg", "/cgi-bin/snapshot.cgi?chn=0"]:
            url = f"{CAMERA_BASE}{path}"
            try:
                r = sess.get(url, timeout=5)
                if r.status_code == 200 and len(r.content) > 1000:
                    found.append((f"{url} [session]", len(r.content)))
                    print(f"      ✓ SESSION HIT!  {url}  →  {len(r.content)} bytes")
                else:
                    content_type = r.headers.get("Content-Type", "?")
                    print(f"      · {url} → {r.status_code} ({content_type}), {len(r.content)}B")
            except Exception as e:
                print(f"      ✗ {url} → {e}")

    except Exception as e:
        print(f"      ✗ Session approach failed: {e}")

    # Summary
    print("\n" + "═" * 54)
    if found:
        print("✅ WORKING SNAPSHOT URLS:")
        for url, size in found:
            print(f"   {url}  ({size} bytes)")
        print(f"\n👉 Update CAMERA_URL in .env with one of these URLs!")
    else:
        print("❌ NO working snapshot URLs found.")
        print("   Suggestions:")
        print("   1. Login to camera web interface (http://192.68.1.6:8080)")
        print("   2. Find the 'Snapshot' or 'Capture' button")
        print("   3. Right-click the image → 'Open image in new tab'")
        print("   4. Copy that URL and paste it below:")
        custom = input("\n   Snapshot URL: ").strip()
        if custom:
            print(f"   → Run: echo 'CAMERA_URL={custom}' >> .env.test")

    print("═" * 54)


if __name__ == "__main__":
    main()
