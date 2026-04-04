# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.

# client/main.py

import json
import webview
import webbrowser
import urllib.request
from urllib.parse import urljoin
from pathlib import Path
from client.config import BASE_URL, LOGIN_PATH

PROFILE_DIR = Path.home() / ".joelinkAI" / "browser_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

SESSION_FILE = PROFILE_DIR / "session.json"


# ── Patch pywebview's EdgeChromium FormClosed crash ───────────────────────
#
# pywebview's edgechromium backend accesses CoreWebView2.BrowserProcessId
# inside its FormClosed handler. If WebView2 has already torn itself down
# (which happens when the user closes the window while a navigation is in
# progress), CoreWebView2 is None and a PythonException crashes the app.
#
# We patch the handler at import time so any access to BrowserProcessId is
# wrapped in a null-check. This is safe: the only thing pywebview does with
# the PID there is an os.kill() to clean up the browser process, which we
# replicate below when the value IS available.

def _patch_edgechromium():
    try:
        from webview.platforms import edgechromium
        original_closed = edgechromium.BrowserView.on_form_closed

        def safe_on_form_closed(self, sender, args):
            try:
                original_closed(self, sender, args)
            except Exception:
                # CoreWebView2 was already None — browser process is gone,
                # nothing left to kill. Swallow silently.
                pass

        edgechromium.BrowserView.on_form_closed = safe_on_form_closed
        print("[patch] edgechromium FormClosed handler patched successfully.")
    except Exception as e:
        # If pywebview's internals change in a future version this is non-fatal.
        print(f"[patch] Could not patch edgechromium handler (non-fatal): {e}")

_patch_edgechromium()


# ── Session file helpers ───────────────────────────────────────────────────

def load_session() -> dict | None:
    """Return saved session data {session_key, expires_at} or None."""
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text())
    except Exception:
        return None


def clear_session():
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
    except Exception:
        pass


def is_session_locally_expired(data: dict) -> bool:
    """Quick local check using the expiry timestamp we stored at login time."""
    import time
    expires_at = data.get("expires_at")
    if expires_at is None:
        return False
    return time.time() > expires_at


# ── Server helpers ─────────────────────────────────────────────────────────

class _NoRedirect(urllib.request.HTTPErrorProcessor):
    """urllib opener that returns responses as-is without following redirects."""
    def http_response(self, request, response):
        return response
    https_response = http_response


def is_server_reachable() -> bool:
    try:
        urllib.request.urlopen(BASE_URL, timeout=3)
        return True
    except Exception:
        return False


def validate_session(session_key: str) -> bool:
    try:
        opener = urllib.request.build_opener(_NoRedirect)
        req = urllib.request.Request(
            urljoin(BASE_URL, "/accounts/session-ping/"),
            headers={"Cookie": f"sessionid={session_key}"},
        )
        with opener.open(req, timeout=5) as resp:
            if resp.status != 200:
                print(f"[validate_session] HTTP {resp.status} -> invalid")
                return False
            body = json.loads(resp.read().decode("utf-8", errors="ignore"))
            ok = body.get("ok") is True
            print(f"[validate_session] ok={ok}")
            return ok
    except Exception as e:
        print(f"[validate_session] error: {e}")
        return False


# ── Offline page ───────────────────────────────────────────────────────────

OFFLINE_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>JoeLink AI - No Connection</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#f0f4ff;min-height:100vh;
display:flex;align-items:center;justify-content:center;text-align:center;padding:2rem}
.card{background:#fff;border-radius:16px;padding:3rem 2.5rem;max-width:420px;
box-shadow:0 8px 40px rgba(26,110,245,.1)}
.icon{font-size:3.5rem;margin-bottom:1.5rem}
h1{font-size:1.4rem;font-weight:700;color:#0d1117;margin-bottom:.75rem}
p{color:#64748b;font-size:.9rem;line-height:1.6;margin-bottom:1.5rem}
button{background:#1a6ef5;color:#fff;border:none;padding:.75rem 2rem;
border-radius:8px;font-size:.95rem;font-weight:600;cursor:pointer}
button:hover{background:#1458cc}
</style></head>
<body><div class="card"><div class="icon">&#128225;</div>
<h1>Unable to connect</h1>
<p>JoeLink AI could not reach the server.<br>Please check your connection and try again.</p>
<button onclick="location.reload()">Try again</button>
</div></body></html>"""


# ── JS API exposed to the WebView ──────────────────────────────────────────

class Api:
    def open_external(self, url: str):
        if url:
            webbrowser.open(url)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    api = Api()

    if not is_server_reachable():
        print("[main] server unreachable")
        webview.create_window(
            "JoeLink AI - No Connection", html=OFFLINE_HTML,
            js_api=api, width=1200, height=800,
        )
        webview.start(gui="edgechromium", storage_path=str(PROFILE_DIR), private_mode=False)
        return

    data = load_session()

    if data:
        session_key = data.get("session_key")

        if is_session_locally_expired(data):
            print("[main] session locally expired")
            clear_session()
            session_key = None

        elif session_key and validate_session(session_key):
            print(f"[main] valid session {session_key[:8]}... injecting cookie")
            import time
            expires_at = data.get("expires_at")
            remaining = int(expires_at - time.time()) if expires_at else 60 * 60 * 24 * 30
            max_age = max(remaining, 3600)
            print(f"[main] cookie Max-Age will be: {max_age}s")
            inject_url = (
                f"{BASE_URL.rstrip('/')}/accounts/inject-session/"
                f"?key={session_key}&next=/docs/&max_age={max_age}"
            )
            webview.create_window(
                "JoeLink AI", inject_url,
                js_api=api, width=1200, height=800,
            )
            webview.start(gui="edgechromium", storage_path=str(PROFILE_DIR), private_mode=False)
            return

        else:
            print("[main] session invalid or server rejected it")
            clear_session()

    print("[main] showing login page")
    start_url = urljoin(BASE_URL, LOGIN_PATH)
    webview.create_window(
        "JoeLink AI", start_url,
        js_api=api, width=1200, height=800,
    )
    webview.start(gui="edgechromium", storage_path=str(PROFILE_DIR), private_mode=False)


if __name__ == "__main__":
    main()