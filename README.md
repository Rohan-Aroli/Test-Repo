# Driver Monitoring System (DMS)

An end-to-end computer vision and telematics system that continuously monitors driver alertness, detects drowsiness/fatigue/microsleep in real time, streams video via FastAPI, syncs state to Supabase, and integrates with the CARLA autonomous driving simulator.

---

## 📌 Architecture Overview

```
                        ┌────────────────────────┐
                        │   Webcam / Camera Feed │
                        └───────────┬────────────┘
                                    │
                                    ▼
                     ┌─────────────────────────────┐
                     │  Face & Landmark Extraction │
                     │   (MediaPipe FaceMesh)      │
                     └──────────────┬──────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌──────────────────┐      ┌──────────────────┐      ┌────────────────────┐
│ Eye Aspect Ratio │      │ Mouth Aspect     │      │ Head Pose (Pitch,  │
│  (EAR & PERCLOS) │      │  Ratio (MAR)     │      │   Yaw, Roll)       │
└────────┬─────────┘      └────────┬─────────┘      └─────────┬──────────┘
         │                         │                          │
         └─────────────────────────┼──────────────────────────┘
                                   │
                                   ▼
             ┌──────────────────────────────────────────────┐
             │   Enhanced Driver State Classifier           │
             │   (NORMAL / DROWSY / UNRESPONSIVE / WAITING) │
             └─────────────────────┬────────────────────────┘
                                   │
      ┌────────────────────────────┼────────────────────────────┐
      ▼                            ▼                            ▼
┌──────────────┐         ┌────────────────────┐       ┌───────────────────┐
│ FastAPI Live │         │  Supabase Cloud    │       │ Shared State File │
│ MJPEG Stream │         │  Metrics & Events  │       │ driver_state.json │
│ (/video_feed)│         │  Storage Evidence  │       │ (CARLA Simulator) │
└──────────────┘         └────────────────────┘       └───────────────────┘
```

---

## 📂 Project Structure

```
driver monitoring/
├── Main.py                     # Primary system launcher
├── subprocess_launcher.py      # Subprocess lifecycle manager for CV pipeline
├── System_paths_config.py      # Python executable and module path resolver
├── pytest.ini                  # Pytest configuration and path discovery
├── requirements_main.txt       # Root environment package dependencies
├── shared/
│   ├── driver_state.json       # Real-time state synchronized with CARLA
│   └── all_scores.json         # Real-time fatigue metric snapshots
├── backend/
│   └── __init__.py             # Namespace bridge to face_detection_codes backend
├── carla_codes/                # CARLA simulator integration
│   ├── main.py                 # CARLA vehicle & autopilot launcher
│   ├── vehicle_control.py      # Control loop listening to driver_state.json
│   ├── vehicle_functions.py    # Hazard lights, horn, and warning controls
│   ├── custom_vehicle_physics.py# Emergency pullover maneuver implementation
│   └── spawn_car_and_camera.py # Spawn actors and virtual cabin camera
├── face_detection_codes/       # Computer Vision & Telematics Core
│   ├── main.py                 # CV detection loop & FastAPI server
│   ├── dashboard.py            # Desktop GUI monitor (Tkinter)
│   ├── streamlit_app.py        # Web dashboard & driver registration
│   ├── requirements.txt        # Sub-environment dependencies
│   ├── backend/
│   │   ├── database_writer.py  # Supabase telemetry & event writer
│   │   ├── supabase_client.py  # Supabase client with offline fallback
│   │   ├── frame_uploader.py   # Incident evidence frame uploader
│   │   ├── push_metrics.py     # Real-time metrics dispatching
│   │   └── Streaming_frames_endpoint.py # FastAPI MJPEG streaming service
│   ├── detection/
│   │   ├── face_detection.py   # MediaPipe face detector
│   │   ├── eye_landmark_extractor.py # 6-point eye landmark extractor
│   │   ├── mouth_landmark_extractor.py # 8-point mouth landmark extractor
│   │   └── head_pose_estimator.py # 3D PnP head pose estimator (Euler angles)
│   ├── metrics/
│   │   ├── ear_calculator.py   # Eye Aspect Ratio calculation
│   │   ├── drowsiness_detector.py # EAR smoothing, blink rate & PERCLOS
│   │   ├── mar_calculator.py   # Mouth Aspect Ratio calculation
│   │   ├── yawn_detector.py    # Yawn frequency & duration tracker
│   │   ├── microsleep_detector.py # Sustained eye-closure detector
│   │   └── baseline_calibration.py # Per-driver baseline calibration
│   ├── core/
│   │   ├── frame_bridge.py     # Thread-safe frame queue for API stream
│   │   ├── enhanced_driver_state_classifier.py # Multi-metric state engine
│   │   ├── system_mode_manager.py # CALIBRATION / MONITORING modes
│   │   └── logger.py           # Synchronized JSON file loggers
│   ├── DriverScore/            # Post-trip safety and risk scoring
│   │   ├── scoring_pipeline.py # End-of-trip score aggregation
│   │   ├── driver_score.py     # Multi-component score weighting
│   │   ├── db_repository.py    # Repository for trips & historical data
│   │   └── models.py           # Pydantic data models
│   └── Tests/                  # Automated PyTest test suite
│       ├── test_backend_refactor.py
│       ├── test_driver_score.py
│       ├── test_enhanced_driver_state_classifier.py
│       ├── test_historical_features.py
│       ├── test_livestream.py
│       ├── test_normalization.py
│       └── test_trip_features.py
```

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- **Python**: Recommended Python 3.10.x to 3.12.x on Windows / Linux / macOS.
- **Webcam**: Standard USB or integrated webcam (camera index `0`).

### 2. Virtual Environment Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate on Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Install project dependencies
pip install -r requirements_main.txt
```

> [!NOTE]
> Ensure `mediapipe==0.10.14` is installed. Versions `>=0.10.15` deprecate the legacy `mediapipe.solutions` API used by real-time landmark meshes.

### 3. Environment Variables (`.env`)

Create or update `.env` in `face_detection_codes/.env` or root:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-publishable-or-service-key
STREAM_PORT=8000
```

> [!TIP]
> If Supabase credentials are not provided or the network is unavailable, the system automatically runs in **offline mode** without crashing.

---

## 🚀 Running the System

### Option A: Complete System Launch (Recommended)
Launches the full driver monitoring pipeline as a supervised subprocess:
```bash
python Main.py
```
To stop, press `Ctrl+C` in the terminal.

### Option B: Face Detection & Telematics Only
```bash
python face_detection_codes/main.py
```

### Option C: Desktop GUI Dashboard
```bash
python face_detection_codes/dashboard.py
```

### Option D: Streamlit Web Dashboard
```bash
streamlit run face_detection_codes/streamlit_app.py
```

### Option E: CARLA Autonomous Driving Integration
Ensure CARLA Simulator is running on `localhost:2000`, then:
```bash
python carla_codes/main.py
```
The vehicle will automatically respond to driver states in real time:
- **NORMAL**: Autonomous driving / cruising.
- **DROWSY**: Hazard lights activated, audio warning honks, 25% speed reduction.
- **UNRESPONSIVE**: Autopilot disengaged, emergency pulled over safely to the road shoulder.

---

## 🌐 FastAPI Streaming Endpoints

When face detection is active, a FastAPI server runs concurrently (default `http://127.0.0.1:8000`):

- **`GET /`**: API status and available routes.
- **`GET /health`**: Health status and camera stream activity (`camera_stream_active`).
- **`GET /video_feed`**: Live MJPEG video stream suitable for `<img>` tags in browsers or dashboards.

---

## 🧪 Running Automated Tests

Run the full pytest suite from the project root:

```bash
pytest
```

Or target the test directory directly:
```bash
pytest face_detection_codes/Tests -v
```

