import os
import sys
import threading
import time

import webview

from models import init_db


# PyInstaller resource directory
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    os.chdir(sys._MEIPASS)


HOST = "127.0.0.1"
PORT = 5001


def start_server():
    from app import app
    from waitress import serve

    serve(
        app,
        host=HOST,
        port=PORT,
        threads=8
    )


if __name__ == "__main__":

    # Initialize database
    init_db()

    # Start Flask/Waitress server
    server_thread = threading.Thread(
        target=start_server,
        daemon=True
    )

    server_thread.start()

    # Give Waitress time to start
    time.sleep(1.5)

    # Create native desktop window
    window = webview.create_window(
        "QuickPOS",
        f"http://{HOST}:{PORT}",
        width=1200,
        height=800,
        min_size=(900, 600),
        resizable=True
    )

    # Start PyWebView
    webview.start()