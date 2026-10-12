from pathlib import Path
import os
import sys

BASE_DIR = Path(__file__).resolve().parent
BASELINE_DIR = BASE_DIR / "face_detection_codes" / "baselines"
BASELINE_DIR.mkdir(parents=True, exist_ok=True)

face_python_env = os.getenv("DRIVER_MONITOR_PYTHON")
if face_python_env:
    face_python = Path(face_python_env)
else:
    current_py = Path(sys.executable)
    venv_py = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    face_venv_py = BASE_DIR / "face_detection_codes" / "facedetection" / "Scripts" / "python.exe"

    if current_py.exists() and "python" in current_py.name.lower():
        face_python = current_py
    elif venv_py.exists():
        face_python = venv_py
    elif face_venv_py.exists():
        face_python = face_venv_py
    else:
        face_python = current_py

face_main = BASE_DIR / "face_detection_codes" / "main.py"

if not face_python.exists():
    raise FileNotFoundError(
        f"❌ Face detection Python not found:\n{face_python}\n"
        "Set DRIVER_MONITOR_PYTHON environment variable to point to the correct interpreter."
    )