import subprocess
import signal
import sys
import time
from System_paths_config import face_python, face_main 
face_process = None




def start_face_detection():
    global face_process

    print("👉 Launching face detection subprocess...")

    

    try:
        import os
        kwargs = {}
        if os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE

        face_process = subprocess.Popen(
            [
                face_python,
                face_main
            ],
            **kwargs
        )

        # Give it a moment to fail if it's going to
        time.sleep(4)

        if face_process.poll() is not None:
            raise RuntimeError("Face detection subprocess crashed immediately")

        print("🧠 Face detection subprocess started")

    except Exception as e:
        print(f"❌ Failed to start face detection: {e}")
        face_process = None
        raise




def stop_face_detection():
    global face_process

    if face_process is not None:
        print("🛑 Stopping face detection...")
        face_process.terminate()
        face_process.wait()

def is_face_detection_running():
    global face_process
    return face_process is not None and face_process.poll() is None