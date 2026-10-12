from unittest.mock import Mock

from backend import push_metrics
from backend.database_writer import DatabaseWriter


def test_update_live_driver_state_uses_driver_id_not_singleton_row():
    client = Mock()
    table = Mock()
    client.table.return_value = table
    table.update.return_value = table
    table.eq.return_value = table
    table.execute.return_value = Mock(data=[{"id": 1}])

    writer = DatabaseWriter(client)
    writer.update_live_driver_state(
        {"ear": 0.2, "perclos": 0.3, "blink_rate": 12, "drowsiness_score": 55, "avg_closure_duration": 0.4},
        "driver-123",
        "DROWSY",
    )

    table.update.assert_called_once()
    payload = table.update.call_args[0][0]
    assert payload["driver_id"] == "driver-123"
    assert payload["driver_state"] == "DROWSY"
    table.eq.assert_called_once_with("driver_id", "driver-123")


def test_push_driver_metrics_writes_historical_sample_and_only_emits_event_on_transition(monkeypatch):
    writer = Mock()
    monkeypatch.setattr(push_metrics, "database_writer", writer)
    push_metrics.last_push_time = 0
    push_metrics.last_metric_write_time = 0
    push_metrics.last_payload = {}
    push_metrics.last_event_state = None

    push_metrics.push_driver_metrics(
        {
            "ear": 0.18,
            "perclos": 0.44,
            "blink_rate": 6,
            "drowsiness_score": 88,
            "avg_closure_duration": 1.8,
        },
        "UNRESPONSIVE",
        driver_id="driver-123",
        trip_id="trip-456",
    )

    writer.update_live_driver_state.assert_called_once()
    writer.write_driver_metrics.assert_called_once_with(
        {
            "ear": 0.18,
            "perclos": 0.44,
            "blink_rate": 6,
            "drowsiness_score": 88,
            "avg_closure_duration": 1.8,
        },
        "driver-123",
        "trip-456",
        "UNRESPONSIVE",
    )
    writer.write_event.assert_called_once()
    event_payload = writer.write_event.call_args.kwargs
    assert event_payload["event_type"] == "UNRESPONSIVE"
    assert event_payload["driver_id"] == "driver-123"
    assert event_payload["trip_id"] == "trip-456"
    assert event_payload["metadata"].get("frame_url") is None
