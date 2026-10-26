import os
import sys
import threading
import time
from pathlib import Path

# Ensure root directory is on sys.path for importing the arduino package
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from arduino.arduino_bridge import ArduinoStateBridge
except ImportError:
    ArduinoStateBridge = None


class ArduinoCommunicator:
    """Non-blocking background thread that connects to Arduino and continuously
    streams the latest driver state to the Arduino Serial Monitor.
    """

    def __init__(self, port=None, baudrate=9600, send_interval=1.0):
        self.port = port
        self.baudrate = baudrate
        self.send_interval = send_interval
        self.bridge = None
        self._current_state = "NORMAL"
        self._last_sent_state = None
        self._last_send_time = 0.0
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

    def update_state(self, new_state):
        """Update active driver state (thread-safe, zero I/O blocking for CV loop)."""
        clean = str(new_state).strip().upper()
        if clean in {"CALIBRATING", "WAITING", "IDLE"}:
            mapped = "NORMAL"
        elif clean in {"NORMAL", "DROWSY", "UNRESPONSIVE"}:
            mapped = clean
        else:
            mapped = "NORMAL"

        with self._state_lock:
            self._current_state = mapped

    def start(self):
        """Start the background streaming worker thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="ArduinoCommunicatorThread",
        )
        self._thread.start()
        print("[INFO] Arduino Communicator background thread started.")

    def _worker_loop(self):
        if ArduinoStateBridge is None:
            raise RuntimeError("[Arduino Communicator] ArduinoStateBridge is not available.")

        target_port = self.port or os.getenv("ARDUINO_PORT")
        try:
            self.bridge = ArduinoStateBridge(port=target_port, baudrate=self.baudrate)
        except RuntimeError as err:
            print(f"\n[FATAL ARDUINO SERIAL ERROR] {err}\n", file=sys.stderr)
            raise

        while not self._stop_event.is_set():
            try:
                now = time.time()
                with self._state_lock:
                    target_state = self._current_state

                # Send immediately on state transition, or send at regular heartbeat interval
                time_since_last_send = now - self._last_send_time
                state_changed = target_state != self._last_sent_state
                interval_elapsed = time_since_last_send >= self.send_interval

                if state_changed or interval_elapsed:
                    if self.bridge.send_state(target_state):
                        self._last_sent_state = target_state
                        self._last_send_time = now

                # Read any serial monitor feedback from Arduino non-blockingly
                feedback = self.bridge.read_feedback()
                if feedback:
                    print(f"[Arduino Feedback]: {feedback}")

            except RuntimeError as err:
                print(f"\n[FATAL ARDUINO SERIAL ERROR] Communication failure on {target_port}: {err}\n", file=sys.stderr)
                raise
            except Exception as err:
                print(f"[Arduino Communicator Worker Error]: {err}")

            time.sleep(0.05)

    def close(self):
        """Stop worker thread and safely close serial connection."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self.bridge:
            self.bridge.close()
            self.bridge = None
        print("[INFO] Arduino Communicator stopped and port released.")
