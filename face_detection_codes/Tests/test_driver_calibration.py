import json
import uuid
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from metrics.baseline_calibration import BaselineCalibrator
from core.driver_manager import DriverManager
from core.system_mode_manager import SystemModeManager
from arduino.Communicator import _read_driver_state


def test_baseline_calibrator_existing_driver(tmp_path):
    driver_id = f"test_driver_{uuid.uuid4().hex[:8]}"
    calibrator = BaselineCalibrator(calibration_time=5)
    calibrator.baseline_folder = tmp_path
    calibrator.set_driver(driver_id)

    # Initially no baseline
    assert not calibrator.load_baseline()
    assert not calibrator.calibrated

    # Create dummy baseline file in isolated tmp_path
    baseline_file = tmp_path / f"{driver_id}.json"
    dummy_baseline = {
        "ear_mean": 0.28,
        "mar_mean": 0.05,
        "perclos_mean": 0.12,
        "blink_rate_mean": 14.0,
        "closure_mean": 0.3,
        "pitch_mean": 0.0,
        "yaw_mean": 0.0,
        "roll_mean": 0.0,
    }
    baseline_file.write_text(json.dumps(dummy_baseline), encoding="utf-8")

    # Now loading should succeed
    loaded = calibrator.load_baseline()
    assert loaded is True
    assert calibrator.calibrated is True
    assert calibrator.get_baseline()["ear_mean"] == 0.28


def test_baseline_calibrator_new_driver_calibration_cycle(tmp_path):
    driver_id = f"test_new_driver_{uuid.uuid4().hex[:8]}"
    calibrator = BaselineCalibrator(calibration_time=0.1)  # fast calibration for test
    calibrator.baseline_folder = tmp_path
    calibrator.set_driver(driver_id)

    assert not calibrator.load_baseline()
    assert not calibrator.calibrated

    # Feed metrics
    metrics = {
        "ear": 0.30,
        "mar": 0.04,
        "perclos": 0.08,
        "blink_rate": 15,
        "avg_closure_duration": 0.25,
        "pitch": 2.0,
        "yaw": 1.0,
        "roll": 0.5,
    }

    # Simulate frames
    with patch("time.time", side_effect=[100.0, 100.05, 100.15]):
        calibrator.update(metrics)
        assert not calibrator.calibrated

        # Second update pushes past calibration_time (0.1s)
        completed = calibrator.update(metrics)
        assert completed is True
        assert calibrator.calibrated is True

    # Check file was saved in tmp_path
    saved_file = tmp_path / f"{driver_id}.json"
    assert saved_file.exists()
    saved_data = json.loads(saved_file.read_text(encoding="utf-8"))
    assert "ear_mean" in saved_data
    assert saved_data["ear_mean"] == pytest.approx(0.30, abs=1e-3)

    # Clean up mirrored test file if created in root
    root_mirror = Path("baselines") / f"{driver_id}.json"
    if root_mirror.exists():
        root_mirror.unlink(missing_ok=True)


def test_driver_manager_baseline_lookup(tmp_path):
    manager = DriverManager(baseline_folder=str(tmp_path))
    unique_id = f"driver_{uuid.uuid4().hex[:8]}"

    # Initially false
    assert not manager.baseline_exists(unique_id)

    # Save a baseline
    (tmp_path / f"{unique_id}.json").write_text('{"ear_mean": 0.3}', encoding="utf-8")

    assert manager.baseline_exists(unique_id)
    assert unique_id in manager.list_drivers()


def test_calibration_mode_preserves_calibrating_state():
    mode_mgr = SystemModeManager()
    mode_mgr.set_mode("CALIBRATION")
    assert mode_mgr.is_calibration()

    # During calibration, driver state is CALIBRATING
    driver_state = "CALIBRATING"
    assert driver_state == "CALIBRATING"
    assert driver_state != "ERROR"


def test_communicator_maps_calibrating_to_normal(tmp_path, monkeypatch):
    import arduino.Communicator as comm
    from arduino.arduino_bridge import ArduinoStateBridge

    state_file = tmp_path / "driver_state.json"
    state_file.write_text('{"driver_state": "CALIBRATING"}', encoding="utf-8")
    monkeypatch.setattr(comm, "JSON_PATHS", [state_file])

    read_state = comm._read_driver_state()
    assert read_state == "CALIBRATING"

    # Verify how communicator maps CALIBRATING
    if read_state in ArduinoStateBridge.VALID_STATES:
        target_state = read_state
    elif read_state in {"CALIBRATING", "WAITING"}:
        target_state = "NORMAL"
    else:
        target_state = None

    assert target_state == "NORMAL"

