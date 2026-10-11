from pathlib import Path
import os
import sys

BASE_DIR = Path(__file__).resolve().parent
BASELINE_DIR = BASE_DIR / "face_detection_codes" / "baselines"
BASELINE_DIR.mkdir(parents=True, exist_ok=True)

face_python = Path(os.getenv("DRIVER_MONITOR_PYTHON", sys.executable))
face_main = BASE_DIR / "face_detection_codes" / "main.py"

if not face_python.exists():
    raise FileNotFoundError(
        f"❌ Face detection Python not found:\n{face_python}\n"
        "Set DRIVER_MONITOR_PYTHON environment variable to point to the correct interpreter."
    )