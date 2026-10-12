import cv2
import time
import uuid

from backend.database_writer import DatabaseWriter
from backend.supabase_client import supabase

last_frame_upload = 0
UPLOAD_INTERVAL = 1.0  # seconds
last_uploaded_url = None
database_writer = DatabaseWriter(supabase)


def upload_driver_frame(frame, driver_id=None, event_type=None):
    """Upload an important event frame to Supabase Storage only.

    The live dashboard stream stays in memory and never goes through Supabase.
    This helper is intentionally limited to single evidence-frame uploads when a
    significant state transition occurs.
    """

    global last_frame_upload
    global last_uploaded_url

    current_time = time.time()

    if current_time - last_frame_upload < UPLOAD_INTERVAL and last_uploaded_url:
        return last_uploaded_url

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
        if not supabase or not hasattr(supabase, "storage"):
            print("[FRAME UPLOAD] Supabase storage client not available. Skipping upload.")
            return None

        bucket_name = "driver-feed"

        supabase.storage.from_(bucket_name).upload(
            path=filename,
            file=frame_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "false"},
        )

        public_url = supabase.storage.from_(bucket_name).get_public_url(filename)
        if public_url:
            last_uploaded_url = public_url
            last_frame_upload = current_time

            if driver_id:
                database_writer.update_latest_driver_frame(driver_id, public_url)

            print(f"[FRAME UPLOAD SUCCESS] {filename}")
            return public_url
        return None

    except Exception as e:
        error_message = str(e)

        if "Bucket not found" in error_message:
            print("[FRAME UPLOAD ERROR] Supabase bucket 'driver-feed' does not exist.")
        elif "Duplicate" in error_message:
            print("[FRAME UPLOAD ERROR] File already exists.")
        else:
            print(f"[FRAME UPLOAD ERROR]: {e}")

        return None