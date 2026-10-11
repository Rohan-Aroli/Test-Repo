import json
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
            "trip_id":
                features.trip_id,

            "driver_id":
                features.driver_id,

            "duration_seconds":
                features.duration_seconds,

            "duration_hours":
                features.duration_hours,

            "avg_perclos":
                features.avg_perclos,

            "high_perclos_seconds":
                features.high_perclos_seconds,

            "high_perclos_time_pct":
                features.high_perclos_time_pct,

            "drowsy_seconds":
                features.drowsy_seconds,

            "drowsy_time_pct":
                features.drowsy_time_pct,

            "drowsy_episode_count":
                features.drowsy_episode_count,

            "drowsy_episode_rate":
                features.drowsy_episode_rate,

            "avg_drowsy_episode_duration":
                features.avg_drowsy_episode_duration,

            "max_drowsy_episode_duration":
                features.max_drowsy_episode_duration,

            "unresponsive_seconds":
                features.unresponsive_seconds,

            "unresponsive_time_pct":
                features.unresponsive_time_pct,

            "unresponsive_episode_count":
                features.unresponsive_episode_count,

            "unresponsive_rate":
                features.unresponsive_rate,

            "avg_blink_rate":
                features.avg_blink_rate,

            "blink_deviation":
                features.blink_deviation,

            "yawn_count":
                features.yawn_count,

            "yawn_rate":
                features.yawn_rate,

            "avg_yawn_duration":
                features.avg_yawn_duration,

            "microsleep_count":
                features.microsleep_count,

            "microsleep_rate":
                features.microsleep_rate,

            "avg_microsleep_duration":
                features.avg_microsleep_duration,

            "max_microsleep_duration":
                features.max_microsleep_duration,

            "distraction_count":
                features.distraction_count,

            "distraction_rate":
                features.distraction_rate,

            "distracted_seconds":
                features.distracted_seconds,

            "distracted_time_pct":
                features.distracted_time_pct,

            "emergency_count":
                features.emergency_count,

            "emergency_rate":
                features.emergency_rate,

            "emergency_risk_rate":
                features.emergency_risk_rate,

            "avg_speed":
                features.avg_speed,

            "max_speed":
                features.max_speed,

            "avg_throttle":
                features.avg_throttle,

            "avg_brake":
                features.avg_brake,

            "steering_variability":
                features.steering_variability,

            "driver_data_coverage":
                features.driver_data_coverage,

            "vehicle_data_coverage":
                features.vehicle_data_coverage,
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

        converted = dict(row)

        calculated_at = converted.get("calculated_at")
        if isinstance(calculated_at, str):
            try:
                converted["calculated_at"] = datetime.fromisoformat(
                    calculated_at.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        # Remove DB specific id column before creating domain model
        converted.pop("id", None)

        return TripFeatures(
            **converted
        )