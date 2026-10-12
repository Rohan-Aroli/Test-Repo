
import sys
from pathlib import Path

# Ensure face_detection_codes is first on sys.path
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import cv2
import json
import os
import threading
from datetime import datetime
from uuid import uuid4

import uvicorn

from backend.frame_uploader import upload_driver_frame
from backend.database_writer import DatabaseWriter
from backend.push_metrics import push_driver_metrics
from backend.supabase_client import supabase
from backend import Streaming_frames_endpoint as stream

from detection.face_detection import FaceDetector
from detection.eye_landmark_extractor import EyeLandmarkExtractor
from detection.mouth_landmark_extractor import MouthLandmarkExtractor
from detection.head_pose_estimator import HeadPoseEstimator

from metrics.drowsiness_detector import DrowsinessDetector
from metrics.mar_calculator import MARCalculator
from metrics.yawn_detector import YawnDetector
from metrics.microsleep_detector import MicrosleepDetector
from metrics.baseline_calibration import BaselineCalibrator

from core import frame_bridge
from core.driver_manager import DriverManager
from core.enhanced_driver_state_classifier import (
    EnhancedDriverStateClassifier
)
from core.system_mode_manager import SystemModeManager
from core.logger import (
    write_state_periodically,
    write_scores_periodically
)

from DriverScore.db_repository import ScoreRepository
from DriverScore.models import TripContext
from DriverScore.scoring_pipeline import ScoringPipeline


# ---------------- INITIALIZE MODULES ----------------
drowsy_detector = DrowsinessDetector()

mouth_extractor = MouthLandmarkExtractor()

mar_calculator = MARCalculator()

yawn_detector = YawnDetector()

microsleep_detector = MicrosleepDetector()

head_pose_estimator = HeadPoseEstimator()

driver_manager = DriverManager()
mode_manager = SystemModeManager()
database_writer = DatabaseWriter(supabase)
dashboard_callback = None
stop_requested = threading.Event()


def set_dashboard_callback(callback):
    global dashboard_callback
    dashboard_callback = callback


def dashboard_update(frame, metrics, driver_state):
    if dashboard_callback is not None:
        dashboard_callback(frame, metrics, driver_state)


def request_stop():
    stop_requested.set()


def prompt_optional(label):
    if os.getenv("DASHBOARD_MODE") == "1" or not sys.stdin.isatty():
        return None
    try:
        value = input(f"{label} (optional): ").strip()
        return value or None
    except (EOFError, OSError):
        return None


def register_new_driver(identifier):
    print("\nNew driver registration")
    identifier = identifier or "default_driver"
    profile_json = os.getenv("DRIVER_PROFILE_JSON")
    profile_values = json.loads(profile_json) if profile_json else {}
    name = profile_values.get("name")
    if not name and os.getenv("DASHBOARD_MODE") != "1" and sys.stdin.isatty():
        try:
            name = input("Name: ").strip()
        except (EOFError, OSError):
            name = None
    if not name:
        name = f"Driver {identifier}"

    age_text = profile_values.get("age") or prompt_optional("Age")
    age = int(age_text) if age_text else None

    profile = {
        "name": name,
        "age": age,
        "employee_id": identifier,
        "license": profile_values.get("license") or prompt_optional("License number"),
        "contact": profile_values.get("contact") or prompt_optional("Contact"),
        "vehicle": profile_values.get("vehicle") or prompt_optional("Vehicle"),
        "plate": profile_values.get("plate") or prompt_optional("Plate number"),
        "route": profile_values.get("route") or prompt_optional("Route"),
        "origin": profile_values.get("origin") or prompt_optional("Origin"),
        "destination": profile_values.get("destination") or prompt_optional("Destination"),
        "shift_start": profile_values.get("shift_start") or prompt_optional("Shift start"),
        "notes": profile_values.get("notes") or prompt_optional("Notes"),
        "fleet_id": None,
    }

    driver = database_writer.register_driver(
        str(uuid4()),
        profile,
    )
    print(f"[INFO] Driver registered: {driver.get('name', name)}")
    return driver


# Globals for initialization
driver_id = None
cap = None
detector = None
extractor = None
last_uploaded_state = None
trip_start_time = None
current_trip_id = None
classifier = None
scoring_pipeline = None


def init_pipeline():
    global driver_id, cap, detector, extractor, last_uploaded_state
    global trip_start_time, current_trip_id, classifier, scoring_pipeline

    from datetime import timezone

    entered_driver_id = os.getenv("DRIVER_ID")
    if not entered_driver_id:
        if sys.stdin.isatty():
            try:
                entered_driver_id = input(
                    "Enter employee ID or driver UUID: "
                ).strip().lower()
            except (EOFError, OSError):
                entered_driver_id = None
        if not entered_driver_id:
            entered_driver_id = "default_driver"

    driver_profile = database_writer.find_driver(entered_driver_id)

    if not driver_profile:
        driver_profile = register_new_driver(entered_driver_id)

    driver_id = driver_profile.get("id") or str(uuid4())
    driver_manager.set_driver(driver_id)

    calibrator = BaselineCalibrator(calibration_time=60)
    calibrator.set_driver(driver_id)

    if calibrator.load_baseline():
        print("[INFO] Existing baseline loaded")
        mode_manager.set_mode("MONITORING")
    else:
        print("[INFO] No baseline found.")
        mode_manager.set_mode("CALIBRATION")

    classifier = EnhancedDriverStateClassifier(
        profile=calibrator.get_baseline()
    )
    drowsy_detector.ear_threshold = classifier.get_ear_threshold()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        if os.getenv("DRY_RUN") == "1":
            print("[WARNING] Failed to open webcam in DRY_RUN mode. Proceeding with dummy camera.")
        else:
            raise RuntimeError("Failed to open webcam.")

    detector = FaceDetector()
    extractor = EyeLandmarkExtractor()
    last_uploaded_state = None
    trip_start_time = datetime.now(timezone.utc)
    trip = database_writer.start_trip(
        driver_id,
        trip_start_time,
        driver_profile,
    )
    current_trip_id = trip.get("trip_id") or str(uuid4())

    score_repository = ScoreRepository(supabase)
    scoring_pipeline = ScoringPipeline(score_repository)


# ---------------- START FASTAPI SERVER ----------------
def start_api():
    try:
        print("[INFO] Starting FastAPI streaming server...")
        import socket
        base_port = int(os.getenv("STREAM_PORT", "8000"))
        port = base_port

        for p in range(base_port, base_port + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", p)) != 0:
                    port = p
                    break

        uvicorn.run(
            stream.app,
            host="127.0.0.1",
            port=port,
            log_level="warning"
        )

    except Exception as e:
        print(f"[ERROR] API Server failed to start: {e}")


def finalize_trip_score():
    """Compute and persist DriverScore for the current trip."""
    from datetime import timezone
    try:
        if not current_trip_id or not scoring_pipeline:
            return

        trip_end_time = datetime.now(timezone.utc)

        database_writer.end_trip(
            current_trip_id,
            trip_end_time,
        )

        trip_context = TripContext(
            trip_id=current_trip_id,
            driver_id=driver_id,
            trip_start=trip_start_time,
            trip_end=trip_end_time
        )

        score = scoring_pipeline.process_trip(trip_context)

        print(
            "[DRIVER SCORE] "
            f"raw={score.raw_driver_score} "
            f"final={score.final_driver_score} "
            f"confidence={score.score_confidence}"
        )

    except Exception as e:
        print(f"[DRIVER SCORE ERROR] {e}")


# ---------------- MAIN PIPELINE ----------------
def run_face_detection():
    global last_uploaded_state
    if cap is None:
        init_pipeline()

    print(" DRIVER MONITORING SYSTEM STARTED")
    print(
    f"[ACTIVE DRIVER] {driver_id}"
    )

    while not stop_requested.is_set():
        try:
            if cap is not None and cap.isOpened():
                ret, frame = cap.read()
            elif os.getenv("DRY_RUN") == "1":
                import numpy as np
                ret, frame = True, np.zeros((480, 640, 3), dtype=np.uint8)
            else:
                ret, frame = False, None

            if not ret or frame is None:
                print("[ERROR] Camera frame not received")
                if os.getenv("DRY_RUN") == "1":
                    break
                time.sleep(0.1)
                continue

            # --------------------------------------------
            # CREATE CLEAN FRAME COPY FOR DASHBOARD STREAM
            # --------------------------------------------
            raw_frame = frame.copy()
            frame_url = None

            # --------------------------------------------
            # SEND FRAME TO LOCAL FASTAPI STREAM
            # --------------------------------------------
            try:
                frame_bridge.send_frame(raw_frame)
            except Exception as e:
                print(f"[WARNING] Frame streaming failed: {e}")

            # --------------------------------------------
            # FACE DETECTION
            # --------------------------------------------
            data = detector.detect(frame)
            face_detected = data["face_detected"]

            left_eye = []
            right_eye = []
            mouth_points = []

            landmarks = {
                "left_eye": [],
                "right_eye": [],
                "nose_tip": None,
                "chin": None,
                "left_eye_corner": None,
                "right_eye_corner": None,
                "left_mouth_corner": None,
                "right_mouth_corner": None
            }

            x, y, w, h = 0, 0, 0, 0

            # --------------------------------------------
            # EXTRACT EYE LANDMARKS
            # --------------------------------------------
            if face_detected:
                try:
                    x, y, w, h = data["face_bbox"]

                    face_region = frame[y:y+h, x:x+w]

                    landmarks = extractor.extract(
                        face_region,
                        (x, y, w, h)
                    )

                    left_eye = landmarks["left_eye"]
                    right_eye = landmarks["right_eye"]

                    mouth_data = mouth_extractor.extract(
                        face_region,
                        (x, y, w, h)
                    )

                    mouth_points = mouth_data["mouth"]

                except Exception as e:
                    print(f"[ERROR] Landmark extraction failed: {e}")
                    face_detected = False

            # --------------------------------------------
            # CLASSIFICATION PIPELINE
            # --------------------------------------------
            try:

                if face_detected and len(left_eye) == 6 and len(right_eye) == 6:

                    metrics = drowsy_detector.update(
                        left_eye,
                        right_eye
                    )

                    # ---------------------------------
                    # MAR
                    # ---------------------------------

                    mar = 0

                    if len(mouth_points) == 8:

                        mar = mar_calculator.calculate_mar(
                            mouth_points
                        )

                    # ---------------------------------
                    # Yawning
                    # ---------------------------------

                    yawn_metrics = yawn_detector.update(
                        mar
                    )

                    # ---------------------------------
                    # Microsleep
                    # ---------------------------------

                    micro_metrics = microsleep_detector.update(
                        metrics["ear"],
                        drowsy_detector.ear_threshold
                    )

                    # ---------------------------------
                    # Head Pose
                    # ---------------------------------

                    if all([
                        landmarks["nose_tip"],
                        landmarks["chin"],
                        landmarks["left_eye_corner"],
                        landmarks["right_eye_corner"],
                        landmarks["left_mouth_corner"],
                        landmarks["right_mouth_corner"]
                    ]):

                        head_pose = head_pose_estimator.estimate(
                            frame,
                            landmarks
                        )

                    else:

                        head_pose = {
                            "pitch": 0,
                            "yaw": 0,
                            "roll": 0
                        }

                    # ---------------------------------
                    # Merge metrics
                    # ---------------------------------

                    metrics.update({

                        "face_detected": True,

                        "eyes_detected": True,

                        "mar": mar,
                        "driver_id": driver_id,

                        "is_yawning":
                            yawn_metrics["is_yawning"],

                        "yawn_count":
                            yawn_metrics["yawn_count"],

                        "avg_yawn_duration":
                            yawn_metrics["avg_yawn_duration"],

                        "continuous_eye_closure":
                            micro_metrics[
                                "continuous_eye_closure"
                            ],

                        "microsleep_detected":
                            micro_metrics[
                                "microsleep_detected"
                            ],

                        "microsleep_count":
                            micro_metrics[
                                "microsleep_count"
                            ],

                        "avg_microsleep_duration":
                            micro_metrics[
                                "avg_microsleep_duration"
                            ],

                        "pitch":
                            head_pose["pitch"],

                        "yaw":
                            head_pose["yaw"],

                        "roll":
                            head_pose["roll"]
                    })

                    # ---------------------------------
                    # Calibration
                    # ---------------------------------

                    # ---------------------------------
                    # System Mode Handling
                    # ---------------------------------

                    if mode_manager.is_calibration():

                        calibrator.update(metrics)

                        driver_state = "CALIBRATING"

                        if calibrator.calibrated:

                            classifier.update_profile(
                                calibrator.get_baseline()
                            )
                            drowsy_detector.ear_threshold = (
                                classifier.get_ear_threshold()
                            )

                            mode_manager.set_mode(
                                "WAITING"
                            )

                            mode_manager.set_mode("MONITORING")

                    elif mode_manager.is_monitoring():

                        driver_state = classifier.classify(
                            metrics
                        )

                    else:

                        driver_state = "WAITING"
                    write_scores_periodically(metrics)

                    # --------------------------------------------
                    # UPLOAD ONLY WHEN DRIVER BECOMES UNRESPONSIVE
                    # --------------------------------------------
                    metrics["driver_id"] = driver_id

                    if (
                        driver_state == "UNRESPONSIVE"
                        and last_uploaded_state != "UNRESPONSIVE"
                    ):
                        frame_url = upload_driver_frame(
                            raw_frame,
                            driver_id,
                        )

                        print(
                            "[INCIDENT SNAPSHOT SAVED]"
                        )

                    last_uploaded_state = driver_state



                    # --------------------------------------------
                    # PUSH METRICS + FRAME URL
                    # --------------------------------------------
                    push_driver_metrics(
                        metrics,
                        driver_state,
                        frame_url,
                        driver_id=driver_id,
                        trip_id=current_trip_id
                    )

                elif face_detected:
                    print("[WARNING] Eye landmarks incomplete")

                    metrics = {

                        "face_detected": True,

                        "eyes_detected": False,

                        "drowsiness_score": 0,

                        "perclos": 0,

                        "ear": 0,

                        "blink_rate": 0,

                        "avg_closure_duration": 0,

                        "mar": 0,

                        "yawn_count": 0,

                        "is_yawning": False,

                        "continuous_eye_closure": 0,

                        "microsleep_detected": False,

                        "pitch": 0,

                        "yaw": 0,

                        "roll": 0
                    }
                    driver_state = classifier.classify(metrics)

                    #frame_url = upload_driver_frame(raw_frame)


                    push_driver_metrics(
                        metrics,
                        driver_state,
                        frame_url,
                        driver_id=driver_id,
                        trip_id=current_trip_id
                    )

                else:
                    print("[INFO] Face not detected")

                    metrics = {

                        "face_detected": False,

                        "eyes_detected": False,

                        "drowsiness_score": 0,

                        "perclos": 0,

                        "ear": 0,

                        "blink_rate": 0,

                        "avg_closure_duration": 0,

                        "mar": 0,

                        "yawn_count": 0,

                        "is_yawning": False,

                        "continuous_eye_closure": 0,

                        "microsleep_detected": False,

                        "pitch": 0,

                        "yaw": 0,

                        "roll": 0
                    }

                    driver_state = classifier.classify(metrics)

                    #frame_url = upload_driver_frame(raw_frame)

                    push_driver_metrics(
                        metrics,
                        driver_state,
                        frame_url,
                        driver_id=driver_id,
                        trip_id=current_trip_id
                    )

            except Exception as e:
                print(f"[ERROR] Classification pipeline failed: {e}")
                driver_state = "ERROR"

            # --------------------------------------------
            # LOG FINAL STATE
            # --------------------------------------------
            try:
                write_state_periodically({
                    "driver_state": driver_state
                })

            except Exception as e:
                print(f"[WARNING] JSON logging failed: {e}")

            print(f"[STATE] {driver_state}")

            dashboard_update(frame, metrics, driver_state)

            # --------------------------------------------
            # LOCAL DEBUG WINDOW
            # --------------------------------------------
            if os.getenv("DASHBOARD_MODE") == "1":
                continue

            if face_detected:

                cv2.rectangle(
                    frame,
                    (x, y),
                    (x + w, y + h),
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"STATE: {driver_state}",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"EAR: {metrics.get('ear', 0):.2f}",
                    (x, y + h + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"PERCLOS: {metrics.get('perclos', 0):.2f}",
                    (x, y + h + 45),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 0),
                    2
                )
                cv2.putText(
                    frame,
                    f"MAR: {metrics.get('mar',0):.2f}",
                    (x, y + h + 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0,255,255),
                    2
                )

                cv2.putText(
                    frame,
                    f"Yawns: {metrics.get('yawn_count',0)}",
                    (x, y + h + 95),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255,255,0),
                    2
                )

                cv2.putText(
                    frame,
                    f"Closure: {metrics.get('continuous_eye_closure',0):.1f}s",
                    (x, y + h + 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0,255,0),
                    2
                )

                cv2.putText(
                    frame,          
                    f"Pitch: {metrics.get('pitch',0):.1f}",
                    (x, y + h + 145),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0,0,255),
                    2
                )

                for (lx, ly) in landmarks["left_eye"]:
                    cv2.circle(
                        frame,
                        (lx, ly),
                        3,
                        (0, 0, 255),
                        -1
                    )

                for (rx, ry) in landmarks["right_eye"]:
                    cv2.circle(
                        frame,
                        (rx, ry),
                        3,
                        (255, 0, 0),
                        -1
                    )

                for (mx, my) in mouth_points:
                    cv2.circle(
                        frame,
                        (mx, my),
                        3,
                        (0, 255, 255),
                        -1
                    )

            else:
                cv2.putText(
                    frame,
                    f"STATE: {driver_state}",
                    (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2
                )

            if os.getenv("HEADLESS") != "1" and os.getenv("DRY_RUN") != "1":
                cv2.imshow("Driver Monitoring System", frame)

                if cv2.waitKey(1) & 0xFF == 27:
                    print("[INFO] Exiting system...")
                    break
            elif os.getenv("DRY_RUN") == "1":
                print("[INFO] Dry run single cycle completed successfully.")
                break

        except Exception as e:
            print(f"[CRITICAL ERROR] Main loop failure: {e}")
            if os.getenv("DRY_RUN") == "1":
                break
            continue

    if cap is not None and hasattr(cap, "release") and cap.isOpened():
        cap.release()
    cv2.destroyAllWindows()
    finalize_trip_score()


# ---------------- ENTRY POINT ----------------
if __name__ == "__main__":
    try:
        threading.Thread(
            target=start_api,
            daemon=True
        ).start()

        run_face_detection()

    except KeyboardInterrupt:
        print("[INFO] System stopped manually")
        finalize_trip_score()

    except Exception as e:
        print(f"[CRITICAL ERROR] System startup failed: {e}")
