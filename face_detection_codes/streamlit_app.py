import json
import os
import queue
import re
import threading
import time
from datetime import time as clock_time
from pathlib import Path
from uuid import uuid4

import cv2
import streamlit as st

from backend.database_writer import DatabaseUnavailableError, DatabaseWriter
from backend.supabase_client import supabase
from detection.eye_landmark_extractor import EyeLandmarkExtractor
from detection.face_detection import FaceDetector
from detection.mouth_landmark_extractor import MouthLandmarkExtractor
from metrics.drowsiness_detector import DrowsinessDetector
from metrics.mar_calculator import MARCalculator

BASE_DIR = Path(__file__).resolve().parent
BASELINE_DIR = BASE_DIR / "baselines"
BASELINE_DIR.mkdir(exist_ok=True)

db = DatabaseWriter(supabase)


def find_driver_by_id(driver_id: str):
    driver_id = (driver_id or "").strip()
    if not driver_id:
        return None
    return db.find_driver(driver_id)


def rough_work_path(driver_id: str) -> Path:
    return BASELINE_DIR / f"{driver_id}_rough_work.json"


def reset_rough_work(driver_id: str):
    path = rough_work_path(driver_id)
    path.write_text("[]", encoding="utf-8")
    return path


def append_rough_work_sample(driver_id: str, sample: dict):
    path = rough_work_path(driver_id)
    try:
        samples = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        samples = []
    samples.append(sample)
    path.write_text(json.dumps(samples, indent=2), encoding="utf-8")
    return path


def average(values):
    filtered = [float(v) for v in values if v is not None]
    if not filtered:
        return 0.0
    return sum(filtered) / len(filtered)


def stddev(values):
    filtered = [float(v) for v in values if v is not None]
    if len(filtered) < 2:
        return 0.0
    mean = average(filtered)
    return (sum((value - mean) ** 2 for value in filtered) / len(filtered)) ** 0.5


def build_baseline_from_samples(samples):
    valid_samples = []
    for sample in samples:
        try:
            values = (
                sample.get("ear"),
                sample.get("mar"),
                sample.get("perclos"),
                sample.get("blink_rate"),
                sample.get("eye_closure_duration"),
            )
            if any(value is None for value in values):
                continue
            [float(value) for value in values]
        except (TypeError, ValueError):
            continue
        valid_samples.append(sample)

    if not valid_samples:
        return {
            "avg_ear": 0.0,
            "avg_mar": 0.0,
            "avg_perclos": 0.0,
            "avg_blink_rate": 0.0,
            "avg_eye_closure_duration": 0.0,
            "sample_count": 0,
        }

    ear_values = [sample.get("ear") for sample in valid_samples]
    mar_values = [sample.get("mar") for sample in valid_samples]
    perclos_values = [sample.get("perclos") for sample in valid_samples]
    blink_values = [sample.get("blink_rate") for sample in valid_samples]
    closure_values = [sample.get("eye_closure_duration") for sample in valid_samples]

    baseline = {
        "avg_ear": average(ear_values),
        "avg_mar": average(mar_values),
        "avg_perclos": average(perclos_values),
        "avg_blink_rate": average(blink_values),
        "avg_eye_closure_duration": average(closure_values),
        "sample_count": len(valid_samples),
    }
    baseline.update({
        "ear_mean": baseline["avg_ear"],
        "ear_std": stddev(ear_values),
        "mar_mean": baseline["avg_mar"],
        "perclos_mean": baseline["avg_perclos"],
        "perclos_std": stddev(perclos_values),
        "blink_rate_mean": baseline["avg_blink_rate"],
        "blink_rate_std": stddev(blink_values),
        "eye_closure_duration_mean": baseline["avg_eye_closure_duration"],
        "eye_closure_duration_std": stddev(closure_values),
    })
    return baseline


def collect_baseline_rough_work(
    driver_id: str,
    duration_seconds: int = 60,
    preview_width: int = 320,
):
    path = reset_rough_work(driver_id)
    samples = []
    start_time = time.time()
    progress = st.progress(0)
    preview = st.empty()

    camera = cv2.VideoCapture(0)
    detector = FaceDetector()
    extractor = EyeLandmarkExtractor()
    mouth_extractor = MouthLandmarkExtractor()
    drowsiness_detector = DrowsinessDetector()
    mar_calculator = MARCalculator()

    if not camera.isOpened():
        raise RuntimeError("Unable to open camera for baseline collection.")

    try:
        while time.time() - start_time < duration_seconds:
            ret, frame = camera.read()
            if not ret or frame is None:
                time.sleep(0.1)
                continue

            preview.image(
                cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                caption="Baseline webcam preview",
                width=preview_width,
            )

            data = detector.detect(frame)
            if not data["face_detected"]:
                time.sleep(0.1)
                continue

            x, y, w, h = data["face_bbox"]
            face_region = frame[y:y + h, x:x + w]
            landmarks = extractor.extract(face_region, (x, y, w, h))
            left_eye = landmarks.get("left_eye", [])
            right_eye = landmarks.get("right_eye", [])

            if len(left_eye) != 6 or len(right_eye) != 6:
                time.sleep(0.1)
                continue

            metrics = drowsiness_detector.update(left_eye, right_eye)
            mouth_points = []
            mouth_data = mouth_extractor.extract(face_region, (x, y, w, h))
            if mouth_data and len(mouth_data.get("mouth", [])) == 8:
                mouth_points = mouth_data["mouth"]
                mar_value = mar_calculator.calculate_mar(mouth_points)
            else:
                mar_value = 0.0

            sample = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "ear": metrics.get("ear", 0.0),
                "mar": mar_value,
                "perclos": metrics.get("perclos", 0.0),
                "blink_rate": metrics.get("blink_rate", 0),
                "eye_closure_duration": metrics.get("avg_closure_duration", 0.0),
            }
            samples.append(sample)
            append_rough_work_sample(driver_id, sample)

            elapsed = time.time() - start_time
            progress.progress(min(1.0, elapsed / duration_seconds))
            time.sleep(0.25)
    finally:
        camera.release()
        preview.empty()

    baseline = build_baseline_from_samples(samples)
    db.save_driver_baseline(driver_id, baseline)
    return path, baseline


def register_driver(driver_id: str, profile: dict, baseline_summary: dict):
    driver = db.find_driver(driver_id)
    if driver is None:
        driver = db.register_driver(str(uuid4()), profile)
    local_baseline_path = BASELINE_DIR / f"{driver['id']}.json"
    local_baseline_path.write_text(
        json.dumps(baseline_summary, indent=2),
        encoding="utf-8",
    )
    return driver


class MonitoringSession:
    """Run the detector in a worker while Streamlit renders its latest frame."""

    def __init__(self, driver_id: str, profile: dict):
        self.driver_id = driver_id
        self.profile = profile
        self.events = queue.Queue(maxsize=2)
        self.error = None
        self.thread = threading.Thread(
            target=self._run,
            name="streamlit-driver-monitor",
            daemon=True,
        )

    def start(self):
        self.thread.start()
        return self

    def _publish(self, frame, metrics, state):
        event = (frame.copy(), dict(metrics), state)
        try:
            self.events.put_nowait(event)
        except queue.Full:
            try:
                self.events.get_nowait()
            except queue.Empty:
                pass
            self.events.put_nowait(event)

    def _run(self):
        os.environ["DRIVER_ID"] = self.driver_id
        os.environ["DRIVER_PROFILE_JSON"] = json.dumps(self.profile)
        os.environ["DASHBOARD_MODE"] = "1"
        try:
            import main

            main.stop_requested.clear()
            main.set_dashboard_callback(self._publish)
            threading.Thread(target=main.start_api, daemon=True).start()
            main.run_face_detection()
        except Exception as error:
            self.error = error

    def latest(self):
        event = None
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                return event

    def stop(self):
        try:
            import main

            main.request_stop()
        except ImportError:
            pass
        self.thread.join(timeout=5)


def stop_monitoring_process(session):
    if session is not None:
        session.stop()


def keep_plate_format(widget_key):
    value = st.session_state.get(widget_key, "")
    st.session_state[widget_key] = value.upper()[:13]


def render_landing_page():
    st.title("Driver Monitoring System")
    st.caption("Choose how you want to enter the pipeline.")

    registration_column, monitoring_column = st.columns(2)
    with registration_column:
        st.subheader("New driver registration")
        st.write("Create a driver profile, collect a baseline, and continue to monitoring.")
        if st.button("Register a new driver", type="primary", width="stretch"):
            st.session_state["page"] = "register"
            st.session_state["driver_id"] = ""
            st.session_state["baseline_summary"] = None
            st.rerun()

    with monitoring_column:
        st.subheader("Start monitoring")
        st.write("Select an existing driver and start the live monitoring pipeline.")
        if st.button("Monitor an existing driver", width="stretch"):
            st.session_state["page"] = "monitor"
            st.session_state["driver_id"] = ""
            st.rerun()


def render_registration_page():
    st.title("Driver Registration")
    driver_id = st.text_input(
        "Driver ID",
        value=st.session_state.get("driver_id", ""),
        key="registration_driver_id",
    ).strip()
    st.session_state["driver_id"] = driver_id

    if not driver_id:
        st.info("Enter the identifier that will be used for this driver.")
        if st.button("Back to dashboard"):
            st.session_state["page"] = "landing"
            st.rerun()
        return

    st.subheader(f"Registering driver: {driver_id}")

    name = st.text_input("Full name", max_chars=25)
    age = st.number_input("Age", min_value=0, max_value=62, value=0, step=1)
    contact_number = st.number_input(
        "Contact number",
        min_value=0,
        max_value=9999999999,
        value=None,
        step=1,
        format="%d",
        key="registration_contact",
        placeholder="10 digits",
    )
    contact = str(contact_number) if contact_number is not None else ""
    vehicle = st.text_input("Vehicle", max_chars=20)
    plate = st.text_input(
        "Plate number",
        max_chars=13,
        placeholder="AB 12 C 3456",
        key="registration_plate",
        on_change=keep_plate_format,
        args=("registration_plate",),
    )
    license_number = st.text_input("License number", max_chars=25)
    shift_start = st.time_input(
        "Shift start",
        value=clock_time(9, 0),
        format="24h",
    )

    profile = {
        "name": name,
        "employee_id": driver_id,
        "age": age,
        "contact": contact,
        "vehicle": vehicle,
        "plate": plate,
        "license": license_number,
        "route": st.text_input("Route"),
        "shift_start": shift_start.strftime("%H:%M"),
        "notes": st.text_area("Notes"),
        "fleet_id": st.text_input("Fleet ID (optional)"),
    }

    st.markdown("### Baseline collection (60s local rough work)")
    st.caption("The raw 60 second values will be stored locally in a .json rough-work file, then the averages will be written to Supabase.")
    preview_width = 800 if st.checkbox("Expand webcam preview", value=False) else 320

    if st.button("Start 60-second baseline collection"):
        with st.spinner("Collecting raw values for 60 seconds..."):
            rough_path, baseline = collect_baseline_rough_work(
                driver_id,
                duration_seconds=60,
                preview_width=preview_width,
            )
        st.success(f"Baseline recorded locally at: {rough_path}")
        st.json(baseline)
        st.session_state["baseline_summary"] = baseline

    if st.session_state.get("baseline_summary"):
        st.subheader("Baseline summary")
        st.json(st.session_state["baseline_summary"])

    if st.button("Save driver and continue to monitoring"):
        if not profile.get("name"):
            st.error("Driver name is required.")
        elif profile.get("contact") and not profile["contact"].isdigit():
            st.error("Contact number must contain only digits.")
        elif profile.get("contact") and len(profile["contact"]) != 10:
            st.error("Contact number must contain exactly 10 digits.")
        elif profile.get("plate") and not re.fullmatch(
            r"[A-Z]{2} [0-9]{2} [A-Z]{1,2} [0-9]{4}",
            profile["plate"],
        ):
            st.error("Plate number must match: AB 12 C 3456")
        else:
            with st.spinner("Saving driver and baseline..."):
                if not st.session_state.get("baseline_summary"):
                    rough_path, baseline = collect_baseline_rough_work(
                        driver_id,
                        duration_seconds=60,
                        preview_width=preview_width,
                    )
                    st.session_state["baseline_summary"] = baseline
                driver = register_driver(driver_id, {k: v for k, v in profile.items() if v not in (None, "", 0) or k == "employee_id"}, st.session_state["baseline_summary"])
            st.success(f"Driver saved: {driver.get('name')}")
            st.session_state["page"] = "monitor"
            st.rerun()

    if st.button("Back to landing page"):
        st.session_state["page"] = "landing"
        st.rerun()


@st.fragment(run_every="500ms")
def render_live_monitoring(session):
    event = session.latest()
    if event is not None:
        frame, metrics, state = event
        st.session_state["monitor_frame"] = frame
        st.session_state["monitor_metrics"] = metrics
        st.session_state["monitor_state"] = state

    if session.error is not None:
        st.error(f"Monitoring stopped: {session.error}")
        return

    frame = st.session_state.get("monitor_frame")
    if frame is None:
        st.info("Starting camera...")
    else:
        st.image(frame, channels="BGR", caption="Live driver-monitoring stream", width="stretch")

    state = st.session_state.get("monitor_state", "STARTING")
    st.metric("Driver state", state)

    metrics = st.session_state.get("monitor_metrics", {})
    metric_columns = st.columns(4)
    for column, (key, label) in zip(
        metric_columns,
        (("ear", "EAR"), ("perclos", "PERCLOS"), ("mar", "MAR"), ("pitch", "Head pitch")),
    ):
        value = metrics.get(key, 0)
        column.metric(label, f"{value:.2f}" if isinstance(value, float) else value)


def render_monitoring_page():
    st.title("Monitoring")
    driver_id = st.text_input(
        "Employee ID or driver UUID",
        value=st.session_state.get("driver_id", ""),
        key="monitoring_driver_id",
    ).strip()
    st.session_state["driver_id"] = driver_id

    if not driver_id:
        st.info("Enter an existing driver's identifier to continue.")
        if st.button("Back to dashboard"):
            st.session_state["page"] = "landing"
            st.rerun()
        return

    try:
        driver = find_driver_by_id(driver_id)
    except DatabaseUnavailableError as exc:
        st.error(
            "The driver database is temporarily unavailable. "
            "Check your internet connection and try again."
        )
        st.caption(str(exc))
        return

    if driver is None:
        st.warning("Driver record not found. Check the identifier or register this driver first.")
        if st.button("Back to dashboard"):
            st.session_state["page"] = "landing"
            st.rerun()
        return

    st.success(f"Monitoring active for {driver.get('name', driver_id)}")

    if "monitor_session" not in st.session_state:
        st.session_state["monitor_session"] = None

    if st.session_state["monitor_session"] is None:
        if st.button("Start monitoring", type="primary"):
            st.session_state["monitor_session"] = MonitoringSession(
                driver_id,
                {"name": driver.get("name")},
            ).start()
            st.rerun()
    else:
        st.info("Monitoring is running in this Streamlit window.")
        render_live_monitoring(st.session_state["monitor_session"])
        if st.button("Exit monitoring"):
            stop_monitoring_process(st.session_state["monitor_session"])
            st.session_state["monitor_session"] = None
            for key in ["monitor_frame", "monitor_metrics", "monitor_state"]:
                st.session_state.pop(key, None)
            st.rerun()

    if st.button("Back to dashboard"):
        if st.session_state["monitor_session"] is not None:
            stop_monitoring_process(st.session_state["monitor_session"])
            st.session_state["monitor_session"] = None
        st.session_state["page"] = "landing"
        st.rerun()


def main():
    st.set_page_config(page_title="Driver Monitoring", layout="wide")

    if "page" not in st.session_state:
        st.session_state["page"] = "landing"

    if "driver_id" not in st.session_state:
        st.session_state["driver_id"] = ""

    if "baseline_summary" not in st.session_state:
        st.session_state["baseline_summary"] = None

    if st.session_state["page"] == "landing":
        render_landing_page()
    elif st.session_state["page"] == "register":
        render_registration_page()
    elif st.session_state["page"] == "monitor":
        render_monitoring_page()

    if st.button("Reset session"):
        session = st.session_state.get("monitor_session")
        if session is not None:
            stop_monitoring_process(session)
        for key in [
            "page",
            "driver_id",
            "baseline_summary",
            "monitor_session",
            "monitor_frame",
            "monitor_metrics",
            "monitor_state",
        ]:
            st.session_state.pop(key, None)
        st.rerun()


if __name__ == "__main__":
    main()
