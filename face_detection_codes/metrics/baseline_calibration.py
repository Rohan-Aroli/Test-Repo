import time
import json
import os
from pathlib import Path


class BaselineCalibrator:

    def __init__(self, calibration_time=60):

        self.calibration_time = calibration_time

        self.start_time = None

        # Feature buffers
        self.ear_values = []
        self.mar_values = []
        self.perclos_values = []
        self.blink_rates = []
        self.closure_values = []

        self.pitch_values = []
        self.yaw_values = []
        self.roll_values = []

        self.calibrated = False

        self.baseline = {}

        # -------------------------------
        # Multi-driver support
        # -------------------------------
        self.baseline_folder = Path(
            "baselines"
        )

        self.baseline_folder.mkdir(
            exist_ok=True
        )

        self.save_path = None

    # -----------------------------------
    # Set active driver
    # -----------------------------------
    def set_driver(self, driver_id, alias=None):

        self.driver_id = str(driver_id).strip() if driver_id else "default_driver"
        self.alias = str(alias).strip() if alias else None
        self.save_path = (
            self.baseline_folder /
            f"{self.driver_id}.json"
        )

        print(
            f"[CALIBRATOR] Active Driver: "
            f"{self.driver_id}"
        )

    # -----------------------------------
    # Start calibration
    # -----------------------------------
    def start(self):

        self.start_time = time.time()

        print(
            "[CALIBRATION] Started"
        )

    # -----------------------------------
    # Reset calibration buffers
    # -----------------------------------
    def reset(self):

        self.start_time = None

        self.ear_values.clear()
        self.mar_values.clear()
        self.perclos_values.clear()
        self.blink_rates.clear()
        self.closure_values.clear()

        self.pitch_values.clear()
        self.yaw_values.clear()
        self.roll_values.clear()

        self.calibrated = False

        self.baseline = {}

        print(
            "[CALIBRATION] Reset"
        )

    # -----------------------------------
    # Update calibration
    # -----------------------------------
    def update(self, metrics):

        if self.calibrated:
            return True

        if self.start_time is None:
            self.start()

        elapsed = (
            time.time() -
            self.start_time
        )

        # Store values

        self.ear_values.append(
            metrics.get("ear", 0)
        )

        self.mar_values.append(
            metrics.get("mar", 0)
        )

        self.perclos_values.append(
            metrics.get("perclos", 0)
        )

        self.blink_rates.append(
            metrics.get("blink_rate", 0)
        )

        self.closure_values.append(
            metrics.get(
                "avg_closure_duration",
                0
            )
        )

        self.pitch_values.append(
            metrics.get("pitch", 0)
        )

        self.yaw_values.append(
            metrics.get("yaw", 0)
        )

        self.roll_values.append(
            metrics.get("roll", 0)
        )

        print(
            f"[CALIBRATING] "
            f"{elapsed:.1f}/"
            f"{self.calibration_time}s"
        )

        # -----------------------------------
        # Calibration completed
        # -----------------------------------
        if elapsed >= self.calibration_time:

            self.baseline = {

                "ear_mean":
                    sum(self.ear_values)
                    / len(self.ear_values),

                "mar_mean":
                    sum(self.mar_values)
                    / len(self.mar_values),

                "perclos_mean":
                    sum(self.perclos_values)
                    / len(self.perclos_values),

                "blink_rate_mean":
                    sum(self.blink_rates)
                    / len(self.blink_rates),

                "closure_mean":
                    sum(self.closure_values)
                    / len(self.closure_values),

                "pitch_mean":
                    sum(self.pitch_values)
                    / len(self.pitch_values),

                "yaw_mean":
                    sum(self.yaw_values)
                    / len(self.yaw_values),

                "roll_mean":
                    sum(self.roll_values)
                    / len(self.roll_values)
            }

            self.save_baseline()

            self.calibrated = True

            print(
                "[CALIBRATION COMPLETE]"
            )

        return self.calibrated

    # -----------------------------------
    # Save baseline
    # -----------------------------------
    def save_baseline(self):

        try:

            if self.save_path is None:

                raise ValueError(
                    "Driver not selected"
                )

            with open(
                    self.save_path,
                    "w") as f:

                json.dump(
                    self.baseline,
                    f,
                    indent=4
                )

            print(
                f"[BASELINE SAVED] "
                f"{self.save_path}"
            )

        except Exception as e:

            print(
                f"[SAVE ERROR] {e}"
            )

    # -----------------------------------
    # Load baseline
    # -----------------------------------
    def load_baseline(self):

        try:
            candidates = [self.save_path]
            if hasattr(self, "driver_id") and self.driver_id:
                candidates.extend([
                    self.baseline_folder / f"{self.driver_id}.json",
                    Path("baselines") / f"{self.driver_id}.json",
                    Path(__file__).resolve().parent.parent / "baselines" / f"{self.driver_id}.json",
                ])
            if hasattr(self, "alias") and self.alias:
                candidates.extend([
                    self.baseline_folder / f"{self.alias}.json",
                    Path("baselines") / f"{self.alias}.json",
                    Path(__file__).resolve().parent.parent / "baselines" / f"{self.alias}.json",
                ])

            for p in candidates:
                if p and Path(p).exists() and Path(p).is_file():
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and len(data) > 0:
                        self.baseline = data
                        self.calibrated = True
                        self.save_path = Path(p)
                        print(f"[BASELINE LOADED] {self.save_path}")
                        return True

            return False

        except Exception:

            return False

    # -----------------------------------
    # Get baseline
    # -----------------------------------
    def get_baseline(self):

        return self.baseline