import os
import sys
import time

try:
    import serial
    import serial.tools.list_ports as list_ports
except ImportError:
    serial = None
    list_ports = None


class ArduinoStateBridge:
    """Serial communication bridge sending driver state updates to Arduino."""

    VALID_STATES = {"NORMAL", "DROWSY", "UNRESPONSIVE"}
    STATE_ALIASES = {
        "N": "NORMAL",
        "D": "DROWSY",
        "U": "UNRESPONSIVE",
    }

    def __init__(self, port=None, baudrate=9600, timeout=1):
        """Initialize serial connection (adjusts port automatically if not specified)."""
        self.baudrate = baudrate
        self.timeout = timeout
        self.port = self._resolve_port(port)
        self.ser = None

        if os.getenv("DRY_RUN") == "1":
            print(f"[ArduinoStateBridge] DRY_RUN mode active. Operating in simulation mode on {self.port}.")
            return

        self._connect()

    def _resolve_port(self, port):
        """Determine target serial port from argument, env variable, or system auto-discovery."""
        if port:
            return port

        env_port = os.getenv("ARDUINO_PORT")
        if env_port:
            return env_port.strip()

        # Try auto-detecting connected serial ports
        if list_ports is not None:
            try:
                available = list(list_ports.comports())
                if available:
                    # Prefer USB serial or FTDI / Arduino devices
                    for p in available:
                        desc = (p.description or "").lower()
                        hwid = (p.hwid or "").lower()
                        if any(k in desc or k in hwid for k in ["usb", "arduino", "ftdi", "ch340", "cp210"]):
                            return p.device
                    # Otherwise return the first available port
                    return available[0].device
            except Exception as e:
                print(f"[ArduinoStateBridge] Auto-detection warning: {e}")

        # Default fallback
        return "COM8" if sys.platform == "win32" else "/dev/ttyUSB0"

    def _connect(self):
        """Connect or reconnect to the serial port, raising RuntimeError on failure."""
        if serial is None:
            raise RuntimeError(
                "[ArduinoStateBridge] 'pyserial' package is not installed. "
                "Install it using: pip install pyserial"
            )

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(2)  # Allow time for Arduino auto-reset
            print(f"[ArduinoStateBridge] Connected to Arduino on {self.port} at {self.baudrate} baud.")
            return True
        except Exception as e:
            self.ser = None
            raise RuntimeError(
                f"[ArduinoStateBridge] Failed to open Arduino serial port '{self.port}' at {self.baudrate} baud: {e}. "
                "Ensure the microcontroller is connected, ARDUINO_PORT is configured, "
                "and no other program (e.g. Serial Monitor or another process) is blocking the port."
            ) from e

    def send_state(self, state_name):
        """Sends a target state command (NORMAL, DROWSY, UNRESPONSIVE) to the Arduino."""
        if not state_name:
            print("[Error]: State name cannot be empty")
            return False

        clean_state = str(state_name).strip().upper()
        # Resolve single-letter aliases (N, D, U) if provided
        clean_state = self.STATE_ALIASES.get(clean_state, clean_state)

        if clean_state in self.VALID_STATES:
            command = f"{clean_state}\n"
            if self.ser is not None and getattr(self.ser, "is_open", False):
                try:
                    self.ser.write(command.encode("utf-8"))
                    self.ser.flush()
                    print(f"[Sent to Arduino]: {clean_state}")
                    return True
                except Exception as e:
                    raise RuntimeError(
                        f"[ArduinoStateBridge] Write error sending '{clean_state}' on '{self.port}': {e}"
                    ) from e
            elif os.getenv("DRY_RUN") == "1":
                # Explicit simulation fallback during test/dry-run mode
                print(f"[Sent to Arduino (DRY_RUN)]: {clean_state}")
                return True
            else:
                raise RuntimeError(
                    f"[ArduinoStateBridge] Cannot send state '{clean_state}': serial port '{self.port}' is closed or not connected."
                )
        else:
            print(f"[Error]: Invalid state '{state_name}'")
            return False

    def read_feedback(self):
        """Reads status responses or ACK confirmations from Arduino."""
        if self.ser is not None and getattr(self.ser, "is_open", False):
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8", errors="replace").strip()
                    return line if line else None
            except Exception as e:
                raise RuntimeError(
                    f"[ArduinoStateBridge] Error reading feedback on port '{self.port}': {e}"
                ) from e
        return None

    def close(self):
        """Safely close the serial connection."""
        if self.ser is not None:
            try:
                if getattr(self.ser, "is_open", False):
                    self.ser.close()
                    print(f"[ArduinoStateBridge] Serial port {self.port} closed.")
            except Exception as e:
                print(f"[ArduinoStateBridge Close Error]: {e}")
            finally:
                self.ser = None


# --- Example Usage ---
if __name__ == "__main__":
    target_port = os.getenv("ARDUINO_PORT", "COM8")
    bridge = ArduinoStateBridge(port=target_port)

    try:
        # Example sequence testing the driver states
        bridge.send_state("NORMAL")
        time.sleep(2)

        bridge.send_state("DROWSY")
        time.sleep(2)

        bridge.send_state("UNRESPONSIVE")
        time.sleep(2)

        # Check for any feedback
        ack = bridge.read_feedback()
        if ack:
            print(f"[Arduino Feedback]: {ack}")

    finally:
        bridge.close()

