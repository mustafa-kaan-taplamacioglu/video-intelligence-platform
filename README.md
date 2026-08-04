> **Disclaimer**: This is a personal portfolio project. It is a prototype, not
> production software. See [DISCLAIMER.md](./DISCLAIMER.md) and
> [LegalandOtherCompliances.md](./LegalandOtherCompliances.md) for full
> compliance posture.

# Video Intelligence Platform

A fullstack web application for video upload, playback, metadata extraction, clip management, and **AI-powered activity detection** using pose estimation.

A personal project exploring real-time video activity detection with MediaPipe Pose and a BiLSTM temporal classifier. It demonstrates end-to-end fullstack architecture (FastAPI + React + ML inference), privacy-by-design choices, and a candid compliance self-assessment.

## Tech Stack
- **Backend:** Python 3.11, FastAPI, SQLite, SQLAlchemy, OpenCV, ffmpeg, MediaPipe (Tasks API), TensorFlow/Keras
- **Frontend:** React 19, TypeScript, Vite 8, TailwindCSS 4, Video.js, MediaPipe Tasks Vision (WASM)
- **ML Pipeline:** MediaPipe Pose Estimation → 231-dim feature vector → BiLSTM activity classifier → scipy peak detection
- **DevOps:** Docker, Docker Compose

## Quick Start (Docker — recommended)

The fastest way to run the project. No Python, Node.js, or ffmpeg installation needed.

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop)

### Run
```bash
git clone https://github.com/mustafa-kaan-taplamacioglu/video-intelligence-platform.git
cd video-intelligence-platform
docker compose up --build
```

That's it. Open http://localhost:5173 in your browser.

**First-run experience:** On the first startup the backend auto-seeds the **7 sample videos** in `backend/demo_videos/` into the database so the Videos tab and Clip Library are populated immediately — no drag-and-drop required to start using the app. The seed runs only when the database is empty, so subsequent restarts do not duplicate data. These sample clips are third-party content and are **not** covered by this project's MIT license — see [DISCLAIMER.md](./DISCLAIMER.md) and [NOTICE](./NOTICE).

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs (Swagger):** http://localhost:8000/docs

To stop: `Ctrl+C` then `docker compose down`

---

## Manual Setup (alternative)

If you prefer running without Docker.

### Prerequisites
- Python 3.11+ ([download](https://www.python.org/downloads/))
- Node.js 20.19+ or 22.12+ ([download](https://nodejs.org/)) — required by Vite 8
- ffmpeg ([install guide](https://ffmpeg.org/download.html))
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: Download from ffmpeg.org and add to PATH

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```
Backend runs at http://localhost:8000

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at http://localhost:5173

---

## Features

### Core
- **Video upload:** Drag & drop MP4 files (max 500MB)
- **Video playback:** In-browser player with play/pause, seek, volume controls
- **Metadata display:** Duration, frame count, resolution, FPS (extracted by backend via OpenCV)
- **Clip generation:** Select start/end timestamps, backend generates and returns clip via ffmpeg
- **Clip library:** Save clips with custom names, re-download, delete — supports multiple source videos
- **First-class clips:** View clips with the same player + metadata dashboard as videos, create sub-clips from clips

### AI-Powered Detection
- **AI Video Analysis:** Upload a video → backend runs MediaPipe Pose Estimation + BiLSTM classifier → detects suspicious activity with timestamped results, confidence scores, and a probability curve
- **Detection Timeline:** Color-coded probability heatmap with peak markers
- **Detection Results:** Clickable table with "Jump to" and "Create Clip" actions
- **Live Stream Analysis:** Connect to webcam / RTSP camera / pre-uploaded demo video → real-time pose analysis → WebSocket-based alert feed
- **Browser-side pose for live webcam:** Pose detection runs client-side via `@mediapipe/tasks-vision` (WebAssembly + GPU). Raw webcam frames never leave the device.
- **Real-time BiLSTM on webcam (browser → backend):** Browser-extracted pose landmarks are streamed to a stateless `POST /api/livestream/classify-pose` endpoint at 8 fps, where the backend BiLSTM fires **real** Suspicious detections. The backend never touches the webcam — the classifier works on derived features only, preserving the privacy-by-design posture.
- **Live webcam clip save / download:** While a webcam session is active the browser uses `MediaRecorder` to capture the stream. Click **Download Recording** for a local file, or **Save to Library** to upload to the server as a Video + Clip (appears in the ClipLibrary immediately). Codec priority: MP4 (Chrome/Safari) → WebM (Firefox fallback).
- **Risk Assessment:** Automatic LOW/MEDIUM/HIGH risk level based on detection count
- **Desktop notifications:** Optional browser notifications fire when a live-stream detection arrives or when a video analysis completes — only when the tab is in the background, to avoid spam. Uses the native Web Notification API (no external services, no account, no configuration). The user grants permission once on first Connect / Analyze.

## Supported Formats
Only MP4 (video/mp4) files are accepted. Validated on both frontend and backend.

## API Documentation
Interactive API docs available at http://localhost:8000/docs when the backend is running.

## Architecture
```
React (Vite) ──HTTP/WS──> FastAPI ──> SQLite (metadata + detections)
                               │
                               ├──> OpenCV (metadata extraction)
                               ├──> ffmpeg (clip generation)
                               ├──> MediaPipe Tasks API (pose estimation)
                               ├──> TensorFlow / Keras BiLSTM (activity classification)
                               ├──> scipy.signal.find_peaks (post-processing)
                               └──> filesystem (video storage)
```
All video processing and AI inference happens on the backend, except for live webcam pose detection which runs client-side in the browser via MediaPipe WASM. The frontend handles UI rendering, API calls, and the WebSocket alert feed.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for full architectural details, database schema, API contract, and component specifications.

## ML Pipeline — Two-Tier System

| Tier | Model | Input | Output |
|------|-------|-------|--------|
| **Tier 2** (best) | MediaPipe Pose + BiLSTM | 231-dim pose feature sequence (window=20 @ 8 fps = 2.5s) | Binary: Normal vs Suspicious |
| **Tier 1** (fallback) | MobileNetV2-035 | Raw frames 128x128 | Binary: Normal vs Suspicious |
| **Mock** (default) | None | Video duration | Fake realistic detections |

The system auto-selects: BiLSTM → MobileNet → Mock. **Pre-trained models are included** in `backend/ml/models/` — real detection works out of the box. The BiLSTM achieves 67.6% accuracy / 0.63 macro F1 on the binary task, MobileNet achieves 81% on the same. Both trained on the DCSASS dataset.

## Model Training (Optional)

```bash
cd backend/ml/training

# Tier 1 — MobileNet (faster to train, frame-level)
python train_mobilenet.py --dcsass_root /path/to/DCSASS --output_dir ../models

# Tier 2 — BiLSTM v5 (better accuracy, temporal, requires MediaPipe pose extraction)
python train_lstm_v5.py --dcsass_root /path/to/DCSASS --output_dir ../models

# Evaluate
python evaluate.py --test_video /path/to/test.mp4
```

Dataset: [DCSASS on Kaggle](https://www.kaggle.com/datasets/mateohervas/dcsass-dataset) (CC BY 4.0)

## Privacy & Compliance

This prototype is built with **privacy-by-design intent** and has been the subject of a **candid compliance self-assessment** — see [LegalandOtherCompliances.md](./LegalandOtherCompliances.md) for the full analysis, and [ComplianceSprintPlan.md](./ComplianceSprintPlan.md) for a sprint-level production-remediation plan.

### What the implementation actually does

- **Pose-only inference pipeline.** The AI classifier consumes only 33 MediaPipe pose landmarks (normalized coordinates, velocities, visibility scores). No facial recognition, no person re-identification, no face-geometry extraction.
- **Live webcam: browser-side processing.** Pose detection runs in the browser via `@mediapipe/tasks-vision` (WebAssembly, GPU where available). Raw webcam frames never leave the device.
- **Live RTSP: in-memory server processing.** Frames are read, analyzed, and discarded. No `cv2.VideoWriter` is invoked and no ring buffer is maintained. RTSP frames are not persisted to disk.
- **Uploaded videos are stored on disk.** The AI Analysis upload flow persists the source MP4 at `storage/uploads/{uuid}.mp4` so that it can be replayed, clipped, and re-analyzed. Uploaded videos and generated clips can be deleted from the Videos tab at any time.
- **Explicit consent gating.** Consent is required before any processing. The backend rejects unconsented live-stream start requests with HTTP 400. Consent is persisted on the `stream_sessions.consent_given` column.
- **No third-party data transmission.** All processing happens locally on the operator's server. No cloud dependency; no external vendor APIs invoked during inference.
- **On-premise capable.** Docker Compose enables fully local deployment. Data residency is implicitly controlled by the operator.

### What this prototype is NOT

This is a **privacy-aware engineering prototype**, not a production-compliant product. In its current state it is explicitly **not** compliant with the GDPR, CCPA/CPRA, KVKK, NY SHIELD Act, or Illinois BIPA. Known gaps include (non-exhaustive):

- No encryption at rest for the SQLite database or uploaded media files
- No TLS termination in the default development configuration
- No authentication, authorization, or role-based access control
- No audit logging of personal-data access
- No Data Subject Access Request (DSAR) workflow
- No automated retention policy or deletion schedule
- No Data Protection Impact Assessment (DPIA)

A full gap analysis, biometric-data classification analysis, industry privacy-commitment comparison, and remediation roadmap are provided in [LegalandOtherCompliances.md](./LegalandOtherCompliances.md). The corresponding sprint-level execution plan is in [ComplianceSprintPlan.md](./ComplianceSprintPlan.md).

## License
Source code is released under the MIT License — see [LICENSE](./LICENSE).

The MIT License covers only the code authored in this repository. Third-party
model weights (MediaPipe, MobileNetV2), the DCSASS training dataset, and the
sample clips in `backend/demo_videos/` carry their own terms — see
[NOTICE](./NOTICE) for full attribution and [DISCLAIMER.md](./DISCLAIMER.md)
for data provenance.
