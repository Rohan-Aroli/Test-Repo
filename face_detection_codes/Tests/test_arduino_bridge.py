from unittest.mock import MagicMock, patch
import os
import sys
from pathlib import Path
import pytest

# Add project root and arduino directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "arduino") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "arduino"))

from arduino.arduino_bridge import ArduinoStateBridge
from arduino.Communicator import _read_driver_state


def test_send_valid_states():
    mock_ser = MagicMock()
    mock_ser.is_open = True

    with patch("serial.Serial", return_value=mock_ser):
        bridge = ArduinoStateBridge(port="COM_TEST")
        bridge.ser = mock_ser

        assert bridge.send_state("NORMAL") is True
        mock_ser.write.assert_called_with(b"NORMAL\n")
        mock_ser.flush.assert_called()

        assert bridge.send_state("DROWSY") is True
        mock_ser.write.assert_called_with(b"DROWSY\n")

        assert bridge.send_state("UNRESPONSIVE") is True
        mock_ser.write.assert_called_with(b"UNRESPONSIVE\n")

        bridge.close()
        mock_ser.close.assert_called_once()


def test_send_state_aliases():
    mock_ser = MagicMock()
    mock_ser.is_open = True

    with patch("serial.Serial", return_value=mock_ser):
        bridge = ArduinoStateBridge(port="COM_TEST")
        bridge.ser = mock_ser

        assert bridge.send_state("N") is True
        mock_ser.write.assert_called_with(b"NORMAL\n")

        assert bridge.send_state("d") is True
        mock_ser.write.assert_called_with(b"DROWSY\n")

        assert bridge.send_state("u") is True
        mock_ser.write.assert_called_with(b"UNRESPONSIVE\n")


def test_send_invalid_states():
    mock_ser = MagicMock()
    mock_ser.is_open = True

    with patch("serial.Serial", return_value=mock_ser):
        bridge = ArduinoStateBridge(port="COM_TEST")
        bridge.ser = mock_ser

        assert bridge.send_state("INVALID") is False
        assert bridge.send_state("") is False
        assert bridge.send_state(None) is False
        mock_ser.write.assert_not_called()


def test_read_feedback():
    mock_ser = MagicMock()
    mock_ser.is_open = True
    mock_ser.in_waiting = 5
    mock_ser.readline.return_value = b"ACK_NORMAL\r\n"

    with patch("serial.Serial", return_value=mock_ser):
        bridge = ArduinoStateBridge(port="COM_TEST")
        bridge.ser = mock_ser

        feedback = bridge.read_feedback()
        assert feedback == "ACK_NORMAL"

        mock_ser.in_waiting = 0
        assert bridge.read_feedback() is None


def test_port_blocked_or_missing_raises_runtime_error():
    with patch("serial.Serial", side_effect=Exception("Port unavailable or access denied")):
        with pytest.raises(RuntimeError) as exc_info:
            ArduinoStateBridge(port="COM_NONEXISTENT")
        assert "Failed to open Arduino serial port 'COM_NONEXISTENT'" in str(exc_info.value)


def test_serial_not_installed_raises_runtime_error():
    with patch("arduino.arduino_bridge.serial", None):
        with pytest.raises(RuntimeError) as exc_info:
            ArduinoStateBridge(port="COM_TEST")
        assert "'pyserial' package is not installed" in str(exc_info.value)


def test_send_state_disconnected_raises_runtime_error():
    mock_ser = MagicMock()
    mock_ser.is_open = True
    with patch("serial.Serial", return_value=mock_ser):
        bridge = ArduinoStateBridge(port="COM_TEST")
        bridge.ser = None
        with pytest.raises(RuntimeError) as exc_info:
            bridge.send_state("NORMAL")
        assert "serial port 'COM_TEST' is closed or not connected" in str(exc_info.value)


def test_dry_run_simulation(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    bridge = ArduinoStateBridge(port="COM_NONEXISTENT")
    assert bridge.ser is None
    assert bridge.send_state("NORMAL") is True
    assert bridge.read_feedback() is None
    bridge.close()


def test_read_driver_state(tmp_path):
    state_file = tmp_path / "driver_state.json"
    state_file.write_text('{"driver_state": "DROWSY"}', encoding="utf-8")

    with patch("arduino.Communicator.JSON_PATHS", [state_file]):
        state = _read_driver_state()
        assert state == "DROWSY"

