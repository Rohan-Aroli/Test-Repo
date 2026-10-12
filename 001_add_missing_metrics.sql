-- Migration 001: Add missing fatigue tracking metrics to driver_metrics table
ALTER TABLE driver_metrics ADD COLUMN IF NOT EXISTS yawn_count int4;
ALTER TABLE driver_metrics ADD COLUMN IF NOT EXISTS avg_yawn_duration float8;
ALTER TABLE driver_metrics ADD COLUMN IF NOT EXISTS microsleep_count int4;
ALTER TABLE driver_metrics ADD COLUMN IF NOT EXISTS continuous_eye_closure float8;
ALTER TABLE driver_metrics ADD COLUMN IF NOT EXISTS microsleep_detected bool;
ALTER TABLE driver_metrics ADD COLUMN IF NOT EXISTS avg_microsleep_duration float8;
