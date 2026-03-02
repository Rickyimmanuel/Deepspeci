"""
DeepSpeci Unified Launcher
Starts FastAPI (8000) + Streamlit (8501) with one command.
Usage: python run.py
"""
import subprocess
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)

env = os.environ.copy()
env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

PYTHON = sys.executable


def start_api():
    return subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "api.main:app",
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        env=env, cwd=str(PROJECT_ROOT),
    )


def start_ui():
    return subprocess.Popen(
        [PYTHON, "-m", "streamlit", "run", "ui/app.py",
         "--server.port", "8501", "--server.headless", "true"],
        env=env, cwd=str(PROJECT_ROOT),
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  DeepSpeci — starting services")
    print("=" * 60)

    api = start_api()
    print(f"  [API]  http://localhost:8000/docs   PID {api.pid}")

    ui = start_ui()
    print(f"  [UI]   http://localhost:8501        PID {ui.pid}")

    print("=" * 60)
    print("  Ctrl+C to stop")
    print("=" * 60)

    try:
        api.wait()
    except KeyboardInterrupt:
        print("\nShutting down…")
        api.terminate()
        ui.terminate()
        api.wait()
        ui.wait()
        print("Done.")
