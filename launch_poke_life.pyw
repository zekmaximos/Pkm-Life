from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path


HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"


def _show_error(title: str, message: str) -> None:
    try:
        from tkinter import messagebox

        messagebox.showerror(title, message)
    except Exception:
        pass


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex((host, port)) == 0


def _open_browser() -> None:
    webbrowser.open(URL)


def main() -> None:
    root = Path(__file__).resolve().parent
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    if _port_is_open(HOST, PORT):
        _open_browser()
        return

    try:
        from web.app import app
    except Exception as exc:
        _show_error(
            "Poke Life",
            "Nao foi possivel iniciar o Poke Life.\n\n"
            "Verifique se as dependencias foram instaladas com:\n"
            "pip install -r requirements.txt\n\n"
            f"Erro: {exc}",
        )
        return

    threading.Timer(1.0, _open_browser).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
