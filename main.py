"""
QuickPOS — Windows Desktop Launcher
Starts Flask, opens chromeless Edge/Chrome window, system tray icon.
"""

import os
import sys
import subprocess
import threading
import time
import webbrowser
from http.client import HTTPConnection

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)

from models import DATA_DIR
from app import app, PORT


def _find_browser():
    for exe in [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    ]:
        if os.path.isfile(exe):
            return exe
    return None


def _wait_for_server(host, port, timeout=8):
    for _ in range(timeout * 10):
        try:
            conn = HTTPConnection(host, port, timeout=1)
            conn.request("GET", "/")
            conn.getresponse().read()
            conn.close()
            return True
        except Exception:
            time.sleep(0.1)
    return False


def _open_app_window():
    url = f"http://localhost:{PORT}"
    browser = _find_browser()
    if browser:
        subprocess.Popen([browser, f"--app={url}", "--start-maximized"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        webbrowser.open(url)


def start_flask():
    app.run(host="localhost", port=PORT, debug=False, use_reloader=False)


def _run_tray():
    try:
        from PIL import Image, ImageDraw
        import pystray

        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle((8, 8, 55, 55), fill=(16, 185, 129, 255))
        draw.ellipse((20, 16, 43, 39), fill=(255, 255, 255, 255))
        draw.polygon([(24, 44), (40, 44), (32, 56)], fill=(255, 255, 255, 255))

        def on_show(icon, item):
            _open_app_window()

        def on_quit(icon, item):
            icon.stop()
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("Show QuickPOS", on_show, default=True),
            pystray.MenuItem("Quit", on_quit),
        )
        icon = pystray.Icon("QuickPOS", img, "QuickPOS", menu)
        icon.run()
    except ImportError:
        while True:
            time.sleep(1)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    if _wait_for_server("localhost", PORT):
        _open_app_window()
    else:
        webbrowser.open(f"http://localhost:{PORT}")

    _run_tray()
