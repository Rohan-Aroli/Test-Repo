import math
from typing import Optional

from .models import TripFeatures, HistoricalFeatures


class HistoricalFeatureEngine:

    def __init__(
        self,
        recency_lambda: float = 0.01
    ):
        self.recency_lambda = recency_lambda

    # ======================================
    # Main method
    # ======================================

    def aggregate(
        self,
        trips: list[TripFeatures],
        reference_time
    ) -> HistoricalFeatures:

        if not trips:
            raise ValueError(
                "At least one trip is required"
            )

        driver_id = trips[-1].driver_id

        weighted_hours = 0.0

        weighted = {}

        event_totals = {
            "yawn_count": 0.0,
            "microsleep_count": 0.0,
            "drowsy_episode_count": 0.0,
            "unresponsive_episode_count": 0.0,
            "distraction_count": 0.0,
            "emergency_count": 0.0,
        }

        for trip in trips:

            # --------------------------------
            # Recency
            # --------------------------------

            age_days = (
                reference_time -
                self._trip_time(trip)
            ).total_seconds() / 86400.0

            age_days = max(0.0, age_days)

            recency = math.exp(
                -self.recency_lambda *
                age_days
            )

            weight = (
                trip.duration_hours *
                recency
            )

            weighted_hours += weight

            # --------------------------------
            # Time weighted features
            # --------------------------------

            self._add_weighted(
                weighted,
                "avg_perclos",
                trip.avg_perclos,
                weight
            )

            self._add_weighted(
                weighted,
                "high_perclos_time_pct",
                trip.high_perclos_time_pct,
                weight
            )

            self._add_weighted(
                weighted,
                "drowsy_time_pct",
                trip.drowsy_time_pct,
                weight
            )

            self._add_weighted(
                weighted,
                "unresponsive_time_pct",
                trip.unresponsive_time_pct,
                weight
            )

            self._add_weighted(
                weighted,
                "blink_deviation",
                trip.blink_deviation,
                weight
            )

            self._add_weighted(
                weighted,
                "avg_yawn_duration",
                trip.avg_yawn_duration,
                weight
            )

            self._add_weighted(
                weighted,
                "avg_microsleep_duration",
                trip.avg_microsleep_duration,
                weight
            )

            self._add_weighted(
                weighted,
                "avg_speed",
                trip.avg_speed,
                weight
            )

            self._add_weighted(
                weighted,
                "avg_throttle",
                trip.avg_throttle,
                weight
            )

            self._add_weighted(
                weighted,
                "avg_brake",
                trip.avg_brake,
                weight
            )

            self._add_weighted(
                weighted,
                "steering_variability",
                trip.steering_variability,
                weight
            )

            self._add_weighted(
                weighted,
                "distracted_time_pct",
                trip.distracted_time_pct,
                weight
            )

            self._add_weighted(
                weighted,
                "emergency_risk_rate",
                trip.emergency_risk_rate,
                weight
            )

            # --------------------------------
            # Event totals
            # --------------------------------

            self._add_event(
                event_totals,
                "yawn_count",
                trip.yawn_count,
                recency
            )

            self._add_event(
                event_totals,
                "microsleep_count",
                trip.microsleep_count,
                recency
            )

            self._add_event(
                event_totals,
                "drowsy_episode_count",
                trip.drowsy_episode_count,
                recency
            )

            self._add_event(
                event_totals,
                "unresponsive_episode_count",
                trip.unresponsive_episode_count,
                recency
            )

            self._add_event(
                event_totals,
                "distraction_count",
                trip.distraction_count,
                recency
            )

            self._add_event(
                event_totals,
                "emergency_count",
                trip.emergency_count,
                recency
            )

        return HistoricalFeatures(

            driver_id=driver_id,

            trips_analyzed=len(trips),

            driving_hours_analyzed=sum(
                trip.duration_hours
                for trip in trips
            ),

            avg_perclos=self._weighted_value(
                weighted,
                "avg_perclos"
            ),

            high_perclos_time_pct=
                self._weighted_value(
                    weighted,
                    "high_perclos_time_pct"
                ),

            drowsy_time_pct=
                self._weighted_value(
                    weighted,
                    "drowsy_time_pct"
                ),

            drowsy_episode_rate=
                event_totals[
                    "drowsy_episode_count"
                ] / max(
                    0.001,
                    sum(
                        trip.duration_hours
                        for trip in trips
                    )
                ),

            unresponsive_rate=
                event_totals[
                    "unresponsive_episode_count"
                ] / max(
                    0.001,
                    sum(
                        trip.duration_hours
                        for trip in trips
                    )
                ),

            unresponsive_time_pct=
                self._weighted_value(
                    weighted,
                    "unresponsive_time_pct"
                ),

            blink_deviation=
                self._weighted_value(
                    weighted,
                    "blink_deviation"
                ),

            yawn_rate=self._rate(
                event_totals["yawn_count"],
                weighted_hours
            ),

            avg_yawn_duration=
                self._weighted_value(
                    weighted,
                    "avg_yawn_duration"
                ),

            microsleep_rate=self._rate(
                event_totals[
                    "microsleep_count"
                ],
                weighted_hours
            ),

            avg_microsleep_duration=
                self._weighted_value(
                    weighted,
                    "avg_microsleep_duration"
                ),

            max_microsleep_duration=
                self._max_value(
                    trips,
                    "max_microsleep_duration"
                ),

            distraction_rate=self._rate(
                event_totals[
                    "distraction_count"
                ],
                weighted_hours
            ),

            distracted_time_pct=
                self._weighted_value(
                    weighted,
                    "distracted_time_pct"
                ),

            emergency_rate=self._rate(
                event_totals[
                    "emergency_count"
                ],
                weighted_hours
            ),

            emergency_risk_rate=
                self._weighted_value(
                    weighted,
                    "emergency_risk_rate"
                ),

            avg_speed=
                self._weighted_value(
                    weighted,
                    "avg_speed"
                ),

            max_speed=
                self._max_value(
                    trips,
                    "max_speed"
                ),

            avg_throttle=
                self._weighted_value(
                    weighted,
                    "avg_throttle"
                ),

            avg_brake=
                self._weighted_value(
                    weighted,
                    "avg_brake"
                ),

            steering_variability=
                self._weighted_value(
                    weighted,
                    "steering_variability"
                ),
        )

    # ======================================
    # Helpers
    # ======================================

    @staticmethod
    def _trip_time(trip):

        # Temporary convention:
        # trip objects should later carry
        # their calculated_at timestamp.
        return getattr(
            trip,
            "calculated_at",
            None
        )

    @staticmethod
    def _add_weighted(
        storage,
        key,
        value,
        weight
    ):

        if value is None:
            return

        if key not in storage:
            storage[key] = [0.0, 0.0]

        storage[key][0] += (
            value * weight
        )

        storage[key][1] += weight

    @staticmethod
    def _weighted_value(
        storage,
        key
    ):

        if key not in storage:
            return None

        numerator, denominator = storage[key]

        if denominator <= 0:
            return None

        return numerator / denominator

    @staticmethod
    def _add_event(
        storage,
        key,
        value,
        recency
    ):

        if value is None:
            return

        storage[key] += (
            value * recency
        )

    @staticmethod
    def _rate(
        count,
        hours
    ):

        if hours <= 0:
            return None

        return count / hours

    @staticmethod
    def _max_value(
        trips,
        attribute
    ):

        values = [
            getattr(trip, attribute)
            for trip in trips
            if getattr(
                trip,
                attribute,
                None
            ) is not None
        ]

        return max(values) if values else None