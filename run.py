import os
import sys
import threading
import webbrowser
import time
from models import init_db

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    os.chdir(sys._MEIPASS)


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5001")

if __name__ == "__main__":
    init_db()  # safe to call every launch — creates tables only if missing
    from app import app
    threading.Thread(target=open_browser).start()
    app.run(host="127.0.0.1", port=5001, debug=False)