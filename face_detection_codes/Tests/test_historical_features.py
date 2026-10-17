from datetime import datetime, timedelta

import pytest

from DriverScore.historical_features import HistoricalFeatureEngine
from DriverScore.models import TripFeatures


BASE = datetime(2026, 8, 21, 10, 0, 0)


def make_trip(
    trip_id,
    duration_hours,
    calculated_at,
    avg_perclos=0.10,
    yawn_count=2,
    microsleep_count=1,
    drowsy_episode_count=1,
    unresponsive_episode_count=0,
    distraction_count=2,
    distracted_time_pct=1.0,
    emergency_risk_rate=2.0,
):
    return TripFeatures(
        trip_id=trip_id,
        driver_id="driver-1",
        calculated_at=calculated_at,
        duration_seconds=duration_hours * 3600,
        duration_hours=duration_hours,
        avg_perclos=avg_perclos,
        high_perclos_seconds=0.0,
        high_perclos_time_pct=5.0,
        drowsy_seconds=100.0,
        drowsy_time_pct=10.0,
        drowsy_episode_count=drowsy_episode_count,
        drowsy_episode_rate=drowsy_episode_count / duration_hours,
        avg_drowsy_episode_duration=100.0,
        max_drowsy_episode_duration=100.0,
        unresponsive_seconds=0.0,
        unresponsive_time_pct=0.0,
        unresponsive_episode_count=unresponsive_episode_count,
        unresponsive_rate=unresponsive_episode_count / duration_hours,
        avg_blink_rate=15.0,
        blink_deviation=0.1,
        yawn_count=yawn_count,
        yawn_rate=yawn_count / duration_hours,
        avg_yawn_duration=1.5,
        microsleep_count=microsleep_count,
        microsleep_rate=microsleep_count / duration_hours,
        avg_microsleep_duration=2.5,
        max_microsleep_duration=3.0,
        distraction_count=distraction_count,
        distraction_rate=distraction_count / duration_hours,
        distracted_seconds=20.0,
        distracted_time_pct=distracted_time_pct,
        emergency_count=1,
        emergency_rate=1 / duration_hours,
        emergency_risk_rate=emergency_risk_rate,
        avg_speed=50.0,
        max_speed=70.0,
        avg_throttle=20.0,
        avg_brake=5.0,
        steering_variability=1.0,
        driver_data_coverage=1.0,
        vehicle_data_coverage=1.0,
    )


def test_empty_history_raises():
    with pytest.raises(ValueError):
        HistoricalFeatureEngine().aggregate([], BASE)


def test_historical_engine_uses_calculated_at():
    trip = make_trip(
        "trip-1",
        1.0,
        BASE - timedelta(days=1),
    )

    result = HistoricalFeatureEngine().aggregate(
        [trip],
        BASE,
    )

    assert result.trips_analyzed == 1
    assert result.driving_hours_analyzed == pytest.approx(1.0)
    assert result.avg_perclos == pytest.approx(0.10)


def test_historical_engine_normalizes_iso_calculated_at():
    trip = make_trip(
        "trip-1",
        1.0,
        "2026-08-20T10:00:00Z",
    )

    result = HistoricalFeatureEngine().aggregate(
        [trip],
        datetime(2026, 8, 21, 10, 0, 0),
    )

    assert result.trips_analyzed == 1


def test_historical_engine_normalizes_fractional_second_timestamp():
    trip = make_trip(
        "trip-1",
        1.0,
        "2026-10-16T07:52:32.98796+00:00",
    )

    result = HistoricalFeatureEngine().aggregate(
        [trip],
        datetime(2026, 10, 17, 7, 52, 32, tzinfo=None),
    )

    assert result.trips_analyzed == 1


def test_event_rates_are_derived_from_history():
    trips = [
        make_trip(
            "trip-1",
            1.0,
            BASE - timedelta(days=1),
            yawn_count=2,
            microsleep_count=1,
        ),
        make_trip(
            "trip-2",
            2.0,
            BASE - timedelta(days=2),
            yawn_count=4,
            microsleep_count=2,
        ),
    ]

    result = HistoricalFeatureEngine().aggregate(
        trips,
        BASE,
    )

    assert result.yawn_rate is not None
    assert result.yawn_rate > 0

    assert result.microsleep_rate is not None
    assert result.microsleep_rate > 0

    assert result.drowsy_episode_rate > 0
    assert result.distracted_time_pct == pytest.approx(1.0)
    assert result.emergency_risk_rate is not None


def test_distracted_time_pct_is_preserved_for_one_trip():
    trip = make_trip(
        "trip-1",
        1.0,
        BASE - timedelta(days=1),
        distracted_time_pct=3.5,
    )

    result = HistoricalFeatureEngine().aggregate([trip], BASE)

    assert result.distracted_time_pct == pytest.approx(3.5)


def test_distracted_time_pct_is_duration_weighted_across_trips():
    trips = [
        make_trip(
            "short",
            1.0,
            BASE,
            distracted_time_pct=2.0,
        ),
        make_trip(
            "long",
            3.0,
            BASE,
            distracted_time_pct=6.0,
        ),
    ]

    result = HistoricalFeatureEngine(
        recency_lambda=0.0
    ).aggregate(trips, BASE)

    assert result.distracted_time_pct == pytest.approx(5.0)


def test_distracted_time_pct_is_none_when_all_values_are_null():
    trips = [
        make_trip(
            "trip-1",
            1.0,
            BASE,
            distracted_time_pct=None,
        ),
        make_trip(
            "trip-2",
            2.0,
            BASE,
            distracted_time_pct=None,
        ),
    ]

    result = HistoricalFeatureEngine(
        recency_lambda=0.0
    ).aggregate(trips, BASE)

    assert result.distracted_time_pct is None


def test_distracted_time_pct_ignores_null_values_when_mixed():
    trips = [
        make_trip(
            "null-trip",
            1.0,
            BASE,
            distracted_time_pct=None,
        ),
        make_trip(
            "value-trip",
            3.0,
            BASE,
            distracted_time_pct=4.0,
        ),
    ]

    result = HistoricalFeatureEngine(
        recency_lambda=0.0
    ).aggregate(trips, BASE)

    assert result.distracted_time_pct == pytest.approx(4.0)


def test_recent_trip_has_more_recency_weight():
    trips = [
        make_trip(
            "old",
            1.0,
            BASE - timedelta(days=100),
            avg_perclos=0.30,
        ),
        make_trip(
            "recent",
            1.0,
            BASE - timedelta(days=1),
            avg_perclos=0.10,
        ),
    ]

    result = HistoricalFeatureEngine(
        recency_lambda=0.05
    ).aggregate(trips, BASE)

    assert result.avg_perclos < 0.20


def test_max_microsleep_duration_is_preserved():
    trips = [
        make_trip(
            "trip-1",
            1.0,
            BASE - timedelta(days=1),
        ),
        make_trip(
            "trip-2",
            1.0,
            BASE - timedelta(days=2),
        ),
    ]

    trips[1].max_microsleep_duration = 7.5

    result = HistoricalFeatureEngine().aggregate(
        trips,
        BASE,
    )

    assert result.max_microsleep_duration == pytest.approx(7.5)