from pathlib import Path

_face_backend = Path(__file__).resolve().parent.parent / "face_detection_codes" / "backend"
if _face_backend.exists() and str(_face_backend) not in __path__:
    __path__.append(str(_face_backend))
