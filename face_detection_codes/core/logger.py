import json
import time
from pathlib import Path

# Universal root path
MODULE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = MODULE_DIR.parent

# Shared folder paths - support both module-level and root-level shared folders
STATE_JSON_PATHS = [
    MODULE_DIR / "shared" / "driver_state.json",
    ROOT_DIR / "shared" / "driver_state.json",
]
SCORES_JSON_PATHS = [
    MODULE_DIR / "shared" / "all_scores.json",
    ROOT_DIR / "shared" / "all_scores.json",
]

# Write timers
last_state_write = 0
last_score_write = 0

STATE_WRITE_INTERVAL = 1.0     # seconds
SCORE_WRITE_INTERVAL = 0.5     # seconds


# -----------------------------------
# Driver state logger
# -----------------------------------
def write_state_periodically(data):
    global last_state_write

    current_time = time.time()

    if current_time - last_state_write < STATE_WRITE_INTERVAL:
        return

    last_state_write = current_time

    for state_path in STATE_JSON_PATHS:
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(state_path, "w") as f:
                json.dump(data, f, indent=4)
                f.flush()
        except Exception as e:
            print(f"[STATE LOGGER ERROR for {state_path}]: {e}")

    print(f"[STATE LOGGER] {data}")


# -----------------------------------
# Drowsiness metrics logger
# -----------------------------------
def write_scores_periodically(metrics):
    global last_score_write

    current_time = time.time()

    if current_time - last_score_write < SCORE_WRITE_INTERVAL:
        return

    last_score_write = current_time

    for score_path in SCORES_JSON_PATHS:
        try:
            score_path.parent.mkdir(parents=True, exist_ok=True)
            with open(score_path, "w") as f:
                json.dump(metrics, f, indent=4)
                f.flush()
        except Exception as e:
            print(f"[SCORE LOGGER ERROR for {score_path}]: {e}")

    print(f"[SCORE LOGGER] {metrics}")