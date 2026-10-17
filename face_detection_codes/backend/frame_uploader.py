import cv2
import time
import uuid

from backend.database_writer import DatabaseWriter
from backend.supabase_client import supabase

last_frame_uploads = {}
UPLOAD_INTERVAL = 1.0  # seconds per driver/event type
database_writer = DatabaseWriter(supabase)


def upload_driver_frame(frame, driver_id=None, event_type=None):
    """Upload and register one important event frame.

    The live dashboard stream stays in memory and never goes through Supabase.
    Callers invoke this only on significant state transitions.
    """

    current_time = time.time()
    upload_key = (str(driver_id or "unknown"), str(event_type or "driver_event"))

    if (
        current_time - last_frame_uploads.get(upload_key, 0) < UPLOAD_INTERVAL
    ):
        return None

    try:
        success, buffer = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, 55],
        )

        if not success:
            print("[FRAME ERROR] JPEG encoding failed")
            return None

        frame_bytes = buffer.tobytes()
        filename = (
            f"{event_type or 'driver_event'}_"
            f"{driver_id or 'unknown'}_"
            f"{int(current_time)}_"
            f"{uuid.uuid4().hex[:8]}.jpg"
        )
        bucket_name = "driver-feed"

        supabase.storage.from_(bucket_name).upload(
            path=filename,
            file=frame_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "false"},
        )

        public_url = supabase.storage.from_(bucket_name).get_public_url(filename)
        last_frame_uploads[upload_key] = current_time

        if driver_id:
            database_writer.write_frame(public_url, driver_id)

        print(f"[FRAME UPLOAD SUCCESS] {filename}")
        return public_url

    except Exception as e:
        error_message = str(e)

        if "Bucket not found" in error_message:
            print("[FRAME UPLOAD ERROR] Supabase bucket 'driver-feed' does not exist.")
        elif "Duplicate" in error_message:
            print("[FRAME UPLOAD ERROR] File already exists.")
        else:
            print(f"[FRAME UPLOAD ERROR]: {e}")

        return None