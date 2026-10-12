from datetime import datetime, timezone
from uuid import UUID, uuid4


class DatabaseWriter:

    def __init__(self, client):
        self.client = client

    def find_driver(self, identifier):
        identifier = str(identifier).strip()
        if not identifier:
            return None
        if not self.client:
            return None

        try:
            response = (
                self.client
                .table("drivers")
                .select("*")
                .eq("employee_id", identifier)
                .limit(1)
                .execute()
            )

            if response and getattr(response, "data", None):
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
                .execute()
            )

            return response.data[0] if (response and getattr(response, "data", None)) else None
        except Exception as e:
            print(f"[DB WARNING] find_driver failed: {e}")
            return None

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
        if not self.client:
            return payload

        try:
            response = (
                self.client
                .table("drivers")
                .insert(payload)
                .execute()
            )

            return response.data[0] if (response and getattr(response, "data", None)) else payload
        except Exception as e:
            print(f"[DB WARNING] register_driver failed: {e}")
            return payload

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
        if not self.client:
            return payload

        try:
            response = (
                self.client
                .table("trips")
                .insert(payload)
                .execute()
            )

            return response.data[0] if (response and getattr(response, "data", None)) else payload
        except Exception as e:
            print(f"[DB WARNING] start_trip failed: {e}")
            return payload

    def end_trip(self, trip_id, end_time=None):
        if not self.client:
            return None

        try:
            response = (
                self.client
                .table("trips")
                .update({"end_time": self._timestamp(end_time)})
                .eq("trip_id", str(trip_id))
                .execute()
            )

            return response.data[0] if (response and getattr(response, "data", None)) else None
        except Exception as e:
            print(f"[DB WARNING] end_trip failed: {e}")
            return None

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
            "id": f"{driver_id}:{uuid4()}",
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
            "yawn_count": self._int(metrics.get("yawn_count")),
            "avg_yawn_duration": self._float(metrics.get("avg_yawn_duration")),
            "microsleep_count": self._int(metrics.get("microsleep_count")),
            "continuous_eye_closure": self._float(metrics.get("continuous_eye_closure")),
            "microsleep_detected": bool(metrics.get("microsleep_detected")),
            "avg_microsleep_duration": self._float(metrics.get("avg_microsleep_duration")),
            "driver_id": str(driver_id),
            "trip_id": str(trip_id),
            "created_at": self._timestamp(),
        }

        if not self.client:
            return None

        try:
            return (
                self.client
                .table("driver_metrics")
                .insert(payload)
                .execute()
            )
        except Exception as e:
            print(f"[DB WARNING] write_driver_metrics failed: {e}")
            err_msg = str(e).lower()
            if "column" in err_msg or "schema" in err_msg or "syntax" in err_msg or "type" in err_msg:
                try:
                    core_payload = {
                        "ear": payload["ear"],
                        "perclos": payload["perclos"],
                        "blink_rate": payload["blink_rate"],
                        "driver_state": payload["driver_state"],
                        "fatigue_score": payload["fatigue_score"],
                        "eye_closure_duration": payload["eye_closure_duration"],
                        "driver_id": payload["driver_id"],
                        "trip_id": payload["trip_id"],
                        "created_at": payload["created_at"],
                    }
                    return (
                        self.client
                        .table("driver_metrics")
                        .insert(core_payload)
                        .execute()
                    )
                except Exception as inner_e:
                    print(f"[DB WARNING] write_driver_metrics core fallback failed: {inner_e}")
            return None

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

        if not self.client:
            return None

        try:
            existing = (
                self.client
                .table("live_driver_state")
                .select("id")
                .eq("driver_id", str(driver_id))
                .limit(1)
                .execute()
            )

            if existing and getattr(existing, "data", None):
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
        except Exception as e:
            print(f"[DB WARNING] update_live_driver_state failed: {e}")
            return None

    def update_latest_driver_frame(self, driver_id, frame_url):
        payload = {
            "frame_url": frame_url,
            "updated_at": self._timestamp(),
            "driver_id": str(driver_id),
        }
        if not self.client:
            return None

        try:
            existing = (
                self.client
                .table("latest_driver_frame")
                .select("id")
                .eq("driver_id", str(driver_id))
                .limit(1)
                .execute()
            )

            if existing and getattr(existing, "data", None):
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
        except Exception as e:
            print(f"[DB WARNING] update_latest_driver_frame failed: {e}")
            return None

    def write_frame(self, frame_url, driver_id):
        payload = {
            "frame_url": frame_url,
            "updated_at": self._timestamp(),
            "driver_id": str(driver_id),
        }
        if not self.client:
            return None

        try:
            response = (
                self.client
                .table("driver_frames")
                .insert(payload)
                .execute()
            )

            self.update_latest_driver_frame(driver_id, frame_url)
            return response
        except Exception as e:
            print(f"[DB WARNING] write_frame failed: {e}")
            return None

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

        if not self.client:
            return None

        try:
            return (
                self.client
                .table("driver_events")
                .insert(payload)
                .execute()
            )
        except Exception as e:
            print(f"[DB WARNING] write_event failed: {e}")
            return None

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

        if not self.client:
            return None

        try:
            return (
                self.client
                .table("emergency_events")
                .insert(payload)
                .execute()
            )
        except Exception as e:
            print(f"[DB WARNING] write_emergency_event failed: {e}")
            return None

    def save_driver_baseline(self, driver_id, baseline_payload):
        payload = {
            "id": str(driver_id),
            "created_at": self._timestamp(),
            "ear": self._float(baseline_payload.get("ear_mean")),
            "perclos": self._float(baseline_payload.get("perclos_mean")),
            "blink_rate": self._int(baseline_payload.get("blink_rate_mean")),
            "driver_state": "NORMAL",
            "eye_closure_duration": self._float(
                baseline_payload.get("eye_closure_duration_mean")
            ),
            "driver_id": str(driver_id),
        }
        if not self.client:
            return None

        try:
            table = self.client.table("driver_metrics")
            existing = table.select("id").eq("id", str(driver_id)).limit(1).execute()
            if existing and getattr(existing, "data", None):
                return table.update(payload).eq("id", str(driver_id)).execute()
            return table.insert(payload).execute()
        except Exception as e:
            print(f"[DB WARNING] save_driver_baseline failed: {e}")
            return None

    def get_driver_baseline(self, driver_id):
        if not self.client:
            return None

        try:
            response = (
                self.client
                .table("driver_metrics")
                .select("*")
                .eq("driver_id", str(driver_id))
                .eq("driver_state", "NORMAL")
                .is_("trip_id", "null")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            return response.data[0] if (response and getattr(response, "data", None)) else None
        except Exception as e:
            print(f"[DB WARNING] get_driver_baseline failed: {e}")
            return None

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