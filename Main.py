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

# from carla_codes.main import run_carla
from subprocess_launcher import start_face_detection, stop_face_detection


def main():
    print("🚀 Starting Driver Monitoring System")

    try:
        start_face_detection()

        from subprocess_launcher import is_face_detection_running
        while is_face_detection_running():
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Ctrl+C detected. Shutting down...")

    except Exception as e:
        print("💥 MAIN SYSTEM ERROR:", e)

    finally:
        stop_face_detection()
        print("🧹 Cleanup done. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()