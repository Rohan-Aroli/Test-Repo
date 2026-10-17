import numpy as np
import pytest

from detection import face_detection
from streamlit_app import MonitoringSession


def test_monitoring_session_keeps_latest_processed_frame():
    session = MonitoringSession("driver-1", {"name": "Driver"})
    first = np.zeros((2, 2, 3), dtype=np.uint8)
    second = np.full((2, 2, 3), 7, dtype=np.uint8)

    session._publish(first, {"face_detected": True}, "MONITORING")
    session._publish(second, {"face_detected": True}, "MONITORING")

    frame, metrics, state = session.latest()
    assert np.array_equal(frame, second)
    assert metrics == {"face_detected": True}
    assert state == "MONITORING"
    assert frame is not second


def test_face_detector_reports_unsupported_mediapipe_api(monkeypatch):
    monkeypatch.delattr(face_detection.mp, "solutions", raising=False)

    with pytest.raises(RuntimeError, match="legacy solutions API"):
        face_detection.FaceDetector()
