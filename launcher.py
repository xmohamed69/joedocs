# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.

# launcher.py  — place this in the project root next to manage.py

import os
import sys
import time
import subprocess
import urllib.request
from pathlib import Path

# ── Resolve base directory ────────────────────────────────────────────────────
IS_FROZEN = getattr(sys, 'frozen', False)
BASE_DIR   = Path(sys._MEIPASS) if IS_FROZEN else Path(__file__).resolve().parent

# ── Django environment ────────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'joedocs.settings')

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DJANGO_PORT = 8000
DJANGO_HOST = f"http://127.0.0.1:{DJANGO_PORT}"
MANAGE_PY   = BASE_DIR / "manage.py"

# ── Python executable ─────────────────────────────────────────────────────────
# When frozen, sys.executable is the .exe itself — useless for running manage.py.
# We need the real Python from the venv.
# The exe lives in dist/, project root is one level up, venv is alongside it.
if IS_FROZEN:
    EXE_DIR      = Path(sys.executable).parent          # dist/
    PROJECT_ROOT = EXE_DIR.parent                        # joedocs/
    PYTHON_EXE   = PROJECT_ROOT / 'venv312' / 'Scripts' / 'python.exe'
    if not PYTHON_EXE.exists():
        # Fallback: try the directory the exe was launched from
        PYTHON_EXE = EXE_DIR / 'python.exe'
else:
    PYTHON_EXE   = Path(sys.executable)
    PROJECT_ROOT = BASE_DIR

_django_process = None

# ── Log file ──────────────────────────────────────────────────────────────────
LOG_PATH = Path(sys.executable).parent / "joedocs_startup.log"


def _log(msg: str):
    print(msg)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def is_server_ready(timeout=1) -> bool:
    try:
        urllib.request.urlopen(DJANGO_HOST, timeout=timeout)
        return True
    except Exception:
        return False


def start_django() -> subprocess.Popen:
    global _django_process

    try:
        LOG_PATH.write_text("", encoding="utf-8")
    except Exception:
        pass

    _log(f"[launcher] BASE_DIR    = {BASE_DIR}")
    _log(f"[launcher] MANAGE_PY   = {MANAGE_PY}")
    _log(f"[launcher] exists      = {MANAGE_PY.exists()}")
    _log(f"[launcher] PYTHON_EXE  = {PYTHON_EXE}")
    _log(f"[launcher] py exists   = {PYTHON_EXE.exists()}")
    _log(f"[launcher] sys.path    = {sys.path}")
    _log("[launcher] Starting Django server...")

    log_fh = open(LOG_PATH, "a", encoding="utf-8")

    env = os.environ.copy()
    env['DJANGO_SETTINGS_MODULE'] = 'joedocs.settings'

    _django_process = subprocess.Popen(
        [str(PYTHON_EXE), str(MANAGE_PY), "runserver",
         f"127.0.0.1:{DJANGO_PORT}", "--noreload"],
        cwd=str(BASE_DIR),
        env=env,
        stdout=log_fh,
        stderr=log_fh,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return _django_process


def wait_for_django(timeout=30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_server_ready():
            _log("[launcher] Django is ready.")
            return True
        if _django_process and _django_process.poll() is not None:
            _log(f"[launcher] Django exited early, code={_django_process.returncode}")
            return False
        time.sleep(0.4)
    _log("[launcher] Django did not start in time.")
    return False


def stop_django():
    global _django_process
    if _django_process and _django_process.poll() is None:
        _log("[launcher] Stopping Django server...")
        _django_process.terminate()
        try:
            _django_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _django_process.kill()


def _error_html(log_text: str) -> str:
    safe = log_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#fef2f2;padding:2rem}}
h2{{color:#dc2626;margin-bottom:1rem}}
p{{color:#374151;margin-bottom:1rem;font-size:.9rem}}
pre{{background:#1e1e1e;color:#f8f8f2;padding:1rem;border-radius:8px;
     font-size:.75rem;overflow:auto;max-height:60vh;white-space:pre-wrap;word-break:break-all}}
</style></head><body>
<h2>&#10060; Failed to start server</h2>
<p>Log file: {LOG_PATH}</p>
<pre>{safe or "(log empty — check paths above)"}</pre>
</body></html>"""


def main():
    if not is_server_ready(timeout=1):
        start_django()
        if not wait_for_django(timeout=30):
            try:
                log_text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
            except Exception:
                log_text = ""
            _log("[launcher] Showing error window.")
            import webview
            webview.create_window(
                "JoeLink AI - Startup Error",
                html=_error_html(log_text),
                width=900, height=600,
            )
            webview.start(gui="edgechromium")
            return
    else:
        _log("[launcher] Django already running, skipping start.")

    from client.main import main as client_main
    try:
        client_main()
    finally:
        stop_django()


if __name__ == "__main__":
    main()