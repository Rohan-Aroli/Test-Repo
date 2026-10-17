import time

from backend.database_writer import DatabaseWriter
from backend.supabase_client import supabase

last_push_time = 0
last_metric_write_time = 0
last_payload = {}
last_event_state = None
database_writer = DatabaseWriter(supabase)
status_callback = None
score_callback = None
EVENT_STATES = {"DROWSY", "UNRESPONSIVE", "MICROSLEEP", "DISTRACTION"}


def set_status_callback(callback):
    global status_callback
    status_callback = callback


def set_score_callback(callback):
    """Register the live score persistence callback supplied by the monitor."""
    global score_callback
    score_callback = callback


def report_status(message, success):
    if status_callback is not None:
        status_callback(message, success)


def _snapshot_payload(metrics, driver_state, frame_url=None):
    payload = {
        "ear": metrics.get("ear"),
        "perclos": metrics.get("perclos"),
        "blink_rate": metrics.get("blink_rate"),
        "driver_state": driver_state,
        "fatigue_score": metrics.get("drowsiness_score"),
        "eye_closure_duration": metrics.get("avg_closure_duration"),
    }
    if frame_url is not None:
        payload["frame_url"] = frame_url
    return payload


def push_driver_metrics(
    metrics,
    driver_state,
    frame_url=None,
    driver_id=None,
    trip_id=None,
):
    global last_push_time
    global last_metric_write_time
    global last_payload
    global last_event_state

    current_time = time.time()
    if not driver_id:
        return

    try:
        payload = _snapshot_payload(metrics, driver_state, frame_url)
        event_transition = (
            driver_state in EVENT_STATES
            and driver_state != last_event_state
        )

        if (
            last_payload
            and payload == last_payload
            and current_time - last_push_time < 1.0
        ):
            return

        database_writer.update_live_driver_state(
            metrics,
            driver_id,
            driver_state,
            frame_url=frame_url,
        )

        if (
            trip_id
            and (
                current_time - last_metric_write_time >= 1.0
                or event_transition
            )
        ):
            database_writer.write_driver_metrics(
                metrics,
                driver_id,
                trip_id,
                driver_state,
            )
            last_metric_write_time = current_time

        if event_transition:
            event_metadata = {
                "ear": metrics.get("ear"),
                "perclos": metrics.get("perclos"),
                "blink_rate": metrics.get("blink_rate"),
                "fatigue_score": metrics.get("drowsiness_score"),
                "eye_closure_duration": metrics.get("avg_closure_duration"),
            }
            if frame_url:
                event_metadata["frame_url"] = frame_url

            database_writer.write_event(
                event_type=driver_state,
                driver_id=driver_id,
                trip_id=trip_id,
                severity=(
                    "critical" if driver_state == "UNRESPONSIVE" else "warning"
                ),
                metadata=event_metadata,
            )
            database_writer.write_emergency_event(
                event_type=driver_state,
                severity=(
                    "critical" if driver_state == "UNRESPONSIVE" else "warning"
                ),
                event_message=(
                    f"Driver state changed to {driver_state}"
                    + (
                        f"; evidence_frame={frame_url}"
                        if frame_url
                        else ""
                    )
                ),
                driver_id=driver_id,
                trip_id=trip_id,
                resolved=False,
            )
            last_event_state = driver_state
            print(f"[EVENT] {driver_state} recorded for {driver_id}")

            if score_callback is not None and trip_id:
                score_callback(driver_id, trip_id)

        elif driver_state not in EVENT_STATES:
            last_event_state = None

        last_payload = payload.copy()
        last_push_time = current_time
        report_status("Live state updated", True)
        print("[SUPABASE LIVE ROW UPDATED]")

    except Exception as e:
        report_status(f"Supabase write failed: {e}", False)
        print(f"[SUPABASE ERROR]: {e}")