import subprocess
import signal
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

from System_paths_config import face_python, face_main 
face_process = None




def start_face_detection():
    global face_process

    print("👉 Launching face detection subprocess...")

    try:
        import os
        kwargs = {}
        # Only use CREATE_NEW_CONSOLE if not headless / dry-run
        is_headless = os.getenv("HEADLESS") == "1" or os.getenv("DRY_RUN") == "1"
        if os.name == "nt" and not is_headless:
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

        env = os.environ.copy()
        face_dir = str(face_main.parent)
        env["PYTHONPATH"] = face_dir + os.pathsep + env.get("PYTHONPATH", "")
        env.setdefault("DRIVER_ID", "default_driver")

        face_process = subprocess.Popen(
            [
                str(face_python),
                str(face_main)
            ],
            cwd=face_dir,
            env=env,
            **kwargs
        )

        # Give it a moment to fail if it's going to
        wait_seconds = 2 if is_headless else 4
        time.sleep(wait_seconds)

        if face_process.poll() is not None:
            raise RuntimeError(f"Face detection subprocess crashed immediately with exit code {face_process.poll()}")

        print("🧠 Face detection subprocess started")

    except Exception as e:
        print(f"❌ Failed to start face detection: {e}")
        face_process = None
        raise


def stop_face_detection():
    global face_process

    if face_process is not None:
        print("🛑 Stopping face detection...")
        try:
            face_process.terminate()
            face_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("⚠️ Force killing face detection...")
            face_process.kill()
            face_process.wait(timeout=2)
        except Exception as e:
            print(f"⚠️ Error stopping face detection: {e}")
        finally:
            face_process = None


def is_face_detection_running():
    global face_process
    return face_process is not None and face_process.poll() is None