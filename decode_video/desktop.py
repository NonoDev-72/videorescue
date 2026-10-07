"""Aplicación de escritorio: servidor local + ventana nativa (pywebview)."""
import socket, threading
import webview
from .app import app

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]

def main():
    port = free_port()
    threading.Thread(target=lambda: app.run(host="127.0.0.1", port=port, threaded=True), daemon=True).start()
    webview.create_window("DECODE-VIDEO", "http://127.0.0.1:%d" % port, width=1180, height=800, min_size=(900, 600))
    webview.start()

if __name__ == "__main__":
    main()
