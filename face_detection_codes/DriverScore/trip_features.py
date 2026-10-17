from typing import Optional
from datetime import datetime, timezone

from .models import TripContext, TripFeatures


class TripFeatureExtractor:

    def __init__(
        self,
        perclos_high_threshold: float = 0.20
    ):
        """
        Create a trip feature extractor.

        Parameters
        ----------
        perclos_high_threshold:
            PERCLOS value above which the period is considered
            high-PERCLOS exposure.
        """

        self.perclos_high_threshold = (
            perclos_high_threshold
        )

    # ==================================================
    # PUBLIC API
    # ==================================================

    def extract(
        self,
        context: TripContext,
        driver_metrics: list,
        vehicle_metrics: list,
        emergency_events: list,
        baseline: Optional[dict] = None,
    ) -> TripFeatures:
        """
        Convert raw trip data into temporal trip-level features.
        """

        normalized_context = TripContext(
            trip_id=context.trip_id,
            driver_id=context.driver_id,
            trip_start=self._as_utc(context.trip_start),
            trip_end=self._as_utc(context.trip_end),
        )

        self._validate_context(normalized_context)

        driver_metrics = self._sort_and_filter(
            driver_metrics,
            normalized_context
        )

        vehicle_metrics = self._sort_and_filter(
            vehicle_metrics,
            normalized_context
        )

        emergency_events = self._sort_and_filter(
            emergency_events,
            normalized_context
        )

        driver_features = self._extract_driver_features(
            normalized_context,
            driver_metrics,
            baseline
        )

        vehicle_features = self._extract_vehicle_features(
            normalized_context,
            vehicle_metrics
        )

        emergency_features = self._extract_emergency_features(
            normalized_context,
            emergency_events
        )

        event_features = self._extract_event_features(
            normalized_context,
            driver_metrics
        )

        return TripFeatures(
            trip_id=normalized_context.trip_id,
            driver_id=normalized_context.driver_id,

            # Important:
            # HistoricalFeatureEngine uses this timestamp
            # for recency weighting.
            calculated_at=normalized_context.trip_end,

            duration_seconds=normalized_context.duration_seconds,
            duration_hours=normalized_context.duration_hours,

            **driver_features,
            **vehicle_features,
            **emergency_features,
            **event_features,

            driver_data_coverage=self._calculate_coverage(
                len(driver_metrics),
                normalized_context.duration_seconds
            ),

            vehicle_data_coverage=self._calculate_coverage(
                len(vehicle_metrics),
                normalized_context.duration_seconds
            )
        )

    # ==================================================
    # VALIDATION
    # ==================================================

    @staticmethod
    def _validate_context(context: TripContext):
        if context.duration_seconds <= 0:
            raise ValueError(
                "Trip duration must be positive"
            )

    # ==================================================
    # FILTERING
    # ==================================================

    @staticmethod
    def _sort_and_filter(
        rows,
        context: TripContext
    ):
        """
        Keep only timestamped rows belonging to this trip.
        """

        valid_rows = []

        for row in rows:

            timestamp = TripFeatureExtractor._to_datetime(
                row.get("created_at")
            )

            if timestamp is None:
                continue

            if (
                context.trip_start
                <= timestamp
                <= context.trip_end
            ):
                normalized_row = dict(row)
                normalized_row["created_at"] = timestamp
                valid_rows.append(normalized_row)

        valid_rows.sort(
            key=lambda row: row["created_at"]
        )

        return valid_rows

    @staticmethod
    def _to_datetime(value):
        if isinstance(value, datetime):
            return TripFeatureExtractor._as_utc(value)

        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                )
                return TripFeatureExtractor._as_utc(parsed)
            except ValueError:
                return None

        return None

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        """Interpret naive values as UTC and normalize aware values to UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    # ==================================================
    # DRIVER FEATURES
    # ==================================================

    def _extract_driver_features(
        self,
        context: TripContext,
        rows,
        baseline: Optional[dict]
    ):

        if not rows:
            return {
                "avg_perclos": None,
                "high_perclos_seconds": 0.0,
                "high_perclos_time_pct": None,

                "drowsy_seconds": 0.0,
                "drowsy_time_pct": None,
                "drowsy_episode_count": 0,
                "drowsy_episode_rate": None,
                "avg_drowsy_episode_duration": None,
                "max_drowsy_episode_duration": None,

                "unresponsive_seconds": 0.0,
                "unresponsive_time_pct": None,
                "unresponsive_episode_count": 0,
                "unresponsive_rate": None,

                "avg_blink_rate": None,
                "blink_deviation": None,
            }

        total_time = context.duration_seconds

        # ----------------------------------------------
        # PERCLOS
        # ----------------------------------------------

        avg_perclos = self._time_weighted_numeric(
            rows,
            "perclos",
            context.trip_end
        )

        high_perclos_seconds = self._state_time(
            rows,
            lambda row: (
                self._numeric(
                    row.get("perclos")
                ) is not None
                and
                self._numeric(
                    row.get("perclos")
                ) > self.perclos_high_threshold
            ),
            context.trip_end
        )

        high_perclos_time_pct = (
            high_perclos_seconds
            / total_time
            * 100.0
        )

        # ----------------------------------------------
        # DROWSINESS
        # ----------------------------------------------

        drowsy_seconds = self._state_time(
            rows,
            lambda row:
                str(
                    row.get("driver_state", "")
                ).upper() == "DROWSY",
            context.trip_end
        )

        drowsy_episodes = self._extract_state_episodes(
            rows,
            "DROWSY",
            context.trip_end
        )

        # ----------------------------------------------
        # UNRESPONSIVE
        # ----------------------------------------------

        unresponsive_seconds = self._state_time(
            rows,
            lambda row:
                str(
                    row.get("driver_state", "")
                ).upper() == "UNRESPONSIVE",
            context.trip_end
        )

        unresponsive_episodes = (
            self._extract_state_episodes(
                rows,
                "UNRESPONSIVE",
                context.trip_end
            )
        )

        # ----------------------------------------------
        # BLINK RATE
        # ----------------------------------------------

        blink_values = [
            self._numeric(
                row.get("blink_rate")
            )
            for row in rows
        ]

        blink_values = [
            value
            for value in blink_values
            if value is not None
        ]

        avg_blink = (
            sum(blink_values)
            / len(blink_values)
            if blink_values
            else None
        )

        # ----------------------------------------------
        # BLINK BASELINE DEVIATION
        # ----------------------------------------------

        blink_deviation = None

        if baseline and avg_blink is not None:

            baseline_blink = self._numeric(
                baseline.get("blink_rate_mean")
            )

            if (
                baseline_blink is not None
                and baseline_blink > 0
            ):
                blink_deviation = (
                    abs(
                        avg_blink
                        - baseline_blink
                    )
                    / baseline_blink
                )

        return {
            "avg_perclos": avg_perclos,

            "high_perclos_seconds":
                high_perclos_seconds,

            "high_perclos_time_pct":
                high_perclos_time_pct,

            "drowsy_seconds":
                drowsy_seconds,

            "drowsy_time_pct":
                drowsy_seconds
                / total_time
                * 100.0,

            "drowsy_episode_count":
                len(drowsy_episodes),

            "drowsy_episode_rate":
                len(drowsy_episodes)
                / context.duration_hours,

            "avg_drowsy_episode_duration":
                self._average_episode_duration(
                    drowsy_episodes
                ),

            "max_drowsy_episode_duration":
                self._max_episode_duration(
                    drowsy_episodes
                ),

            "unresponsive_seconds":
                unresponsive_seconds,

            "unresponsive_time_pct":
                unresponsive_seconds
                / total_time
                * 100.0,

            "unresponsive_episode_count":
                len(unresponsive_episodes),

            "unresponsive_rate":
                len(unresponsive_episodes)
                / context.duration_hours,

            "avg_blink_rate":
                avg_blink,

            "blink_deviation":
                blink_deviation,
        }

    # ==================================================
    # TIME-WEIGHTED NUMERIC FEATURE
    # ==================================================

    @staticmethod
    def _time_weighted_numeric(
        rows,
        field,
        trip_end
    ):
        """
        Calculate a time-weighted mean.

        This is preferable to a simple row-wise mean when
        sampling intervals are not perfectly uniform.
        """

        weighted_sum = 0.0
        total_time = 0.0

        for index, row in enumerate(rows):

            value = TripFeatureExtractor._numeric(
                row.get(field)
            )

            if value is None:
                continue

            current_time = row["created_at"]

            if index + 1 < len(rows):
                next_time = rows[
                    index + 1
                ]["created_at"]
            else:
                next_time = trip_end

            delta = (
                next_time
                - current_time
            ).total_seconds()

            if delta <= 0:
                continue

            weighted_sum += (
                value * delta
            )

            total_time += delta

        if total_time <= 0:
            return None

        return weighted_sum / total_time

    # ==================================================
    # STATE DURATION
    # ==================================================

    @staticmethod
    def _state_time(
        rows,
        condition,
        trip_end
    ):
        """
        Calculate the total amount of time for which
        a state/condition was active.
        """

        total = 0.0

        for index, row in enumerate(rows):

            if not condition(row):
                continue

            current_time = row["created_at"]

            if index + 1 < len(rows):
                next_time = rows[
                    index + 1
                ]["created_at"]
            else:
                next_time = trip_end

            delta = (
                next_time
                - current_time
            ).total_seconds()

            if delta > 0:
                total += delta

        return total

    # ==================================================
    # STATE EPISODES
    # ==================================================

    @staticmethod
    def _extract_state_episodes(
        rows,
        target_state,
        trip_end
    ):
        """
        Convert consecutive state observations into episodes.

        Example:

        DROWSY
        DROWSY
        DROWSY
        NORMAL

        becomes one DROWSY episode.
        """

        episodes = []
        start = None

        target_state = target_state.upper()

        for index, row in enumerate(rows):

            state = str(
                row.get("driver_state", "")
            ).upper()

            current_time = row["created_at"]

            is_target = (
                state == target_state
            )

            if (
                is_target
                and start is None
            ):
                start = current_time

            is_last = (
                index == len(rows) - 1
            )

            if start is not None:

                if (
                    not is_target
                    or is_last
                ):

                    if (
                        is_last
                        and is_target
                    ):
                        end = trip_end
                    else:
                        end = current_time

                    duration = (
                        end - start
                    ).total_seconds()

                    if duration > 0:
                        episodes.append({
                            "start": start,
                            "end": end,
                            "duration": duration
                        })

                    start = None

        return episodes

    @staticmethod
    def _average_episode_duration(
        episodes
    ):
        if not episodes:
            return None

        return (
            sum(
                episode["duration"]
                for episode in episodes
            )
            / len(episodes)
        )

    @staticmethod
    def _max_episode_duration(
        episodes
    ):
        if not episodes:
            return None

        return max(
            episode["duration"]
            for episode in episodes
        )

    # ==================================================
    # EVENT FEATURES
    # ==================================================

    def _extract_event_features(
        self,
        context: TripContext,
        rows
    ):
        """
        Extract cumulative event counters from the
        real-time monitoring pipeline.

        IMPORTANT:
        yawn_count and microsleep_count are cumulative
        counters. They must NOT be summed row-by-row.

        Example:

            0 -> 1 -> 1 -> 3 -> 3

        represents 3 events, not 8.
        """

        if not rows:
            return {
                "yawn_count": None,
                "yawn_rate": None,
                "avg_yawn_duration": None,

                "microsleep_count": None,
                "microsleep_rate": None,
                "avg_microsleep_duration": None,
                "max_microsleep_duration": None,

                "distraction_count": None,
                "distraction_rate": None,
                "distracted_seconds": None,
                "distracted_time_pct": None,
            }

        # ----------------------------------------------
        # YAWNS
        # ----------------------------------------------

        yawn_count = self._counter_delta(
            rows,
            "yawn_count"
        )

        avg_yawn_duration = self._last_numeric(
            rows,
            "avg_yawn_duration"
        )

        # ----------------------------------------------
        # MICROSLEEPS
        # ----------------------------------------------

        microsleep_count = self._counter_delta(
            rows,
            "microsleep_count"
        )

        avg_microsleep_duration = self._last_numeric(
            rows,
            "avg_microsleep_duration"
        )

        max_microsleep_duration = (
            self._max_microsleep_duration(
                rows
            )
        )

        # ----------------------------------------------
        # DISTRACTION
        # ----------------------------------------------

        distraction_count = self._counter_delta(
            rows,
            "distraction_count"
        )

        distracted_seconds = self._last_numeric(
            rows,
            "distracted_seconds"
        )

        if distracted_seconds is None:
            distracted_seconds = self._sum_numeric(
                rows,
                "distraction_duration"
            )

        duration_hours = (
            context.duration_hours
        )

        duration_seconds = (
            context.duration_seconds
        )

        # ----------------------------------------------
        # FINAL EVENT FEATURES
        # ----------------------------------------------

        return {
            "yawn_count":
                yawn_count,

            "yawn_rate":
                (
                    yawn_count
                    / duration_hours
                    if (
                        yawn_count is not None
                        and duration_hours > 0
                    )
                    else None
                ),

            "avg_yawn_duration":
                avg_yawn_duration,

            "microsleep_count":
                microsleep_count,

            "microsleep_rate":
                (
                    microsleep_count
                    / duration_hours
                    if (
                        microsleep_count is not None
                        and duration_hours > 0
                    )
                    else None
                ),

            "avg_microsleep_duration":
                avg_microsleep_duration,

            "max_microsleep_duration":
                max_microsleep_duration,

            "distraction_count":
                distraction_count,

            "distraction_rate":
                (
                    distraction_count
                    / duration_hours
                    if (
                        distraction_count is not None
                        and duration_hours > 0
                    )
                    else None
                ),

            "distracted_seconds":
                distracted_seconds,

            "distracted_time_pct":
                (
                    distracted_seconds
                    / duration_seconds
                    * 100.0
                    if (
                        distracted_seconds is not None
                        and duration_seconds > 0
                    )
                    else None
                ),
        }

    # ==================================================
    # CUMULATIVE COUNTER DELTA
    # ==================================================

    @staticmethod
    def _counter_delta(
        rows,
        field
    ):
        """
        Convert a cumulative counter into the number
        of events observed during the trip.

        Handles counter resets safely.

        Example:

            0 -> 1 -> 1 -> 3 -> 3
            = 3 events

        If the counter resets:

            3 -> 0 -> 1

        the reset does not create a negative event count.
        """

        values = []

        for row in rows:

            value = (
                TripFeatureExtractor._numeric(
                    row.get(field)
                )
            )

            if value is not None:
                values.append(value)

        if not values:
            return None

        total = max(
            0.0,
            values[0]
        )

        for previous, current in zip(
            values,
            values[1:]
        ):

            delta = (
                current - previous
            )

            if delta > 0:
                total += delta

        return (
            int(total)
            if total.is_integer()
            else total
        )

    # ==================================================
    # LAST NUMERIC VALUE
    # ==================================================

    @staticmethod
    def _last_numeric(
        rows,
        field
    ):
        for row in reversed(rows):

            value = (
                TripFeatureExtractor._numeric(
                    row.get(field)
                )
            )

            if value is not None:
                return value

        return None

    # ==================================================
    # SUM NUMERIC
    # ==================================================

    @staticmethod
    def _sum_numeric(
        rows,
        field
    ):
        values = []

        for row in rows:

            value = (
                TripFeatureExtractor._numeric(
                    row.get(field)
                )
            )

            if value is not None:
                values.append(value)

        return (
            sum(values)
            if values
            else None
        )

    # ==================================================
    # MAX MICROSLEEP DURATION
    # ==================================================

    @staticmethod
    def _max_microsleep_duration(
        rows
    ):
        """
        Determine the maximum observed microsleep/closure
        duration from the available pipeline fields.

        Preferred:
            continuous_eye_closure

        Fallback:
            eye_closure_duration
        """

        durations = []

        for row in rows:

            detected = row.get(
                "microsleep_detected"
            )

            closure = (
                TripFeatureExtractor._numeric(
                    row.get(
                        "continuous_eye_closure"
                    )
                )
            )

            if closure is None:
                closure = (
                    TripFeatureExtractor._numeric(
                        row.get(
                            "eye_closure_duration"
                        )
                    )
                )

            is_detected = (
                detected is True
                or
                str(
                    detected
                ).lower() == "true"
            )

            if (
                closure is not None
                and is_detected
                and closure > 0
            ):
                durations.append(
                    closure
                )

        return (
            max(durations)
            if durations
            else None
        )

    # ==================================================
    # VEHICLE FEATURES
    # ==================================================

    @staticmethod
    def _extract_vehicle_features(
        context,
        rows
    ):

        if not rows:
            return {
                "avg_speed": None,
                "max_speed": None,
                "avg_throttle": None,
                "avg_brake": None,
                "steering_variability": None,
            }

        speeds = []
        throttles = []
        brakes = []
        steering = []

        for row in rows:

            speed = (
                TripFeatureExtractor._numeric(
                    row.get("speed")
                )
            )

            throttle = (
                TripFeatureExtractor._numeric(
                    row.get("throttle")
                )
            )

            brake = (
                TripFeatureExtractor._numeric(
                    row.get("brake")
                )
            )

            steer = (
                TripFeatureExtractor._numeric(
                    row.get("steering")
                )
            )

            if speed is not None:
                speeds.append(speed)

            if throttle is not None:
                throttles.append(throttle)

            if brake is not None:
                brakes.append(brake)

            if steer is not None:
                steering.append(steer)

        return {
            "avg_speed":
                TripFeatureExtractor._mean(
                    speeds
                ),

            "max_speed":
                (
                    max(speeds)
                    if speeds
                    else None
                ),

            "avg_throttle":
                TripFeatureExtractor._mean(
                    throttles
                ),

            "avg_brake":
                TripFeatureExtractor._mean(
                    brakes
                ),

            "steering_variability":
                TripFeatureExtractor._std(
                    steering
                ),
        }

    # ==================================================
    # EMERGENCY EVENTS
    # ==================================================

    @staticmethod
    def _extract_emergency_features(
        context,
        events
    ):

        count = len(events)

        if count == 0:
            return {
                "emergency_count": 0,
                "emergency_rate": 0.0,
                "emergency_risk_rate": 0.0,
            }

        severity_weights = {
            "low": 1.0,
            "medium": 2.0,
            "high": 4.0,
            "critical": 8.0,
        }

        risk = 0.0

        for event in events:

            severity = str(
                event.get(
                    "severity",
                    "medium"
                )
            ).lower()

            risk += severity_weights.get(
                severity,
                2.0
            )

        return {
            "emergency_count":
                count,

            "emergency_rate":
                count
                / context.duration_hours,

            "emergency_risk_rate":
                risk
                / context.duration_hours,
        }

    # ==================================================
    # HELPERS
    # ==================================================

    @staticmethod
    def _numeric(value):

        if value is None:
            return None

        try:
            return float(value)

        except (
            TypeError,
            ValueError
        ):
            return None

    @staticmethod
    def _mean(values):

        if not values:
            return None

        return (
            sum(values)
            / len(values)
        )

    @staticmethod
    def _std(values):

        if len(values) < 2:
            return 0.0

        mean = (
            sum(values)
            / len(values)
        )

        variance = (
            sum(
                (x - mean) ** 2
                for x in values
            )
            / len(values)
        )

        return variance ** 0.5

    # ==================================================
    # DATA COVERAGE
    # ==================================================

    @staticmethod
    def _calculate_coverage(
        observation_count,
        duration_seconds
    ):
        """
        V1 coverage proxy.

        Current pipeline writes approximately once per second,
        so valid observations / trip seconds provides a rough
        coverage estimate.

        This should eventually be replaced with a proper
        expected-vs-observed sampling calculation.
        """

        if duration_seconds <= 0:
            return 0.0

        return min(
            1.0,
            observation_count
            / max(
                1.0,
                duration_seconds
            )
        )