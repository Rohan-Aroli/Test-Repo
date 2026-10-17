from unittest.mock import Mock

import httpx
import pytest

from backend import push_metrics
from backend.database_writer import DatabaseUnavailableError, DatabaseWriter


def test_find_driver_retries_transient_transport_errors(monkeypatch):
    monkeypatch.setattr("backend.database_writer.sleep", lambda _: None)
    client = Mock()
    table = Mock()
    client.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.side_effect = [
        httpx.RemoteProtocolError("Server disconnected"),
        Mock(data=[{"employee_id": "driver-123"}]),
    ]

    assert DatabaseWriter(client).find_driver("driver-123") == {
        "employee_id": "driver-123"
    }
    assert table.execute.call_count == 2


def test_find_driver_raises_clear_error_after_transport_retries(monkeypatch):
    monkeypatch.setattr("backend.database_writer.sleep", lambda _: None)
    client = Mock()
    table = Mock()
    client.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.side_effect = httpx.RemoteProtocolError("Server disconnected")

    with pytest.raises(DatabaseUnavailableError, match="could not be reached"):
        DatabaseWriter(client).find_driver("driver-123")
    assert table.execute.call_count == 3


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


def test_write_driver_metrics_leaves_database_id_to_supabase():
    client = Mock()
    table = Mock()
    client.table.return_value = table
    table.insert.return_value = table

    DatabaseWriter(client).write_driver_metrics(
        {"ear": 0.2, "perclos": 0.3, "blink_rate": 12},
        "driver-123",
        "trip-456",
        "NORMAL",
    )

    payload = table.insert.call_args[0][0]
    assert "id" not in payload
    assert payload["driver_uuid"] == "driver-123"


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
    writer.write_emergency_event.assert_called_once()
    emergency_payload = writer.write_emergency_event.call_args.kwargs
    assert emergency_payload["event_type"] == "UNRESPONSIVE"
    assert emergency_payload["driver_id"] == "driver-123"
    assert emergency_payload["trip_id"] == "trip-456"
    event_payload = writer.write_event.call_args.kwargs
    assert event_payload["event_type"] == "UNRESPONSIVE"
    assert event_payload["driver_id"] == "driver-123"
    assert event_payload["trip_id"] == "trip-456"
    assert "frame_url" not in event_payload["metadata"]


def test_push_driver_metrics_includes_supplied_frame_url_in_event_metadata(
    monkeypatch,
):
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
        frame_url="https://example.test/frame.jpg",
        driver_id="driver-123",
        trip_id="trip-456",
    )

    event_payload = writer.write_event.call_args.kwargs
    assert (
        event_payload["metadata"]["frame_url"]
        == "https://example.test/frame.jpg"
    )


def test_push_driver_metrics_persists_live_score_after_event(monkeypatch):
    writer = Mock()
    score_callback = Mock(return_value=object())
    monkeypatch.setattr(push_metrics, "database_writer", writer)
    monkeypatch.setattr(push_metrics, "score_callback", score_callback)
    push_metrics.last_push_time = 0
    push_metrics.last_metric_write_time = 0
    push_metrics.last_payload = {}
    push_metrics.last_event_state = None

    push_metrics.push_driver_metrics(
        {"ear": 0.18, "perclos": 0.44, "blink_rate": 6},
        "DROWSY",
        driver_id="driver-123",
        trip_id="trip-456",
    )

    score_callback.assert_called_once_with("driver-123", "trip-456")
