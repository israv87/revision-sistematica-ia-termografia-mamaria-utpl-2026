"""Start the local app and open its browser page when the server is ready."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "brujula_bibliografica" / "app.py"


def available_port() -> int:
    for port in range(8501, 8521):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No hay un puerto libre entre 8501 y 8520.")


def main() -> int:
    port = available_port()
    url = f"http://127.0.0.1:{port}"
    print("Iniciando el servidor local...", flush=True)
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP),
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
    ]
    process = subprocess.Popen(command, cwd=ROOT)
    try:
        for _ in range(120):
            if process.poll() is not None:
                return process.returncode or 1
            try:
                with urllib.request.urlopen(f"{url}/_stcore/health", timeout=1) as response:
                    if response.status == 200:
                        print(f"Abriendo {url}", flush=True)
                        if not webbrowser.open(url):
                            print(f"Abre esta direccion manualmente: {url}", flush=True)
                        return process.wait()
            except (OSError, urllib.error.URLError):
                time.sleep(0.5)
        print(f"El servidor tarda demasiado. Revisa {url}", flush=True)
        return 1
    except KeyboardInterrupt:
        print("Cerrando la aplicacion...", flush=True)
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
