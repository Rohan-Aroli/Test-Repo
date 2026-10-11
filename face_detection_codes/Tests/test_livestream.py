import pytest
from fastapi.testclient import TestClient
import numpy as np
import time

from core import frame_bridge
from backend.Streaming_frames_endpoint import app, generate_frames

client = TestClient(app)

def test_health_no_frame():
    frame_bridge.latest_frame = None
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["camera_stream_active"] == False

def test_health_with_fresh_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame_bridge.send_frame(frame)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["camera_stream_active"] == True

def test_health_with_stale_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame_bridge.send_frame(frame)
    frame_bridge.latest_timestamp = time.time() - 10.0

    # We must patch the client because we mutated the module directly
    # but the client might load the endpoint and use a different instance of frame_bridge
    # Wait, they share memory if imported from the same root. Let's just fix Streaming_frames_endpoint.py

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["camera_stream_active"] == False

def test_video_feed_yields_mjpeg():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame_bridge.send_frame(frame)

    # Test generator directly
    gen = generate_frames()
    chunk = next(gen)
    assert b"--frame\r\n" in chunk
    assert b"Content-Type: image/jpeg\r\n\r\n" in chunk

    # Test generator cleanup/disconnect handling
    gen.close()
    with pytest.raises(StopIteration):
        next(gen)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "video_endpoint" in response.json()
