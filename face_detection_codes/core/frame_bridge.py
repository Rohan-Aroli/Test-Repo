from threading import Lock

import time
latest_frame = None
latest_timestamp = 0.0
frame_lock = Lock()


def send_frame(frame):
    """
    Store latest frame safely.
    """
    global latest_frame, latest_timestamp

    with frame_lock:
        latest_frame = frame.copy()
        latest_timestamp = time.time()


def receive_frame():
    """
    Return latest frame safely.
    """
    with frame_lock:
        if latest_frame is None:
            return None, 0.0

        return latest_frame.copy(), latest_timestamp