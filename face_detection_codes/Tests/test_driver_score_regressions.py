import ast
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path

import pytest

from DriverScore.db_repository import ScoreRepository
from DriverScore.models import (
    FinalizationResult,
    TripContext,
    TripFeatures,
)
from DriverScore.scoring_pipeline import ScoringPipeline


def load_finalize_trip_score():
    source_path = (
        Path(__file__).resolve().parents[1] / "main.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "finalize_trip_score"
    )
    namespace = {
        "FinalizationResult": FinalizationResult,
    }
    exec(
        compile(
            ast.Module(body=[function], type_ignores=[]),
            str(source_path),
            "exec",
        ),
        namespace,
    )
    return namespace["finalize_trip_score"]


def complete_trip_feature_row():
    feature_names = {
        field.name
        for field in fields(TripFeatures)
    }
    row = {
        name: None
        for name in feature_names
    }
    row.update(
        trip_id="trip-1",
        driver_id="driver-1",
        calculated_at="2026-08-21T10:00:00Z",
        duration_seconds=60.0,
        duration_hours=1 / 60,
        high_perclos_seconds=0.0,
        drowsy_seconds=0.0,
        drowsy_episode_count=0,
        unresponsive_seconds=0.0,
        unresponsive_episode_count=0,
        emergency_count=0,
        driver_data_coverage=0.0,
        vehicle_data_coverage=0.0,
    )
    return row


def test_historical_row_ignores_generated_id():
    row = complete_trip_feature_row()
    row["id"] = 42

    features = ScoreRepository._trip_features_from_row(row)

    assert features.trip_id == "trip-1"
    assert not hasattr(features, "id")


def test_historical_row_preserves_fields_and_none_values():
    row = complete_trip_feature_row()
    row["avg_perclos"] = None
    row["avg_speed"] = 42.0

    features = ScoreRepository._trip_features_from_row(row)

    assert features.avg_perclos is None
    assert features.avg_speed == 42.0
    assert features.calculated_at == datetime(
        2026, 8, 21, 10, 0, 0,
        tzinfo=timezone.utc,
    )


def test_historical_row_uses_defaults_for_missing_defaulted_fields():
    row = complete_trip_feature_row()
    row.pop("yawn_count")
    row.pop("avg_speed")
    row.pop("vehicle_data_coverage")

    features = ScoreRepository._trip_features_from_row(row)

    assert features.yawn_count is None
    assert features.avg_speed is None
    assert features.vehicle_data_coverage == 0.0


def test_historical_row_rejects_missing_required_fields():
    row = complete_trip_feature_row()
    row.pop("trip_id")

    with pytest.raises(TypeError):
        ScoreRepository._trip_features_from_row(row)


class EmptyHistoricalResponse:
    data = []


class EmptyHistoricalQuery:
    def select(self, _columns):
        return self

    def eq(self, _column, _value):
        return self

    def order(self, _column, desc):
        return self

    def execute(self):
        return EmptyHistoricalResponse()


class EmptyHistoricalClient:
    def table(self, _table_name):
        return EmptyHistoricalQuery()


def test_empty_historical_result_returns_empty_list():
    repository = ScoreRepository(EmptyHistoricalClient())

    assert repository.get_previous_trip_features("driver-1") == []


class WriteResponse:
    data = [{"id": 1}]


class WriteQuery:
    def __init__(self):
        self.inserted = None
        self.updated = None
        self.selected = None

    def insert(self, payload):
        self.inserted = payload
        return self

    def select(self, _columns):
        return self

    def eq(self, _column, _value):
        return self

    def order(self, _column, desc):
        return self

    def limit(self, _count):
        return self

    def update(self, payload):
        self.updated = payload
        return self

    def execute(self):
        return type(
            "WriteResponse",
            (),
            {
                "data": (
                    WriteResponse.data
                    if self.selected is None
                    else self.selected
                )
            },
        )()


class WriteClient:
    def __init__(self):
        self.queries = {}

    def table(self, table_name):
        query = self.queries.setdefault(table_name, WriteQuery())
        return query


def test_save_trip_features_persists_all_declared_fields_and_nulls():
    row = complete_trip_feature_row()
    row.update(
        calculated_at="2026-08-21T10:00:00Z",
        yawn_count=None,
        microsleep_count=None,
        distraction_count=None,
        distracted_time_pct=None,
    )
    features = ScoreRepository._trip_features_from_row(row)
    client = WriteClient()

    ScoreRepository(client).save_trip_features(features)

    payload = client.queries["trip_features"].inserted
    assert set(payload) == {
        field.name
        for field in fields(TripFeatures)
    }
    assert payload["calculated_at"] == features.calculated_at.isoformat()
    assert payload["yawn_count"] is None
    assert payload["microsleep_count"] is None
    assert payload["distraction_count"] is None
    assert payload["distracted_time_pct"] is None
    assert "id" not in payload


def test_save_score_history_persists_identifiers_and_nullable_scores():
    client = WriteClient()
    client.table("driver_score_history").selected = []
    score = type(
        "Score",
        (),
        {
            "driver_id": "driver-1",
            "fatigue_score": None,
            "safety_score": None,
            "attention_score": 95.0,
            "experience_score": 80.0,
            "health_score": 90.0,
            "raw_driver_score": 88.0,
            "final_driver_score": 88.0,
            "critical_event": False,
            "score_cap": None,
            "trips_analyzed": 1,
            "driving_hours_analyzed": 1.0,
            "score_confidence": "LOW",
            "data_quality": 1.0,
            "normalization_version": "1.0",
        },
    )()

    ScoreRepository(client).save_score_history(score, "trip-1")

    payload = client.queries["driver_score_history"].inserted
    assert payload["driver_id"] == "driver-1"
    assert payload["trip_id"] == "trip-1"
    assert payload["fatigue_score"] is None
    assert payload["score_cap"] is None
    assert payload["final_driver_score"] == 88.0
    assert "id" not in payload


def test_save_score_history_inserts_each_score_history_row():
    client = WriteClient()
    query = client.table("driver_score_history")
    score = type(
        "Score",
        (),
        {
            "driver_id": "driver-1",
            "fatigue_score": 90.0,
            "safety_score": 90.0,
            "attention_score": 90.0,
            "experience_score": 90.0,
            "health_score": 90.0,
            "raw_driver_score": 90.0,
            "final_driver_score": 90.0,
            "critical_event": False,
            "score_cap": None,
            "trips_analyzed": 2,
            "driving_hours_analyzed": 2.0,
            "score_confidence": "LOW",
            "data_quality": 1.0,
            "normalization_version": "1.0",
        },
    )()

    ScoreRepository(client).save_score_history(score, "trip-2")

    assert query.inserted["trip_id"] == "trip-2"
    assert query.inserted["final_driver_score"] == 90.0
    assert query.updated is None


def test_database_write_errors_are_propagated():
    class FailingQuery(WriteQuery):
        def execute(self):
            raise RuntimeError("database unavailable")

    class FailingClient(WriteClient):
        def table(self, table_name):
            query = FailingQuery()
            self.queries[table_name] = query
            return query

    row = complete_trip_feature_row()
    features = ScoreRepository._trip_features_from_row(row)

    with pytest.raises(RuntimeError, match="database unavailable"):
        ScoreRepository(FailingClient()).save_trip_features(features)


class FakeRepository:
    def __init__(self):
        self.saved_trip_features = []
        self.saved_scores = []
        self.previous_trip_features = []

    def get_trip_driver_metrics(self, trip_id):
        return [
            {
                "created_at": "2026-08-21T10:00:00Z",
                "driver_state": "NORMAL",
                "perclos": 0.10,
                "blink_rate": 20,
            },
            {
                "created_at": "2026-08-21T10:00:30Z",
                "driver_state": "NORMAL",
                "perclos": 0.10,
                "blink_rate": 20,
            },
        ]

    def get_trip_vehicle_metrics(self, trip_id):
        return []

    def get_trip_emergency_events(self, trip_id):
        return []

    def get_driver_baseline(self, driver_id):
        return {"blink_rate_mean": 20}

    def save_trip_features(self, features):
        self.saved_trip_features.append(features)

    def get_previous_trip_features(self, driver_id):
        return self.previous_trip_features

    def get_driver_profile(self, driver_id):
        return {
            "experience_score": 80.0,
            "health_score": 90.0,
        }

    def count_recent_critical_events(self, driver_id):
        return 0

    def save_score_history(self, score, trip_id):
        self.saved_scores.append((score, trip_id))


def test_pipeline_persists_features_and_score_with_fake_repository():
    repository = FakeRepository()
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

    score = ScoringPipeline(repository).process_trip(context)

    assert len(repository.saved_trip_features) == 1
    assert len(repository.saved_scores) == 1
    assert repository.saved_scores[0] == (score, "trip-1")
    assert score.driver_id == "driver-1"
    assert score.raw_driver_score is not None
    assert score.final_driver_score is not None
    assert score.raw_driver_score == pytest.approx(96.0)
    assert score.final_driver_score == pytest.approx(96.0)


def test_pipeline_keeps_current_raw_score_separate_from_cumulative_final_score():
    repository = FakeRepository()
    previous_context = TripContext(
        trip_id="previous-trip",
        driver_id="driver-1",
        trip_start=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        trip_end=datetime(2026, 8, 20, 11, 0, tzinfo=timezone.utc),
    )
    previous_metrics = [
        {
            "created_at": "2026-08-20T10:00:00Z",
            "driver_state": "UNRESPONSIVE",
            "perclos": 0.5,
            "blink_rate": 2,
        },
        {
            "created_at": "2026-08-20T10:30:00Z",
            "driver_state": "UNRESPONSIVE",
            "perclos": 0.5,
            "blink_rate": 2,
        },
    ]
    repository.previous_trip_features = [
        ScoringPipeline(repository).trip_extractor.extract(
            previous_context,
            previous_metrics,
            [],
            [],
            {"blink_rate_mean": 20},
        )
    ]

    current_context = TripContext(
        trip_id="current-trip",
        driver_id="driver-1",
        trip_start=datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc),
        trip_end=datetime(2026, 8, 21, 11, 0, tzinfo=timezone.utc),
    )
    score = ScoringPipeline(repository).process_trip(current_context)

    assert score.raw_driver_score > score.final_driver_score
    assert score.trips_analyzed == 2


def test_pipeline_does_not_save_score_when_feature_save_fails():
    class FeatureFailureRepository(FakeRepository):
        def save_trip_features(self, features):
            raise RuntimeError("trip feature write failed")

        def save_score_history(self, score, trip_id):
            self.saved_scores.append((score, trip_id))

    repository = FeatureFailureRepository()
    context = TripContext(
        trip_id="trip-1",
        driver_id="driver-1",
        trip_start=datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc),
        trip_end=datetime(2026, 8, 21, 10, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(RuntimeError, match="trip feature write failed"):
        ScoringPipeline(repository).process_trip(context)

    assert repository.saved_scores == []


def test_pipeline_feature_save_can_succeed_before_score_save_fails():
    class ScoreFailureRepository(FakeRepository):
        def save_score_history(self, score, trip_id):
            raise RuntimeError("score history write failed")

    repository = ScoreFailureRepository()
    context = TripContext(
        trip_id="trip-1",
        driver_id="driver-1",
        trip_start=datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc),
        trip_end=datetime(2026, 8, 21, 10, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(RuntimeError, match="score history write failed"):
        ScoringPipeline(repository).process_trip(context)

    assert len(repository.saved_trip_features) == 1
    assert repository.saved_scores == []


def test_finalize_trip_score_returns_structured_success(monkeypatch):
    finalize_trip_score = load_finalize_trip_score()

    class Writer:
        def end_trip(self, trip_id, trip_end):
            self.ended = (trip_id, trip_end)

    class Pipeline:
        def __init__(self, score):
            self.score = score

        def process_trip(self, context):
            return self.score

    expected_score = type(
                "Score",
                (),
                {
                    "raw_driver_score": 90.0,
                    "final_driver_score": 90.0,
                    "score_confidence": "LOW",
                },
            )()
    pipeline = Pipeline(expected_score)

    writer = Writer()
    namespace = finalize_trip_score.__globals__
    namespace.update(
        database_writer=writer,
        current_trip_id="trip-1",
        driver_id="driver-1",
        trip_start_time=datetime(
            2026, 8, 21, 10, 0, tzinfo=timezone.utc
        ),
        scoring_pipeline=pipeline,
        datetime=datetime,
        timezone=timezone,
        TripContext=TripContext,
        FinalizationResult=FinalizationResult,
    )

    result = finalize_trip_score()
    assert result.success is True
    assert result.score is expected_score
    assert result.error is None
    assert writer.ended[0] == "trip-1"


def test_finalize_trip_score_returns_structured_failure(capsys):
    finalize_trip_score = load_finalize_trip_score()

    class Writer:
        def end_trip(self, trip_id, trip_end):
            pass

    class Pipeline:
        def process_trip(self, context):
            raise RuntimeError("score persistence failed")

    namespace = finalize_trip_score.__globals__
    namespace.update(
        database_writer=Writer(),
        current_trip_id="trip-1",
        driver_id="driver-1",
        trip_start_time=datetime(
            2026, 8, 21, 10, 0, tzinfo=timezone.utc
        ),
        scoring_pipeline=Pipeline(),
        datetime=datetime,
        timezone=timezone,
        TripContext=TripContext,
        FinalizationResult=FinalizationResult,
    )

    result = finalize_trip_score()
    assert result.success is False
    assert result.score is None
    assert result.error == "score persistence failed"
    assert "DRIVER SCORE ERROR" in capsys.readouterr().out


def test_finalize_trip_score_returns_failure_when_end_trip_fails(capsys):
    finalize_trip_score = load_finalize_trip_score()

    class Writer:
        def end_trip(self, trip_id, trip_end):
            raise RuntimeError("trip end write failed")

    class Pipeline:
        def process_trip(self, context):
            raise AssertionError("scoring must not start")

    namespace = finalize_trip_score.__globals__
    namespace.update(
        database_writer=Writer(),
        current_trip_id="trip-1",
        driver_id="driver-1",
        trip_start_time=datetime(
            2026, 8, 21, 10, 0, tzinfo=timezone.utc
        ),
        scoring_pipeline=Pipeline(),
        datetime=datetime,
        timezone=timezone,
        TripContext=TripContext,
        FinalizationResult=FinalizationResult,
    )

    result = finalize_trip_score()

    assert result.success is False
    assert result.score is None
    assert result.error == "trip end write failed"
    assert "DRIVER SCORE ERROR" in capsys.readouterr().out


def test_finalization_result_is_importable_without_application_startup():
    result = FinalizationResult(
        success=False,
        score=None,
        error="test error",
    )

    assert result.success is False
    assert result.score is None
    assert result.error == "test error"
