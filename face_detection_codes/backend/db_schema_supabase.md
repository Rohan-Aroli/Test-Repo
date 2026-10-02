## Table `driver_metrics`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary |
| `created_at` | `timestamptz` |  Nullable |
| `ear` | `float8` |  Nullable |
| `perclos` | `float8` |  Nullable |
| `blink_rate` | `int4` |  Nullable |
| `driver_state` | `text` |  Nullable |
| `fatigue_score` | `float8` |  Nullable |
| `head_pose` | `text` |  Nullable |
| `eye_closure_duration` | `float8` |  Nullable |
| `driver_id` | `uuid` |  Nullable |
| `trip_id` | `uuid` |  Nullable |

## Table `driver_baselines`

| Name | Type | Constraints |
|------|------|-------------|
| `driver_id` | `text` | Primary; formatted application Driver ID |
| `avg_ear` | `float8` |  Nullable |
| `avg_mar` | `float8` |  Nullable |
| `avg_perclos` | `float8` |  Nullable |
| `avg_blink_rate` | `float8` |  Nullable |
| `avg_eye_closure_duration` | `float8` |  Nullable |
| `sample_count` | `int4` |  Nullable |
| `created_at` | `timestamptz` |  Default `now()` |
| `updated_at` | `timestamptz` |  Default `now()` |

## Table `vehicle_metrics`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary |
| `created_at` | `timestamptz` |  Nullable |
| `speed` | `float8` |  Nullable |
| `throttle` | `float8` |  Nullable |
| `brake` | `float8` |  Nullable |
| `steering` | `float8` |  Nullable |
| `hazard_lights` | `bool` |  Nullable |
| `vehicle_state` | `text` |  Nullable |
| `fleet_id` | `uuid` |  Nullable |
| `driver_id` | `uuid` |  Nullable |
| `trip_id` | `uuid` |  Nullable |

## Table `emergency_events`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary |
| `created_at` | `timestamptz` |  Nullable |
| `event_type` | `text` |  Nullable |
| `severity` | `text` |  Nullable |
| `event_message` | `text` |  Nullable |
| `resolved` | `bool` |  Nullable |
| `driver_id` | `uuid` |  Nullable |
| `fleet_id` | `uuid` |  Nullable |
| `location` | `text` |  Nullable |
| `trip_id` | `uuid` |  Nullable |

## Table `live_driver_state`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `updated_at` | `timestamp` |  Nullable |
| `ear` | `float8` |  Nullable |
| `perclos` | `float8` |  Nullable |
| `blink_rate` | `int4` |  Nullable |
| `driver_state` | `text` |  Nullable |
| `fatigue_score` | `float8` |  Nullable |
| `eye_closure_duration` | `float8` |  Nullable |
| `frame_url` | `text` |  Nullable |
| `driver_id` | `uuid` |  Nullable |

## Table `driver_frames`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `frame_url` | `text` |  Nullable |
| `updated_at` | `timestamp` |  Nullable |
| `driver_id` | `uuid` |  Nullable |

## Table `latest_driver_frame`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `frame_url` | `text` |  Nullable |
| `updated_at` | `timestamp` |  Nullable |
| `driver_id` | `uuid` |  Nullable |

## Table `drivers`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `name` | `text` |  |
| `license` | `text` |  Nullable |
| `vehicle` | `text` |  Nullable |
| `plate` | `text` |  Nullable |
| `route` | `text` |  Nullable |
| `origin` | `text` |  Nullable |
| `destination` | `text` |  Nullable |
| `shift_start` | `text` |  Nullable |
| `notes` | `text` |  Nullable |
| `created_at` | `timestamptz` |  |
| `employee_id` | `text` |  Nullable |
| `age` | `int4` |  Nullable |
| `contact` | `text` |  Nullable |
| `fleet_id` | `uuid` |  Nullable |
| `profile_photo` | `text` |  Nullable |

## Table `users`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `name` | `text` |  |
| `email` | `text` |  Unique |
| `password` | `text` |  |
| `phone` | `text` |  Nullable |
| `role` | `text` |  Nullable |
| `profile_photo` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `fleets`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `fleet_name` | `text` |  |
| `vehicle_number` | `text` |  Nullable |
| `driver_id` | `uuid` |  Nullable |
| `status` | `text` |  Nullable |
| `latitude` | `float8` |  Nullable |
| `longitude` | `float8` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `trips`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `trip_id` | `uuid` | Primary |
| `driver_id` | `uuid` |  |
| `start_time` | `timestamptz` |  |
| `end_time` | `timestamptz` |  Nullable |
| `origin` | `text` |  Nullable |
| `destination` | `text` |  Nullable |
| `route` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `trip_features`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `trip_id` | `uuid` |  |
| `driver_id` | `uuid` |  |
| `calculated_at` | `timestamptz` |  Nullable |
| `duration_seconds` | `float8` |  Nullable |
| `duration_hours` | `float8` |  Nullable |
| `avg_perclos` | `float8` |  Nullable |
| `high_perclos_seconds` | `float8` |  Nullable |
| `high_perclos_time_pct` | `float8` |  Nullable |
| `drowsy_seconds` | `float8` |  Nullable |
| `drowsy_time_pct` | `float8` |  Nullable |
| `drowsy_episode_count` | `int4` |  Nullable |
| `drowsy_episode_rate` | `float8` |  Nullable |
| `avg_drowsy_episode_duration` | `float8` |  Nullable |
| `max_drowsy_episode_duration` | `float8` |  Nullable |
| `unresponsive_seconds` | `float8` |  Nullable |
| `unresponsive_time_pct` | `float8` |  Nullable |
| `unresponsive_episode_count` | `int4` |  Nullable |
| `unresponsive_rate` | `float8` |  Nullable |
| `avg_blink_rate` | `float8` |  Nullable |
| `blink_deviation` | `float8` |  Nullable |
| `yawn_count` | `int4` |  Nullable |
| `yawn_rate` | `float8` |  Nullable |
| `avg_yawn_duration` | `float8` |  Nullable |
| `microsleep_count` | `int4` |  Nullable |
| `microsleep_rate` | `float8` |  Nullable |
| `avg_microsleep_duration` | `float8` |  Nullable |
| `max_microsleep_duration` | `float8` |  Nullable |
| `distraction_count` | `int4` |  Nullable |
| `distraction_rate` | `float8` |  Nullable |
| `distracted_seconds` | `float8` |  Nullable |
| `distracted_time_pct` | `float8` |  Nullable |
| `emergency_count` | `int4` |  Nullable |
| `emergency_rate` | `float8` |  Nullable |
| `emergency_risk_rate` | `float8` |  Nullable |
| `avg_speed` | `float8` |  Nullable |
| `max_speed` | `float8` |  Nullable |
| `avg_throttle` | `float8` |  Nullable |
| `avg_brake` | `float8` |  Nullable |
| `steering_variability` | `float8` |  Nullable |
| `driver_data_coverage` | `float8` |  Nullable |
| `vehicle_data_coverage` | `float8` |  Nullable |

## Table `driver_score_history`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `driver_id` | `uuid` |  |
| `trip_id` | `uuid` |  Nullable |
| `calculated_at` | `timestamptz` |  Nullable |
| `fatigue_score` | `float8` |  Nullable |
| `safety_score` | `float8` |  Nullable |
| `attention_score` | `float8` |  Nullable |
| `experience_score` | `float8` |  Nullable |
| `health_score` | `float8` |  Nullable |
| `raw_driver_score` | `float8` |  Nullable |
| `final_driver_score` | `float8` |  Nullable |
| `critical_event` | `bool` |  Nullable |
| `score_cap` | `float8` |  Nullable |
| `trips_analyzed` | `int4` |  Nullable |
| `driving_hours_analyzed` | `float8` |  Nullable |
| `score_confidence` | `text` |  Nullable |
| `data_quality` | `float8` |  Nullable |
| `normalization_version` | `text` |  Nullable |

## Table `driver_events`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `event_id` | `int8` | Primary Identity |
| `driver_id` | `uuid` |  |
| `trip_id` | `uuid` |  |
| `event_type` | `text` |  |
| `start_time` | `timestamptz` |  |
| `end_time` | `timestamptz` |  Nullable |
| `duration_seconds` | `float8` |  Nullable |
| `severity` | `text` |  Nullable |
| `metadata` | `jsonb` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## RLS Policies

### `live_driver_state`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Public read` | SELECT | public | PERMISSIVE | `true` | — |

### `latest_driver_frame`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Public read` | SELECT | public | PERMISSIVE | `true` | — |

### `drivers`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Allow auth access` | ALL | authenticated | PERMISSIVE | `true` | — |
| `Public delete` | DELETE | public | PERMISSIVE | `true` | — |
| `Public insert` | INSERT | public | PERMISSIVE | — | `true` |
| `Public read` | SELECT | public | PERMISSIVE | `true` | — |
| `Public update` | UPDATE | public | PERMISSIVE | `true` | — |

