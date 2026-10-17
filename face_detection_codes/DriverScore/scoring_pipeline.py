from dataclasses import replace

from .trip_features import TripFeatureExtractor
from .historical_features import HistoricalFeatureEngine
from .component_scores import ComponentScorer
from .driver_score import DriverScoreEngine


class ScoringPipeline:

    def __init__(
        self,
        repository,
        perclos_threshold=0.20,
        recency_lambda=0.01
    ):

        self.repository = repository

        self.trip_extractor = (
            TripFeatureExtractor(
                perclos_high_threshold=
                    perclos_threshold
            )
        )

        self.history_engine = (
            HistoricalFeatureEngine(
                recency_lambda=
                    recency_lambda
            )
        )

        self.component_scorer = (
            ComponentScorer()
        )

        self.score_engine = (
            DriverScoreEngine()
        )

    # ======================================
    # Main entry point
    # ======================================

    def process_trip(
        self,
        trip_context
    ):

        # -------------------------------
        # 1. Fetch raw data
        # -------------------------------

        driver_metrics = (
            self.repository
            .get_trip_driver_metrics(
                trip_context.trip_id
            )
        )

        vehicle_metrics = (
            self.repository
            .get_trip_vehicle_metrics(
                trip_context.trip_id
            )
        )

        emergency_events = (
            self.repository
            .get_trip_emergency_events(
                trip_context.trip_id
            )
        )

        # -------------------------------
        # 2. Fetch baseline
        # -------------------------------

        baseline = (
            self.repository
            .get_driver_baseline(
                trip_context.driver_id
            )
        )

        # -------------------------------
        # 3. Extract current trip
        # -------------------------------

        trip_features = (
            self.trip_extractor.extract(
                context=trip_context,
                driver_metrics=driver_metrics,
                vehicle_metrics=vehicle_metrics,
                emergency_events=emergency_events,
                baseline=baseline
            )
        )

        # -------------------------------
        # 4. Fetch historical trips before saving the current trip
        # -------------------------------

        previous_trips = (
            self.repository
            .get_previous_trip_features(
                trip_context.driver_id
            )
        )
        previous_trips = [
            trip
            for trip in previous_trips
            if trip.trip_id != trip_context.trip_id
        ]

        # -------------------------------
        # 5. Save current trip features
        # -------------------------------

        self.repository.save_trip_features(
            trip_features
        )

        # -------------------------------
        # 6. Aggregate current and historical trips separately
        # -------------------------------

        current_historical = (
            self.history_engine.aggregate(
                trips=[trip_features],
                reference_time=trip_context.trip_end
            )
        )

        all_trips = (
            previous_trips +
            [trip_features]
        )

        historical = (
            self.history_engine.aggregate(
                trips=all_trips,
                reference_time=
                    trip_context.trip_end
            )
        )

        current_normalized = (
            self.component_scorer.normalize(
                current_historical
            )
        )

        historical_normalized = (
            self.component_scorer.normalize(
                historical
            )
        )

        current_fatigue = (
            self.component_scorer
            .fatigue_score(
                current_normalized
            )
        )

        current_attention = (
            self.component_scorer
            .attention_score(
                current_normalized
            )
        )

        current_safety = (
            self.component_scorer
            .safety_score(
                current_normalized
            )
        )

        historical_fatigue = (
            self.component_scorer
            .fatigue_score(
                historical_normalized
            )
        )

        historical_attention = (
            self.component_scorer
            .attention_score(
                historical_normalized
            )
        )

        historical_safety = (
            self.component_scorer
            .safety_score(
                historical_normalized
            )
        )

        profile = (
            self.repository
            .get_driver_profile(
                trip_context.driver_id
            )
        )

        experience = profile.get(
            "experience_score"
        )

        health = profile.get(
            "health_score"
        )

        historical_critical_events = (
            self.repository
            .count_recent_critical_events(
                trip_context.driver_id
            )
        )

        current_critical_events = sum(
            1
            for event in emergency_events
            if event.get("severity") == "critical"
        )

        current_score = self.score_engine.calculate(
            driver_id=
                trip_context.driver_id,

            fatigue_score=current_fatigue,
            safety_score=current_safety,
            attention_score=current_attention,

            experience_score=experience,
            health_score=health,

            historical_features=current_historical,

            critical_events=current_critical_events,

            data_quality=self._data_quality(
                trip_features
            )
        )

        cumulative_score = self.score_engine.calculate(
            driver_id=trip_context.driver_id,
            fatigue_score=historical_fatigue,
            safety_score=historical_safety,
            attention_score=historical_attention,
            experience_score=experience,
            health_score=health,
            historical_features=historical,
            critical_events=historical_critical_events,
            data_quality=self._data_quality(trip_features),
        )

        # The raw score describes this trip. The final score describes the
        # driver's complete trip history, including historical constraints.
        score = replace(
            current_score,
            final_driver_score=cumulative_score.final_driver_score,
            critical_event=cumulative_score.critical_event,
            score_cap=cumulative_score.score_cap,
            trips_analyzed=cumulative_score.trips_analyzed,
            driving_hours_analyzed=(
                cumulative_score.driving_hours_analyzed
            ),
            score_confidence=cumulative_score.score_confidence,
        )

        self.repository.save_score_history(
            score,
            trip_context.trip_id
        )

        return score

    @staticmethod
    def _data_quality(
        trip_features
    ):

        return (
            trip_features.driver_data_coverage +
            trip_features.vehicle_data_coverage
        ) / 2.0