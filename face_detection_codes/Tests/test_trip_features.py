from datetime import datetime, timedelta, timezone

import pytest

from DriverScore.models import TripContext
from DriverScore.trip_features import TripFeatureExtractor


BASE = datetime(2026, 8, 21, 10, 0, 0)


def make_context(minutes=10):
    return TripContext(
        trip_id="trip-1",
        driver_id="driver-1",
        trip_start=BASE,
        trip_end=BASE + timedelta(minutes=minutes),
    )


def metric(seconds, **values):
    return {
        "created_at": BASE + timedelta(seconds=seconds),
        **values,
    }


def test_invalid_trip_duration_raises():
    context = TripContext(
        trip_id="trip-1",
        driver_id="driver-1",
        trip_start=BASE,
        trip_end=BASE,
    )

    with pytest.raises(ValueError):
        TripFeatureExtractor().extract(
            context,
            [],
            [],
            [],
        )


def test_trip_features_have_calculated_at():
    context = make_context()

    features = TripFeatureExtractor().extract(
        context,
        [],
        [],
        [],
    )

    assert features.calculated_at == context.trip_end.replace(
        tzinfo=timezone.utc
    )
    assert context.trip_end.tzinfo is None


def test_driver_rows_outside_trip_are_ignored():
    context = make_context()

    rows = [
        {
            "created_at": BASE - timedelta(seconds=10),
            "perclos": 0.90,
        },
        metric(10, perclos=0.10),
        {
            "created_at": context.trip_end + timedelta(seconds=10),
            "perclos": 0.90,
        },
    ]

    features = TripFeatureExtractor().extract(
        context,
        rows,
        [],
        [],
    )

    assert features.avg_perclos == pytest.approx(0.10)


def test_drowsy_and_unresponsive_temporal_features():
    context = make_context(minutes=1)

    rows = [
        metric(0, driver_state="NORMAL", perclos=0.10),
        metric(10, driver_state="DROWSY", perclos=0.25),
        metric(20, driver_state="DROWSY", perclos=0.25),
        metric(30, driver_state="NORMAL", perclos=0.10),
        metric(40, driver_state="UNRESPONSIVE", perclos=0.35),
        metric(50, driver_state="NORMAL", perclos=0.10),
    ]

    features = TripFeatureExtractor().extract(
        context,
        rows,
        [],
        [],
    )

    assert features.drowsy_seconds == pytest.approx(20.0)
    assert features.drowsy_episode_count == 1
    assert features.avg_drowsy_episode_duration == pytest.approx(20.0)
    assert features.max_drowsy_episode_duration == pytest.approx(20.0)

    assert features.unresponsive_seconds == pytest.approx(10.0)
    assert features.unresponsive_episode_count == 1
    assert features.unresponsive_rate == pytest.approx(60.0)


def test_cumulative_yawn_counter_is_not_summed_per_row():
    context = make_context(minutes=1)

    rows = [
        metric(0, yawn_count=0, avg_yawn_duration=0.0),
        metric(10, yawn_count=1, avg_yawn_duration=1.5),
        metric(20, yawn_count=1, avg_yawn_duration=1.5),
        metric(30, yawn_count=3, avg_yawn_duration=1.8),
        metric(40, yawn_count=3, avg_yawn_duration=1.8),
    ]

    features = TripFeatureExtractor().extract(
        context,
        rows,
        [],
        [],
    )

    assert features.yawn_count == 3
    assert features.yawn_rate == pytest.approx(180.0)
    assert features.avg_yawn_duration == pytest.approx(1.8)


def test_cumulative_microsleep_counter_and_max_duration():
    context = make_context(minutes=1)

    rows = [
        metric(
            0,
            microsleep_count=0,
            avg_microsleep_duration=0.0,
            microsleep_detected=False,
            continuous_eye_closure=0.0,
        ),
        metric(
            10,
            microsleep_count=1,
            avg_microsleep_duration=2.5,
            microsleep_detected=True,
            continuous_eye_closure=2.5,
        ),
        metric(
            20,
            microsleep_count=1,
            avg_microsleep_duration=2.5,
            microsleep_detected=True,
            continuous_eye_closure=3.2,
        ),
        metric(
            30,
            microsleep_count=2,
            avg_microsleep_duration=3.0,
            microsleep_detected=True,
            continuous_eye_closure=3.0,
        ),
    ]

    features = TripFeatureExtractor().extract(
        context,
        rows,
        [],
        [],
    )

    assert features.microsleep_count == 2
    assert features.microsleep_rate == pytest.approx(120.0)
    assert features.avg_microsleep_duration == pytest.approx(3.0)
    assert features.max_microsleep_duration == pytest.approx(3.2)


def test_baseline_blink_deviation():
    context = make_context(minutes=1)

    rows = [
        metric(0, blink_rate=20, perclos=0.10),
        metric(30, blink_rate=10, perclos=0.10),
    ]

    features = TripFeatureExtractor().extract(
        context,
        rows,
        [],
        [],
        baseline={"blink_rate_mean": 20},
    )

    assert features.avg_blink_rate == pytest.approx(15.0)
    assert features.blink_deviation == pytest.approx(0.25)


def test_vehicle_features_are_extracted():
    context = make_context(minutes=1)

    rows = [
        metric(0, speed=40, throttle=20, brake=5, steering=1),
        metric(30, speed=60, throttle=30, brake=10, steering=3),
    ]

    features = TripFeatureExtractor().extract(
        context,
        [],
        rows,
        [],
    )

    assert features.avg_speed == pytest.approx(50.0)
    assert features.max_speed == pytest.approx(60.0)
    assert features.avg_throttle == pytest.approx(25.0)
    assert features.avg_brake == pytest.approx(7.5)
    assert features.steering_variability == pytest.approx(1.0)


def test_emergency_severity_is_converted_to_risk():
    context = make_context(minutes=1)

    events = [
        metric(10, severity="low", event_type="test"),
        metric(20, severity="high", event_type="test"),
        metric(30, severity="critical", event_type="test"),
    ]

    features = TripFeatureExtractor().extract(
        context,
        [],
        [],
        events,
    )

    assert features.emergency_count == 3
    assert features.emergency_rate == pytest.approx(180.0)
    assert features.emergency_risk_rate == pytest.approx(780.0)


def test_empty_input_returns_missing_optional_features():
    context = make_context()

    features = TripFeatureExtractor().extract(
        context,
        [],
        [],
        [],
    )

    assert features.avg_perclos is None
    assert features.yawn_count is None
    assert features.microsleep_count is None
    assert features.distraction_count is None
    assert features.emergency_count == 0
    assert features.driver_data_coverage == 0.0
    assert features.vehicle_data_coverage == 0.0


def test_naive_context_boundaries_accept_aware_utc_telemetry():
    context = make_context(minutes=1)
    rows = [
        {
            "created_at": BASE.replace(tzinfo=timezone.utc)
            + timedelta(seconds=30),
            "perclos": 0.10,
        }
    ]

    features = TripFeatureExtractor().extract(
        context,
        rows,
        [],
        [],
    )

    assert features.avg_perclos == pytest.approx(0.10)
    assert context.trip_start.tzinfo is None


def test_z_and_nonzero_offset_timestamps_are_normalized_to_utc():
    context = TripContext(
        trip_id="trip-1",
        driver_id="driver-1",
        trip_start=datetime(
            2026, 8, 21, 10, 0, 0,
            tzinfo=timezone.utc,
        ),
        trip_end=datetime(
            2026, 8, 21, 10, 1, 0,
            tzinfo=timezone.utc,
        ),
    )
    rows = [
        {
            "created_at": "2026-08-21T10:00:10Z",
            "perclos": 0.10,
        },
        {
            "created_at": "2026-08-21T12:00:20+02:00",
            "perclos": 0.20,
        },
    ]

    features = TripFeatureExtractor().extract(
        context,
        rows,
        [],
        [],
    )

    assert features.avg_perclos == pytest.approx(0.18)


def test_naive_telemetry_timestamp_is_interpreted_as_utc():
    context = TripContext(
        trip_id="trip-1",
        driver_id="driver-1",
        trip_start=datetime(
            2026, 8, 21, 10, 0, 0,
            tzinfo=timezone.utc,
        ),
        trip_end=datetime(
            2026, 8, 21, 10, 1, 0,
            tzinfo=timezone.utc,
        ),
    )
    rows = [
        {
            # Naive telemetry timestamps are explicitly interpreted as UTC.
            "created_at": datetime(2026, 8, 21, 10, 0, 30),
            "perclos": 0.10,
        }
    ]

    features = TripFeatureExtractor().extract(
        context,
        rows,
        [],
        [],
    )

    assert features.avg_perclos == pytest.approx(0.10)


def test_negative_offset_timestamp_inside_trip_is_included():
    context = TripContext(
        trip_id="trip-1",
        driver_id="driver-1",
        trip_start=datetime(
            2026, 8, 21, 10, 0, 0,
            tzinfo=timezone.utc,
        ),
        trip_end=datetime(
            2026, 8, 21, 10, 1, 0,
            tzinfo=timezone.utc,
        ),
    )
    rows = [
        {
            "created_at": "2026-08-21T05:00:30-05:00",
            "perclos": 0.10,
        }
    ]

    features = TripFeatureExtractor().extract(
        context,
        rows,
        [],
        [],
    )

    assert features.avg_perclos == pytest.approx(0.10)


def test_missing_and_invalid_timestamps_are_skipped():
    rows = [
        {"perclos": 0.10},
        {"created_at": "invalid", "perclos": 0.20},
        metric(30, perclos=0.30),
    ]

    features = TripFeatureExtractor().extract(
        make_context(minutes=1),
        rows,
        [],
        [],
    )

    assert features.avg_perclos == pytest.approx(0.30)


def test_trip_boundaries_are_inclusive_and_outside_rows_are_excluded():
    context = make_context(minutes=1)
    rows = [
        metric(0, perclos=0.10),
        metric(60, perclos=0.20),
        {
            "created_at": BASE - timedelta(microseconds=1),
            "perclos": 0.90,
        },
        {
            "created_at": context.trip_end + timedelta(microseconds=1),
            "perclos": 0.90,
        },
    ]

    features = TripFeatureExtractor().extract(
        context,
        rows,
        [],
        [],
    )

    assert features.avg_perclos == pytest.approx(0.10)