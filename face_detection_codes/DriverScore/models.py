from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TripContext:
    """
    Identifies a single driving trip and its time boundaries.
    """

    trip_id: str
    driver_id: str
    trip_start: datetime
    trip_end: datetime

    @property
    def duration_seconds(self) -> float:
        return (
            self.trip_end - self.trip_start
        ).total_seconds()

    @property
    def duration_hours(self) -> float:
        return self.duration_seconds / 3600.0


@dataclass
class TripFeatures:
    """
    Temporal features extracted from one driving trip.

    Raw sensor values should not be directly used for the
    long-term Driver Score. This model stores derived,
    trip-level features.
    """

    trip_id: str
    driver_id: str
    calculated_at: datetime

    duration_seconds: float
    duration_hours: float

    # ==================================================
    # FATIGUE
    # ==================================================

    avg_perclos: Optional[float]
    high_perclos_seconds: float
    high_perclos_time_pct: Optional[float]

    drowsy_seconds: float
    drowsy_time_pct: Optional[float]
    drowsy_episode_count: int
    drowsy_episode_rate: Optional[float]
    avg_drowsy_episode_duration: Optional[float]
    max_drowsy_episode_duration: Optional[float]

    unresponsive_seconds: float
    unresponsive_time_pct: Optional[float]
    unresponsive_episode_count: int
    unresponsive_rate: Optional[float]

    avg_blink_rate: Optional[float]
    blink_deviation: Optional[float]

    # ==================================================
    # YAWN
    # ==================================================

    yawn_count: Optional[int] = None
    yawn_rate: Optional[float] = None
    avg_yawn_duration: Optional[float] = None

    # ==================================================
    # MICROSLEEP
    # ==================================================

    microsleep_count: Optional[int] = None
    microsleep_rate: Optional[float] = None
    avg_microsleep_duration: Optional[float] = None
    max_microsleep_duration: Optional[float] = None

    # ==================================================
    # ATTENTION / DISTRACTION
    # ==================================================

    distraction_count: Optional[int] = None
    distraction_rate: Optional[float] = None
    distracted_seconds: Optional[float] = None
    distracted_time_pct: Optional[float] = None

    # ==================================================
    # SAFETY
    # ==================================================

    emergency_count: int = 0
    emergency_rate: Optional[float] = None
    emergency_risk_rate: Optional[float] = None

    # ==================================================
    # VEHICLE DESCRIPTIVE FEATURES
    # ==================================================

    avg_speed: Optional[float] = None
    max_speed: Optional[float] = None
    avg_throttle: Optional[float] = None
    avg_brake: Optional[float] = None
    steering_variability: Optional[float] = None

    # ==================================================
    # DATA QUALITY
    # ==================================================

    driver_data_coverage: float = 0.0
    vehicle_data_coverage: float = 0.0


@dataclass
class HistoricalFeatures:
    """
    Exposure-weighted and recency-weighted historical features
    accumulated across multiple trips for one driver.
    """

    driver_id: str
    trips_analyzed: int
    driving_hours_analyzed: float

    # ==================================================
    # FATIGUE
    # ==================================================

    avg_perclos: Optional[float]
    high_perclos_time_pct: Optional[float]

    drowsy_time_pct: Optional[float]
    drowsy_episode_rate: Optional[float]

    unresponsive_rate: Optional[float]
    unresponsive_time_pct: Optional[float]

    blink_deviation: Optional[float]

    # ==================================================
    # YAWN
    # ==================================================

    yawn_rate: Optional[float]
    avg_yawn_duration: Optional[float]

    # ==================================================
    # MICROSLEEP
    # ==================================================

    microsleep_rate: Optional[float]
    avg_microsleep_duration: Optional[float]
    max_microsleep_duration: Optional[float]

    # ==================================================
    # ATTENTION
    # ==================================================

    distraction_rate: Optional[float]
    distracted_time_pct: Optional[float]

    # ==================================================
    # SAFETY
    # ==================================================

    emergency_rate: Optional[float]
    emergency_risk_rate: Optional[float]

    # ==================================================
    # VEHICLE
    # ==================================================

    avg_speed: Optional[float]
    max_speed: Optional[float]
    avg_throttle: Optional[float]
    avg_brake: Optional[float]
    steering_variability: Optional[float]


@dataclass
class NormalizedFeatures:
    """
    Normalized 0-100 representations of historical risk metrics.
    Higher score means better performance.
    """

    # Fatigue
    perclos_score: Optional[float]
    high_perclos_score: Optional[float]

    drowsy_time_score: Optional[float]
    drowsy_episode_score: Optional[float]

    unresponsive_score: Optional[float]

    blink_score: Optional[float]

    # Yawn
    yawn_rate_score: Optional[float]
    yawn_duration_score: Optional[float]

    # Microsleep
    microsleep_rate_score: Optional[float]
    microsleep_duration_score: Optional[float]
    max_microsleep_score: Optional[float]

    # Attention
    distraction_rate_score: Optional[float]
    distracted_time_score: Optional[float]

    # Safety
    emergency_score: Optional[float]
    braking_score: Optional[float]
    acceleration_score: Optional[float]
    steering_score: Optional[float]


@dataclass
class DriverScore:
    """
    Final Driver Score and supporting metadata.
    """

    driver_id: str

    # Component scores
    fatigue_score: Optional[float]
    safety_score: Optional[float]
    attention_score: Optional[float]
    experience_score: Optional[float]
    health_score: Optional[float]

    # Final score
    raw_driver_score: Optional[float]
    final_driver_score: Optional[float]

    # Critical-event handling
    critical_event: bool
    score_cap: Optional[float]

    # Historical coverage
    trips_analyzed: int
    driving_hours_analyzed: float

    # Reliability
    score_confidence: str
    data_quality: float

    # Versioning
    normalization_version: str


@dataclass
class FinalizationResult:
    """
    Outcome of finalizing and persisting one driving trip score.
    """

    success: bool
    score: Optional[DriverScore]
    error: Optional[str]