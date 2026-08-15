#!/usr/bin/env python3
"""Запуск Exam Checker на Mac и Windows (открывает браузер)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def free_port(start: int = 8501) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "exam_checker"
    return Path(__file__).resolve().parents[1]


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = project_root()
    ui = app_dir()
    app_py = ui / "app.py"
    if not app_py.exists():
        app_py = Path(__file__).resolve().parents[1] / "app.py"

    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env")
        load_dotenv(ui / ".env")
    except ImportError:
        pass

    port = free_port()
    url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_py),
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        f"--server.fileWatcherType=none",
    ]

    print("Exam Checker")
    print(f"Открываю {url}")
    print("Закройте это окно, чтобы остановить программу.")

    proc = subprocess.Popen(cmd, cwd=str(root), env=env)
    time.sleep(2.5)
    webbrowser.open(url)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()
