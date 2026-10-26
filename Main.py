import os
import sys
import time

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# The face-detection process owns the Arduino serial connection and sends
# its current classifier state directly through core.arduino_client.
# Do NOT start arduino.main.main_aur() here: that opens the same COM port
# and reads a different/stale JSON state file.
from subprocess_launcher import (
    start_face_detection,
    stop_face_detection,
    is_face_detection_running,
)


def main():
    print("=" * 60)
    print("[SYSTEM] Starting Driver Monitoring System")
    print("=" * 60)

    driver_id = os.getenv("DRIVER_ID")
    if not driver_id and sys.stdin.isatty():
        try:
            driver_id = input(
                "\nEnter Driver ID / Employee ID (e.g. 007, driver_1): "
            ).strip()
        except (EOFError, OSError):
            driver_id = None

    if not driver_id:
        driver_id = os.getenv("DRIVER_ID", "default_driver")

    print(f"[INFO] Active Driver ID: {driver_id}")

    try:
        start_face_detection(driver_id=driver_id)
        print(
            "[INFO] Arduino serial communication is handled by the "
            "face-detection process."
        )
        while is_face_detection_running():
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C detected. Shutting down...")

    except Exception as error:
        print(f"[ERROR] MAIN SYSTEM ERROR: {error}")

    finally:
        stop_face_detection()
        print("[INFO] Cleanup done. Exiting.")


if __name__ == "__main__":
    main()
