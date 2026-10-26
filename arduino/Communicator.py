import json
import os
import sys
import time
from pathlib import Path

# Add project root and arduino directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from arduino_bridge import ArduinoStateBridge

# face_detection_codes/core/logger.py writes state here. Keep the project-level
# path as a fallback for older/manual runs, but always prefer the live file.
JSON_PATHS = [
    ROOT_DIR / "face_detection_codes" / "shared" / "driver_state.json",
    ROOT_DIR / "shared" / "driver_state.json",
]


def _read_driver_state():
    """Read the latest valid driver state from the shared JSON files."""
    for path in JSON_PATHS:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            state = str(data.get("driver_state", "")).strip().upper()
            if state in ArduinoStateBridge.VALID_STATES:
                return state
        except (OSError, ValueError, TypeError) as error:
            print(f"[Arduino Communicator] Could not read {path}: {error}")
    return None


def run_arduino_communicator():
    """Continuously send the latest shared driver state to the Arduino."""
    print("[INFO] Starting Arduino Communicator...")
    target_port = os.getenv("ARDUINO_PORT")
    bridge = ArduinoStateBridge(port=target_port)

    sent_state = None
    last_send_time = 0.0
    send_interval = 1.0

    try:
        if os.getenv("DRY_RUN") == "1":
            initial_state = _read_driver_state() or "NORMAL"
            bridge.send_state(initial_state)
            print("[INFO] Arduino Communicator dry-run completed successfully.")
            return

        while True:
            try:
                now = time.time()
                raw_state = _read_driver_state()

                # Do not turn a missing/invalid state into NORMAL on every loop.
                # Keep the last valid state until a new valid one appears.
                if raw_state in ArduinoStateBridge.VALID_STATES:
                    target_state = raw_state
                    time_since_last = now - last_send_time
                    if target_state != sent_state or time_since_last >= send_interval:
                        if bridge.send_state(target_state):
                            if target_state != sent_state:
                                print(
                                    f"[STATE CHANGE DETECTED] {sent_state} -> "
                                    f"{target_state}"
                                )
                            sent_state = target_state
                            last_send_time = now

                feedback = bridge.read_feedback()
                if feedback:
                    print(f"[Arduino Feedback]: {feedback}")

            except RuntimeError as error:
                print(f"[FATAL ARDUINO ERROR] {error}", file=sys.stderr)
                raise
            except Exception as error:
                print(f"[COMMUNICATOR LOOP ERROR] {error}")

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("[INFO] Arduino Communicator stopped by user.")
    finally:
        bridge.close()
        print("[INFO] Arduino Communicator finished cleanup.")


if __name__ == "__main__":
    run_arduino_communicator()
