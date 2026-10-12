from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import cv2
import time

from core import frame_bridge
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
STREAM_FPS = 15
FRAME_DELAY = 1 / STREAM_FPS
def generate_frames():

    while True:

        try:
            latest_frame, timestamp = (
                frame_bridge.receive_frame()
            )

            if latest_frame is None:
                time.sleep(0.1)
                continue

            ret, buffer = cv2.imencode(
                ".jpg",
                latest_frame
            )

            if not ret:
                continue

            frame_bytes = buffer.tobytes()

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n'
                + frame_bytes +
                b'\r\n'
            )
            time.sleep(FRAME_DELAY)

        except GeneratorExit:
            break
        except Exception as e:

            print(
                f"[API ERROR]: {e}"
            )

            time.sleep(0.1)
            continue


@app.get("/")
def home():

    return {
        "status": "running",
        "video_endpoint": "/video_feed",
        "health_endpoint": "/health"
    }


@app.get("/health")
def health():
    import time
    latest_frame, timestamp = (
        frame_bridge.receive_frame()
    )

    is_active = False
    if latest_frame is not None:
        if (time.time() - timestamp) < 5.0:
            is_active = True

    return {
        "backend_status": "healthy",
        "camera_stream_active": is_active
    }


@app.get("/video_feed")
def video_feed():

    return StreamingResponse(
        generate_frames(),
        media_type=
        "multipart/x-mixed-replace; boundary=frame"
    )