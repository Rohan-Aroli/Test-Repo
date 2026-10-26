import time
from unittest.mock import MagicMock, patch
import pytest

from core.arduino_client import ArduinoCommunicator


def test_arduino_communicator_state_mapping():
    comm = ArduinoCommunicator()
    comm.update_state("CALIBRATING")
    assert comm._current_state == "NORMAL"

    comm.update_state("DROWSY")
    assert comm._current_state == "DROWSY"

    comm.update_state("UNRESPONSIVE")
    assert comm._current_state == "UNRESPONSIVE"

    comm.update_state("RANDOM_INVALID")
    assert comm._current_state == "NORMAL"


def test_arduino_communicator_continuous_sending():
    comm = ArduinoCommunicator(send_interval=0.1)
    mock_bridge = MagicMock()
    mock_bridge.send_state.return_value = True
    mock_bridge.read_feedback.return_value = None

    with patch("core.arduino_client.ArduinoStateBridge", return_value=mock_bridge):
        comm.start()
        time.sleep(0.05)
        # Verify it started sending initial NORMAL
        comm.update_state("NORMAL")
        time.sleep(0.25)
        # Heartbeat should have triggered send_state at least twice in 0.25s with 0.1s interval
        assert mock_bridge.send_state.call_count >= 2

        # State transition triggers immediate send
        initial_calls = mock_bridge.send_state.call_count
        comm.update_state("DROWSY")
        time.sleep(0.08)
        assert mock_bridge.send_state.call_count > initial_calls
        mock_bridge.send_state.assert_any_call("DROWSY")

        comm.close()
        assert not comm._thread.is_alive()
        mock_bridge.close.assert_called_once()

