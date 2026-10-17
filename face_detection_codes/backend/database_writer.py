from datetime import datetime, timezone
from time import sleep
from uuid import UUID, uuid4

import httpx


class DatabaseUnavailableError(RuntimeError):
    """Raised when a database request cannot reach Supabase."""


class DatabaseWriter:
    _MAX_REQUEST_ATTEMPTS = 3

    def __init__(self, client):
        self.client = client

    def _execute_with_retry(self, request):
        for attempt in range(self._MAX_REQUEST_ATTEMPTS):
            try:
                return request.execute()
            except httpx.RequestError as exc:
                if attempt == self._MAX_REQUEST_ATTEMPTS - 1:
                    raise DatabaseUnavailableError(
                        "Supabase could not be reached after "
                        f"{self._MAX_REQUEST_ATTEMPTS} attempts."
                    ) from exc
                sleep(0.25 * (2**attempt))

    def find_driver(self, identifier):
        identifier = str(identifier).strip()
        if not identifier:
            return None

        response = (
            self.client
            .table("drivers")
            .select("*")
            .eq("employee_id", identifier)
            .limit(1)
        )
        response = self._execute_with_retry(response)

        if response.data:
            return response.data[0]

        try:
            UUID(identifier)
        except ValueError:
            return None

        response = (
            self.client
            .table("drivers")
            .select("*")
            .eq("id", identifier)
            .limit(1)
        )
        response = self._execute_with_retry(response)

        return response.data[0] if response.data else None

    def register_driver(self, driver_id, profile):
        payload = {
            "id": str(driver_id),
            "name": profile["name"],
            "license": profile.get("license"),
            "vehicle": profile.get("vehicle"),
            "plate": profile.get("plate"),
            "route": profile.get("route"),
            "origin": profile.get("origin"),
            "destination": profile.get("destination"),
            "shift_start": profile.get("shift_start"),
            "notes": profile.get("notes"),
            "employee_id": profile.get("employee_id"),
            "age": profile.get("age"),
            "contact": profile.get("contact"),
            "fleet_id": profile.get("fleet_id"),
        }

        response = (
            self.client
            .table("drivers")
            .insert(payload)
            .execute()
        )

        return response.data[0] if response.data else payload

    def start_trip(self, driver_id, start_time=None, details=None):
        details = details or {}
        payload = {
            "trip_id": str(uuid4()),
            "driver_id": str(driver_id),
            "start_time": self._timestamp(start_time),
            "origin": details.get("origin"),
            "destination": details.get("destination"),
            "route": details.get("route"),
        }

        response = (
            self.client
            .table("trips")
            .insert(payload)
            .execute()
        )

        return response.data[0] if response.data else payload

    def end_trip(self, trip_id, end_time=None):
        response = (
            self.client
            .table("trips")
            .update({"end_time": self._timestamp(end_time)})
            .eq("trip_id", str(trip_id))
            .execute()
        )

        return response.data[0] if response.data else None

    def write_driver_metrics(
        self,
        metrics,
        driver_id,
        trip_id,
        driver_state,
    ):
        """Legacy optional call for explicit historical snapshots.

        The project now keeps high-frequency driver telemetry in Python memory and
        writes only current state and important events to Supabase.
        """
        payload = {
            "ear": self._float(metrics.get("ear")),
            "perclos": self._float(metrics.get("perclos")),
            "blink_rate": self._int(metrics.get("blink_rate")),
            "driver_state": str(driver_state),
            "fatigue_score": self._float(
                metrics.get("drowsiness_score")
            ),
            "eye_closure_duration": self._float(
                metrics.get("avg_closure_duration")
            ),
            "driver_uuid": str(driver_id),
            "trip_id": str(trip_id),
            "created_at": self._timestamp(),
        }

        return (
            self.client
            .table("driver_metrics")
            .insert(payload)
            .execute()
        )

    def update_live_driver_state(
        self,
        metrics,
        driver_id,
        driver_state,
        frame_url=None,
    ):
        payload = {
            "updated_at": self._timestamp(),
            "ear": self._float(metrics.get("ear")),
            "perclos": self._float(metrics.get("perclos")),
            "blink_rate": self._int(metrics.get("blink_rate")),
            "driver_state": str(driver_state),
            "fatigue_score": self._float(
                metrics.get("drowsiness_score")
            ),
            "eye_closure_duration": self._float(
                metrics.get("avg_closure_duration")
            ),
            "driver_id": str(driver_id),
        }

        if frame_url is not None:
            payload["frame_url"] = frame_url

        existing = (
            self.client
            .table("live_driver_state")
            .select("id")
            .eq("driver_id", str(driver_id))
            .limit(1)
            .execute()
        )

        if existing.data:
            return (
                self.client
                .table("live_driver_state")
                .update(payload)
                .eq("driver_id", str(driver_id))
                .execute()
            )

        payload["driver_id"] = str(driver_id)
        return (
            self.client
            .table("live_driver_state")
            .insert(payload)
            .execute()
        )

    def update_latest_driver_frame(self, driver_id, frame_url):
        payload = {
            "frame_url": frame_url,
            "updated_at": self._timestamp(),
            "driver_id": str(driver_id),
        }

        existing = (
            self.client
            .table("latest_driver_frame")
            .select("id")
            .eq("driver_id", str(driver_id))
            .limit(1)
            .execute()
        )

        if existing.data:
            return (
                self.client
                .table("latest_driver_frame")
                .update(payload)
                .eq("driver_id", str(driver_id))
                .execute()
            )

        return (
            self.client
            .table("latest_driver_frame")
            .insert(payload)
            .execute()
        )

    def write_frame(self, frame_url, driver_id):
        payload = {
            "frame_url": frame_url,
            "updated_at": self._timestamp(),
            "driver_id": str(driver_id),
        }

        response = (
            self.client
            .table("driver_frames")
            .insert(payload)
            .execute()
        )

        self.update_latest_driver_frame(driver_id, frame_url)
        return response

    def write_event(
        self,
        event_type,
        driver_id,
        trip_id,
        start_time=None,
        end_time=None,
        duration_seconds=None,
        severity=None,
        metadata=None,
    ):
        payload = {
            "driver_id": str(driver_id),
            "event_type": str(event_type),
            "start_time": self._timestamp(start_time),
            "end_time": self._timestamp(end_time) if end_time else None,
            "duration_seconds": self._float(duration_seconds),
            "severity": severity,
            "metadata": metadata or {},
            "created_at": self._timestamp(),
        }

        if trip_id is not None:
            payload["trip_id"] = str(trip_id)

        return (
            self.client
            .table("driver_events")
            .insert(payload)
            .execute()
        )

    def write_emergency_event(
        self,
        event_type,
        severity,
        event_message,
        driver_id,
        trip_id=None,
        fleet_id=None,
        location=None,
        resolved=False,
    ):
        payload = {
            "event_type": str(event_type),
            "severity": severity,
            "event_message": event_message,
            "resolved": bool(resolved),
            "driver_id": str(driver_id) if driver_id else None,
            "fleet_id": str(fleet_id) if fleet_id else None,
            "location": location,
            "trip_id": str(trip_id) if trip_id else None,
            "created_at": self._timestamp(),
        }

        return (
            self.client
            .table("emergency_events")
            .insert(payload)
            .execute()
        )

    def save_driver_baseline(self, driver_id, baseline_payload):
        payload = {
            "driver_id": str(driver_id),
            "avg_ear": self._float(baseline_payload.get("avg_ear")),
            "avg_mar": self._float(baseline_payload.get("avg_mar")),
            "avg_perclos": self._float(baseline_payload.get("avg_perclos")),
            "avg_blink_rate": self._float(
                baseline_payload.get("avg_blink_rate")
            ),
            "avg_eye_closure_duration": self._float(
                baseline_payload.get("avg_eye_closure_duration")
            ),
            "sample_count": self._int(baseline_payload.get("sample_count")),
        }

        return self.client.table("driver_baselines").upsert(payload).execute()

    def get_driver_baseline(self, driver_id):
        response = (
            self.client
            .table("driver_baselines")
            .select("*")
            .eq("driver_id", str(driver_id))
            .limit(1)
            .execute()
        )

        return response.data[0] if response.data else None

    @staticmethod
    def _timestamp(value=None):
        if value is None:
            value = datetime.now(timezone.utc)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return str(value)

    @staticmethod
    def _float(value):
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _int(value):
        if value is None:
            return None
        return int(value)