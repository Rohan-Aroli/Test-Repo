import json
from dataclasses import fields
from datetime import datetime
from pathlib import Path


class ScoreRepository:

    def __init__(self, supabase):
        self.supabase = supabase

    # ======================================
    # Raw data
    # ======================================

    def get_trip_driver_metrics(
        self,
        trip_id
    ):

        response = (
            self.supabase
            .table("driver_metrics")
            .select("*")
            .eq("trip_id", trip_id)
            .execute()
        )

        return response.data or []

    def get_trip_vehicle_metrics(
        self,
        trip_id
    ):

        response = (
            self.supabase
            .table("vehicle_metrics")
            .select("*")
            .eq("trip_id", trip_id)
            .execute()
        )

        return response.data or []

    def get_trip_emergency_events(
        self,
        trip_id
    ):

        response = (
            self.supabase
            .table("emergency_events")
            .select("*")
            .eq("trip_id", trip_id)
            .execute()
        )

        return response.data or []

    # ======================================
    # Driver profile
    # ======================================

    def get_driver_profile(
        self,
        driver_id
    ):

        response = (
            self.supabase
            .table("drivers")
            .select("*")
            .eq("id", driver_id)
            .single()
            .execute()
        )

        return response.data or {}

    # ======================================
    # Baseline
    # ======================================

    def get_driver_baseline(
        self,
        driver_id
    ):

        baseline_path = (
            Path("baselines") /
            f"{driver_id}.json"
        )

        if not baseline_path.exists():
            return {}

        try:
            with open(baseline_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return {}

    # ======================================
    # Historical trips
    # ======================================

    def get_previous_trip_features(
        self,
        driver_id
    ):

        response = (
            self.supabase
            .table("trip_features")
            .select("*")
            .eq("driver_id", driver_id)
            .order(
                "calculated_at",
                desc=False
            )
            .execute()
        )

        # Convert DB rows to TripFeatures
        # objects here.

        return [
            self._trip_features_from_row(row)
            for row in (
                response.data or []
            )
        ]

    # ======================================
    # Save trip features
    # ======================================

    def save_trip_features(
        self,
        features
    ):

        payload = {
            field.name: self._json_value(
                getattr(features, field.name)
            )
            for field in fields(type(features))
        }

        return (
            self.supabase
            .table("trip_features")
            .insert(payload)
            .execute()
        )

    # ======================================
    # Save score
    # ======================================

    def save_score_history(
        self,
        score,
        trip_id
    ):

        payload = {
            "driver_id":
                score.driver_id,

            "trip_id":
                trip_id,

            "calculated_at":
                datetime.now().isoformat(),

            "fatigue_score":
                score.fatigue_score,

            "safety_score":
                score.safety_score,

            "attention_score":
                score.attention_score,

            "experience_score":
                score.experience_score,

            "health_score":
                score.health_score,

            "raw_driver_score":
                score.raw_driver_score,

            "final_driver_score":
                score.final_driver_score,

            "critical_event":
                score.critical_event,

            "score_cap":
                score.score_cap,

            "trips_analyzed":
                score.trips_analyzed,

            "driving_hours_analyzed":
                score.driving_hours_analyzed,

            "score_confidence":
                score.score_confidence,

            "data_quality":
                score.data_quality,

            "normalization_version":
                score.normalization_version,
        }

        return (
            self.supabase
            .table("driver_score_history")
            .insert(payload)
            .execute()
        )

    # ======================================
    # Critical events
    # ======================================

    def count_recent_critical_events(
        self,
        driver_id
    ):

        response = (
            self.supabase
            .table("emergency_events")
            .select("id")
            .eq("driver_id", driver_id)
            .eq("severity", "critical")
            .execute()
        )

        return len(response.data or [])

    # ======================================
    # Conversion
    # ======================================

    @staticmethod
    def _trip_features_from_row(row):

        from .models import TripFeatures

        feature_fields = {
            field.name
            for field in fields(TripFeatures)
        }
        converted = {
            key: value
            for key, value in dict(row).items()
            if key in feature_fields
        }

        calculated_at = converted.get("calculated_at")
        if isinstance(calculated_at, str):
            try:
                converted["calculated_at"] = datetime.fromisoformat(
                    calculated_at.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        return TripFeatures(
            **converted
        )

    @staticmethod
    def _json_value(value):
        """Convert Python datetime values to Supabase JSON values."""
        if isinstance(value, datetime):
            return value.isoformat()
        return value