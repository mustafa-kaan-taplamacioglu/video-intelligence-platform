# Architecture

A technical reference for the **Video Intelligence Platform** prototype. Covers tech stack rationale, system architecture, database schema, API contract, frontend component specifications, and the ML pipeline.

This is the canonical design document for the project. For runtime instructions see [README.md](./README.md). For compliance posture see [LegalandOtherCompliances.md](./LegalandOtherCompliances.md).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Tech Stack and Rationale](#2-tech-stack-and-rationale)
3. [Architecture Diagram](#3-architecture-diagram)
4. [File Structure](#4-file-structure)
5. [Database Schema](#5-database-schema)
6. [API Contract](#6-api-contract)
7. [Frontend Components](#7-frontend-components)
8. [ML Pipeline](#8-ml-pipeline)
9. [Live Stream Architecture](#9-live-stream-architecture)
10. [Critical Implementation Notes](#10-critical-implementation-notes)
11. [Tier Selection and Fallback](#11-tier-selection-and-fallback)
12. [Docker Deployment](#12-docker-deployment)

---

## 1. Overview

The Video Intelligence Platform is a fullstack web application that combines:

- **Video CRUD**: upload, playback, metadata extraction, server-side clipping
- **Clip library**: persistent named clips with re-download and delete
- **AI activity detection**: MediaPipe Pose Estimation feeding a BiLSTM temporal classifier
- **Live stream analysis**: webcam (browser-side pose), RTSP cameras (server in-memory), and demo mode (uploaded video)
- **Real-time alerting**: WebSocket-based event stream from backend to frontend

All video processing and ML inference happens on the backend, except for **live webcam pose detection** which runs entirely in the user's browser via MediaPipe WebAssembly. This is a deliberate privacy-by-design choice — raw webcam frames never leave the device.

---

## 2. Tech Stack and Rationale

### Backend
| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.11 | Mature ML ecosystem; first-class FastAPI / TensorFlow / MediaPipe support |
| Web framework | FastAPI 0.115 | Async I/O, automatic OpenAPI docs, Pydantic validation, WebSocket support |
| ORM | SQLAlchemy 2.0 (sync) | Industry standard; async overhead unjustified at this scale |
| Database | SQLite | Zero-config, file-based, swappable to Postgres later via SQLAlchemy dialect |
| Video processing | OpenCV (`opencv-python-headless`) | Industry standard for frame extraction and metadata |
| Video clipping | `ffmpeg-python` | Stream-copy mode (`-c copy`) gives lossless, fast clip extraction |
| Pose extraction | MediaPipe Tasks API 0.10+ | CPU real-time, 33-keypoint BlazePose GHUM model, privacy-preserving |
| ML framework | TensorFlow 2.16 / Keras | BiLSTM temporal classifier; portable saved model format |
| WebSocket | FastAPI built-in | No separate broker needed for single-instance deployment |

### Frontend
| Component | Choice | Rationale |
|---|---|---|
| Library | React 19 | Latest stable; concurrent rendering improvements |
| Language | TypeScript 6 | Type safety across API contract |
| Build tool | Vite 8 | Fast HMR, native ESM, integrated dev proxy |
| Styling | Tailwind CSS 4 | Utility-first, no CSS file proliferation |
| Routing | React Router 7 | Industry standard for SPA navigation |
| Video player | Video.js 8 | Mature, customizable, supports HTTP Range requests |
| HTTP client | Axios | Better error semantics than fetch; upload progress events |
| Pose (browser) | `@mediapipe/tasks-vision` 0.10 | WASM + GPU pose detection client-side |

### DevOps
| Component | Choice | Rationale |
|---|---|---|
| Container runtime | Docker | Eliminates "works on my machine" for ffmpeg/system deps |
| Orchestration | Docker Compose | Single-command local stack |
| Storage persistence | Bind mount (`./backend/storage`) | Data survives container rebuilds; usable from both host and container |

### Privacy-relevant choices
| Decision | Why |
|---|---|
| Pose-only inference (no raw pixels into the classifier) | Reduces personal-data footprint; pose landmarks are not face geometry |
| Browser-side webcam pose | Raw webcam frames never reach the server |
| Live stream frames in-memory only | No `cv2.VideoWriter`, no ring buffer; RTSP frames are read-process-discard |
| Consent gating at API boundary | Backend rejects unconsented sessions with HTTP 400 |
| On-premise capable Docker | No cloud dependency; data residency under operator control |

---

## 3. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Frontend                               │
│                React 19 + TypeScript + Vite 8                   │
│                                                                 │
│  Pages:  Videos │ Clip Library │ AI Analysis │ Live Stream      │
│                                                                 │
│  Webcam pose: MediaPipe Tasks Vision (WASM/GPU, client-side)    │
└─────┬──────────────────────────────────────────────────┬────────┘
      │ REST API (JSON)                  WebSocket (real-time)
      │                                                  │
┌─────▼──────────────────────────────────────────────────▼────────┐
│                          Backend                                │
│                  Python 3.11 + FastAPI + Uvicorn                │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ video CRUD   │  │ clip CRUD    │  │ detection / stream   │   │
│  │  /api/videos │  │  /api/clips  │  │  /api/detection,     │   │
│  │              │  │              │  │  /api/livestream     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                  │                     │              │
│  ┌──────▼─────────────────▼──────┐  ┌───────────▼───────────┐   │
│  │ video_processor.py            │  │ activity_classifier.py│   │
│  │  - OpenCV (metadata)          │  │  - tier selection     │   │
│  │  - ffmpeg-python (clipping)   │  │  - peak detection     │   │
│  └────────────────────────────────┘  └───────────┬───────────┘   │
│                                                  │              │
│                                       ┌──────────▼───────────┐  │
│                                       │ pose_extractor.py    │  │
│                                       │  - MediaPipe Tasks   │  │
│                                       │  - feature engineer  │  │
│                                       └──────────┬───────────┘  │
│                                                  │              │
│                                       ┌──────────▼───────────┐  │
│                                       │ stream_processor.py  │  │
│                                       │  - threaded capture  │  │
│                                       │  - in-memory frames  │  │
│                                       └──────────────────────┘  │
└─────────┬─────────────────────────────────────────────┬─────────┘
          │                                             │
   ┌──────▼──────────┐                       ┌──────────▼─────────┐
   │  SQLite         │                       │  Filesystem        │
   │                 │                       │                    │
   │  videos         │                       │  storage/uploads/  │
   │  clips          │                       │  storage/clips/    │
   │  detection_     │                       │  ml/models/        │
   │    results      │                       │   - lstm.keras     │
   │  stream_        │                       │   - mobilenet.h5   │
   │    sessions     │                       │   - pose.task      │
   │  stream_        │                       │   - scaler.pkl     │
   │    detections   │                       │                    │
   └─────────────────┘                       └────────────────────┘
```

---

## 4. File Structure

```
video-intelligence-platform/
├── README.md
├── ARCHITECTURE.md                       ← this file
├── LegalandOtherCompliances.md
├── ComplianceSprintPlan.md
├── DISCLAIMER.md
├── LICENSE
├── docker-compose.yml
├── .gitignore
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       ← FastAPI app + lifespan + CORS
│   │   ├── config.py                     ← paths, limits, allowed formats
│   │   ├── database.py                   ← SQLAlchemy engine + session
│   │   ├── models.py                     ← ORM models
│   │   ├── schemas.py                    ← Pydantic request/response
│   │   ├── routers/
│   │   │   ├── videos.py                 ← /api/videos/*
│   │   │   ├── clips.py                  ← /api/clips/*
│   │   │   ├── detection.py              ← /api/detection/*
│   │   │   └── livestream.py             ← /api/livestream/* (REST + WebSocket)
│   │   └── services/
│   │       ├── video_processor.py        ← OpenCV metadata + ffmpeg clipping
│   │       ├── file_manager.py           ← upload save / delete
│   │       ├── pose_extractor.py         ← MediaPipe Tasks + feature engineering
│   │       ├── activity_classifier.py    ← tier selection + inference + peak detection
│   │       ├── stream_processor.py       ← live stream worker thread
│   │       └── demo_seeder.py            ← first-run seed from demo_videos/
│   ├── demo_videos/                              ← committed public-source sample videos
│   │   ├── multiple_people_normal.mp4            ← auto-seeded on fresh install
│   │   ├── onthewebsite.mp4
│   │   ├── single_person_normal.mp4
│   │   ├── single_person_shoplifting.mp4
│   │   ├── teamed_up_single_person(s)_shoplifting.mp4
│   │   ├── teamed_up_three_people_shoplifting.mp4
│   │   └── teamed_up_two_people_shoplifting.mp4
│   ├── ml/
│   │   ├── config.json                   ← inference config (window/stride/threshold)
│   │   ├── models/
│   │   │   ├── lstm_activity_classifier.keras   ← Tier 2 weights (~1 MB)
│   │   │   ├── mobilenet_shoplifting.h5         ← Tier 1 weights (~1.3 MB)
│   │   │   ├── pose_landmarker_lite.task        ← MediaPipe model (~5.5 MB)
│   │   │   ├── feature_scaler.pkl               ← StandardScaler fit
│   │   │   └── label_map.json
│   │   └── training/
│   │       ├── train_mobilenet.py
│   │       ├── train_lstm_v5.py                 ← latest LSTM training
│   │       └── evaluate.py
│   ├── storage/                                  ← runtime; bind-mounted; gitignored
│   │   ├── uploads/                              ← user uploads + demo seed (UUID-named)
│   │   ├── clips/
│   │   └── app.db
│   ├── requirements.txt
│   ├── .dockerignore
│   ├── Dockerfile
│   └── run.py
│
└── frontend/
    ├── public/
    │   ├── favicon.svg
    │   └── icons.svg
    ├── src/
    │   ├── main.tsx                       ← React entry
    │   ├── App.tsx                        ← Router + layout
    │   ├── api/
    │   │   └── client.ts                  ← REST + WebSocket wrappers
    │   ├── hooks/
    │   │   └── useBrowserPose.ts          ← MediaPipe WASM pose hook
    │   ├── utils/
    │   │   └── notifications.ts           ← Web Notification API helper
    │   ├── components/
    │   │   ├── Layout.tsx                 ← App shell + nav
    │   │   ├── VideoUploader.tsx
    │   │   ├── VideoPlayer.tsx            ← Video.js wrapper
    │   │   ├── VideoMetadata.tsx          ← metric cards
    │   │   ├── ClipCreator.tsx            ← timeline + start/end inputs
    │   │   ├── ClipSaveModal.tsx
    │   │   ├── ClipLibrary.tsx
    │   │   ├── DetectionPlayer.tsx        ← Video.js + canvas pose overlay
    │   │   ├── DetectionTimeline.tsx      ← color-coded probability heatmap
    │   │   ├── DetectionResults.tsx       ← detections table
    │   │   ├── LiveStreamView.tsx         ← webcam <video> + canvas overlay
    │   │   └── AlertFeed.tsx              ← real-time event list
    │   ├── pages/
    │   │   ├── HomePage.tsx
    │   │   ├── VideoPage.tsx
    │   │   ├── ClipPage.tsx
    │   │   ├── DetectionPage.tsx
    │   │   └── LiveStreamPage.tsx
    │   ├── types/
    │   │   └── index.ts
    │   └── index.css
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── .dockerignore
    └── Dockerfile
```

---

## 5. Database Schema

### `videos`
```sql
CREATE TABLE videos (
    id          TEXT PRIMARY KEY,          -- UUID v4
    filename    TEXT NOT NULL,
    filepath    TEXT NOT NULL,             -- relative to STORAGE_PATH
    filesize    INTEGER NOT NULL,          -- bytes
    duration    REAL NOT NULL,             -- seconds
    frame_count INTEGER NOT NULL,
    width       INTEGER NOT NULL,
    height      INTEGER NOT NULL,
    fps         REAL NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `clips`
```sql
CREATE TABLE clips (
    id              TEXT PRIMARY KEY,
    video_id        TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    source_clip_id  TEXT REFERENCES clips(id) ON DELETE SET NULL,  -- sub-clips
    name            TEXT NOT NULL,
    start_time      REAL NOT NULL,
    end_time        REAL NOT NULL,
    filepath        TEXT,                  -- relative to STORAGE_PATH
    filesize        INTEGER,
    duration        REAL,
    frame_count     INTEGER,
    width           INTEGER,
    height          INTEGER,
    fps             REAL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `detection_results`
```sql
CREATE TABLE detection_results (
    id          TEXT PRIMARY KEY,
    video_id    TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    start_time  REAL NOT NULL,
    end_time    REAL NOT NULL,
    label       TEXT NOT NULL,             -- "Suspicious" or "Normal"
    confidence  REAL NOT NULL,             -- 0.0 to 1.0
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `stream_sessions`
```sql
CREATE TABLE stream_sessions (
    id            TEXT PRIMARY KEY,
    source_url    TEXT NOT NULL,
    source_type   TEXT NOT NULL,           -- "webcam", "rtsp", "demo"
    consent_given INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'active',   -- "active", "stopped", "error"
    started_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    stopped_at    DATETIME
);
```

### `stream_detections`
```sql
CREATE TABLE stream_detections (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES stream_sessions(id) ON DELETE CASCADE,
    timestamp   DATETIME NOT NULL,
    frame_num   INTEGER NOT NULL,
    label       TEXT NOT NULL,
    confidence  REAL NOT NULL
);
```

---

## 6. API Contract

### Videos

#### `POST /api/videos/upload`
Upload an MP4 video file.
- **Request:** multipart/form-data, field `file` (max 500 MB)
- **Response 201:** `Video` object with extracted metadata
- **Errors:** 400 invalid format, 413 too large

#### `GET /api/videos`
List all uploaded videos.

#### `GET /api/videos/{id}`
Get a single video.

#### `GET /api/videos/{id}/stream`
Stream the file with HTTP Range support (required for browser seeking).

#### `POST /api/videos/{id}/clip`
Generate and download a clip via ffmpeg `-c copy`.
- **Body:** `{"start_time": float, "end_time": float}`
- **Response:** binary MP4 with `Content-Disposition: attachment`

### Clips

- `POST /api/clips` — save a clip record (name + range), generate file
- `GET /api/clips` — list all saved clips
- `GET /api/clips/{id}` — get single clip
- `GET /api/clips/{id}/stream` — stream with Range support
- `GET /api/clips/{id}/download` — file download
- `POST /api/clips/{id}/subclip` — create sub-clip from clip
- `DELETE /api/clips/{id}`

### Detection

- `POST /api/detection/analyze` — upload + analyze in one call; returns `AnalysisResponse` with detections, summary, probability curve
- `GET /api/detection/{video_id}/results` — fetch saved detection results
- `GET /api/detection/{video_id}/pose/{frame_number}` — get pose landmarks for a specific frame (overlay rendering)

### Live stream

- `POST /api/livestream/start` — start a session; requires `consent_given: true`, returns `session_id`
- `POST /api/livestream/{session_id}/stop` — stop session
- `GET /api/livestream/{session_id}` — session info
- `WS /api/livestream/{session_id}/ws` — WebSocket: detection events, heartbeats, end-of-stream
- `POST /api/livestream/classify-pose` — stateless BiLSTM classifier for browser-extracted pose windows. Body: `{ landmarks: number[][], session_id?: string }` where `landmarks` is `window_size × 132` floats. Returns `{ probability, label, mode, persisted }`. If `session_id` is provided and the window crosses the alert threshold, the detection is also persisted to `stream_detections`. Concurrency is serialized via a module-level `threading.Lock`.
- `POST /api/livestream/save-recording` — save a browser MediaRecorder blob as a `Video` + full-duration `Clip`. Multipart form: `file` (video/mp4 or video/webm blob) + `name` (string). Returns `{ video, clip }`. This is the only endpoint in the project that accepts non-MP4 video — the existing `/api/videos/upload` strictly enforces MP4 and is not changed. The clip appears in the ClipLibrary immediately after successful save.

### Schemas (TypeScript-equivalent)

```typescript
interface Video {
  id: string;
  filename: string;
  filesize: number;
  duration: number;
  frame_count: number;
  width: number;
  height: number;
  fps: number;
  created_at: string;
}

interface Clip {
  id: string;
  video_id: string;
  video_filename: string;
  name: string;
  start_time: number;
  end_time: number;
  source_clip_id?: string;
  // ... full metadata fields like Video
  created_at: string;
}

interface DetectionItem {
  start_time: number;
  end_time: number;
  label: string;
  confidence: number;
}

interface AnalysisResponse {
  video_id: string;
  duration: number;
  fps_analyzed: number;
  detections: DetectionItem[];
  summary: { total_detections: number; by_class: Record<string, number>; risk_level: string };
  probability_curve?: number[];
  curve_timestamps?: number[];
}

interface StreamDetectionEvent {
  type: 'detection' | 'heartbeat' | 'ended' | 'error';
  timestamp?: string;
  frame_number?: number;
  label?: string;
  confidence?: number;
  fps_processing?: number;
  frames_analyzed?: number;
}
```

---

## 7. Frontend Components

### Layout (`Layout.tsx`)
App shell. Top bar with logo + navigation tabs (Videos, Clip Library, AI Analysis, Live Stream). Footer.

### VideoUploader (`VideoUploader.tsx`)
Drag-and-drop zone with:
- MP4 validation (frontend + backend double-check)
- Upload progress bar
- Inline error display

### VideoPlayer (`VideoPlayer.tsx`)
Video.js wrapper exposing:
- Source URL prop
- `onTimeUpdate` callback for parent to track playback time
- Standard controls (play/pause, seek, volume, fullscreen)

### VideoMetadata (`VideoMetadata.tsx`)
6-card grid:
- Duration (`MM:SS.s`)
- Frames (locale-formatted)
- Resolution (`WxH`)
- FPS (`xx.xx fps`)
- File size (`MB`)
- Filename (truncated with title)

### ClipCreator (`ClipCreator.tsx`)
- Mini timeline bar with clip range overlay + current playhead marker
- Start / End inputs accepting `MM:SS` or raw seconds
- "Now" buttons that grab the current playback time from props
- "Download Clip" (calls `POST /api/videos/{id}/clip`) and "Save Clip" (opens save modal) buttons

### ClipSaveModal (`ClipSaveModal.tsx`)
Modal with name input + read-only source/start/end display + Save action.

### ClipLibrary (`ClipLibrary.tsx`)
Table of all saved clips with View / Download / Delete actions. `refreshKey` prop triggers re-fetch when a new clip is saved.

### DetectionPlayer (`DetectionPlayer.tsx`)
Video.js + a `<canvas>` overlay (`absolute inset-0 pointer-events-none`). On every animation frame the canvas is cleared and the latest pose landmarks are redrawn (skeleton + bounding box + label). Pose data is fetched from `/api/detection/{id}/pose/{frame}` on a throttled cadence (~2 fps) and cached.

### DetectionTimeline (`DetectionTimeline.tsx`)
Color-coded probability heatmap: each window's probability mapped to a hue (green=normal, amber=uncertain, red=suspicious). Peak detections marked as vertical lines + dots above the bar. Click to seek.

### DetectionResults (`DetectionResults.tsx`)
Table of detection peaks with timestamp range, label, confidence, "Jump to" and "Create Clip" buttons.

### LiveStreamView (`LiveStreamView.tsx`)
For webcam sources:
- `<video>` element with `getUserMedia` stream
- `<canvas>` overlay on top
- `useBrowserPose(videoRef, active, onLandmarks)` hook returns pose landmarks computed in the browser
- Same drawing logic as DetectionPlayer (skeleton + bounding box + label)
- Consent gate before activation
- Loading overlay while WASM model downloads from CDN
- **`onLandmarks?: (raw: number[]) => void`** — forwarded as-is to `useBrowserPose`; consumed by the parent to stream pose windows to the backend BiLSTM classifier
- **`onStreamReady?: (stream: MediaStream | null) => void`** — fires when the webcam MediaStream is acquired (with the stream) or released (with `null`). Parent uses this to construct a `MediaRecorder` for clip save/download without having to re-request `getUserMedia`

**Lifecycle decoupling:** The `active` prop is intentionally tied to the parent's `sessionId !== null` state, **not** to the WebSocket connection state. The WebSocket can drop for many reasons (backend `cv2.VideoCapture` failing in Docker on macOS where the container cannot access the host webcam, idle timeouts, network blips, or the backend processor finishing), but the user's webcam and browser-side pose overlay must keep working until they explicitly click Stop. Coupling camera lifecycle to WebSocket state would cause the camera to die — and the browser to release the device, turning off the LED — every time the WS dropped, which is a poor user experience and was a real bug at one point.

### AlertFeed (`AlertFeed.tsx`)
WebSocket-driven scrolling list of detection events. Shows label, confidence, timestamp, optional thumbnail.

### useBrowserPose hook (`hooks/useBrowserPose.ts`)
Wraps `@mediapipe/tasks-vision`:
- Loads WASM from CDN once (`FilesetResolver.forVisionTasks`)
- Creates `PoseLandmarker` with `RunningMode.VIDEO`, GPU delegate, `numPoses: 1`
- `requestAnimationFrame` loop throttled to ~15 fps for a smooth canvas overlay
- Calls `landmarker.detectForVideo(videoEl, performance.now())`
- Returns `{ landmarks, loading, error }` for the canvas drawing consumers
- **Optional `onLandmarks?: (raw: number[]) => void` callback** — fires at a separate 125ms (8 fps) timestamp-based throttle with the flattened 132-float raw landmark vector `[x, y, z, visibility, ...]`. This is consumed by `LiveStreamPage` to stream windows to the backend `POST /classify-pose` endpoint. The 8 fps rate matches the BiLSTM training sample rate exactly so velocity features are computed with the same `dt` as during training. Missing `visibility` is defaulted to `1.0` to guard against silent undefined propagation.
- Callback identity is stored in a ref and updated in a separate effect, so parent re-renders do not cause the MediaPipe landmarker to re-initialize
- Cleanup on unmount

### notifications utility (`utils/notifications.ts`)
Thin wrapper around the Web Notification API (NOT Web Push). Deliberately avoids service workers, VAPID keys, and HTTPS requirements so it works on `http://localhost` and requires no external service or account.

Exports:
- `getNotificationSupport(): 'unsupported' | 'default' | 'granted' | 'denied'` — current permission state
- `requestNotificationPermission(): Promise<NotificationSupport>` — safe to call multiple times; browsers remember the decision
- `notify({ title, body, icon, tag, skipIfVisible, onClick })` — shows a notification, returns `null` silently if unsupported, not granted, or if `skipIfVisible` is true and the tab is currently visible

Wired into two user-facing flows:
1. **Live Stream detection events** — `LiveStreamPage` requests permission on the user's Connect click, then calls `notify()` whenever a detection message arrives on the WebSocket. The `skipIfVisible` default prevents duplication with the AlertFeed UI when the user is actively watching.
2. **Analysis complete / failed** — `DetectionPage` requests permission on the Analyze click, then fires a notification when `analyzeVideo()` resolves (summary: detection count + risk level) or when it rejects (error message).

**Scope note:** This uses the *Web Notification API*, not the *Web Push API*. It only delivers notifications while the browser is running. True mobile push (APNs/FCM delivering to a phone while the browser is closed) is documented as a production remediation item in `ComplianceSprintPlan.md` Sprint 6.

---

## 8. ML Pipeline

### Why pose + temporal classifier (instead of YOLO or end-to-end transformer)

1. **Privacy-preserving by construction.** Only 33 skeleton keypoints are processed, not raw pixel data. No facial recognition, no person re-identification, no face geometry.
2. **Temporal sequences capture behaviour.** Suspicious activity is a *sequence* of actions (look around → reach → conceal → move away), not a single-frame event. A temporal model is well-suited.
3. **Lightweight for edge / CPU inference.** MediaPipe runs real-time on CPU with no GPU. The BiLSTM classifier is ~1 MB. Suitable for edge deployment (Jetson, Coral).
4. **Reproducible and auditable.** Pose features are interpretable; the model can be inspected, retrained, and explained more readily than a black-box CNN.

### Tier 2 (preferred) — MediaPipe Pose + BiLSTM

```
video → cv2.VideoCapture
       ↓
       extract every Nth frame (target_fps=8 → N = stream_fps / 8)
       ↓
       MediaPipe Tasks API (PoseLandmarker, RunningMode.VIDEO)
       ↓
       33 landmarks × (x, y, z, visibility) = 132 raw values per frame
       ↓
       feature engineering → 231-dim vector per frame:
         - 99 normalized positions (xyz, hip-centered, shoulder-scaled)
         - 99 velocities (frame-to-frame deltas)
         - 33 visibility scores
       ↓
       sliding window (size=20 @ 8 fps = 2.5 s, stride=10)
       ↓
       StandardScaler.transform (fit on training data only)
       ↓
       BiLSTM(units=32, return_sequences) → BiLSTM(units=16)
       → Dense(32) → Dropout(0.3) → Dense(1, sigmoid)
       ↓
       per-window probability ∈ [0, 1]
       ↓
       full-video probability curve
       ↓
       scipy.signal.find_peaks (adaptive threshold = mean + 0.5σ, min distance ~3 s)
       ↓
       Detection objects with start, end, label, confidence
```

**Training**: Video-level GroupShuffleSplit (70/15/15) on the DCSASS dataset. Sub-clips from the same parent video are kept in the same split (no leakage). StandardScaler fit on train only. Augmentation (Gaussian noise + time warp) on train only. Optuna hyperparameter tuning (15 trials, TPE sampler) optimising macro F1 on validation. Final BiLSTM v5 metrics on the test set: **accuracy 67.6%, macro F1 0.63, ROC-AUC 0.59**.

**Inference config** (`backend/ml/config.json`):
```json
{
  "window_size": 20,
  "stride": 10,
  "num_classes": 2,
  "labels": ["Normal", "Suspicious"],
  "confidence_threshold": 0.5,
  "features_per_frame": 231,
  "target_fps": 8,
  "best_architecture": "bilstm"
}
```

### Tier 1 (fallback) — MobileNetV2 frame-level classifier

If the BiLSTM weights are missing, the classifier falls back to MobileNetV2-035-128:

```
video → extract frames at 2 fps → resize to 128x128 → normalize → MobileNetV2 → sigmoid
```

Test accuracy on the binary task: ~81%. Faster but loses temporal context.

### Tier 0 (mock) — fallback when no models present

Returns hard-coded "fake realistic" detections so the entire UI pipeline can be developed without trained models. Used during initial development.

### Feature engineering details

```python
# Per frame, given 33 landmarks of (x, y, z, visibility):
hip_center = (landmarks[23, :3] + landmarks[24, :3]) / 2     # left_hip + right_hip / 2
shoulder_dist = norm(landmarks[11, :3] - landmarks[12, :3])  # left_shoulder - right_shoulder

normalized = (frame[:, :3] - hip_center) / shoulder_dist     # 33 × 3 = 99 values
velocity = frame[:, :3] - prev_frame[:, :3]                  # 33 × 3 = 99 values
visibility = frame[:, 3]                                     # 33 values

feature_vector = concat([normalized.flatten(), velocity.flatten(), visibility])  # 231-dim
```

The hip-centered, shoulder-scaled normalization makes the features invariant to camera distance and absolute position. Velocities capture motion. Visibility lets the model learn to ignore occluded joints.

### Post-processing: peak detection

Instead of merging overlapping windows (which produced false-positive monoblocks), the post-processing uses `scipy.signal.find_peaks` on a smoothed probability curve:

```python
smoothed = rolling_mean(curve, window=3)
height = max(0.7, mean + 0.5 * std)
distance = max(1, int(windows_per_second * 3.0))  # min 3 s between peaks
peaks, _ = find_peaks(smoothed, height=height, distance=distance, prominence=0.05)
```

This produces well-localised detection events instead of overlapping blob regions.

---

## 9. Live Stream Architecture

Three source types, each with a different data path:

### Webcam (browser-side pose → backend BiLSTM classifier)

```
browser getUserMedia() → <video> element → (fan-out to three consumers)
       │
       ├──► useBrowserPose (requestAnimationFrame @ ~15 fps)
       │         ↓
       │         MediaPipe Tasks Vision (WASM, GPU delegate where available)
       │         ↓
       │         33 NormalizedLandmark × (x, y, z, visibility)
       │         ↓
       │         ├─► setLandmarks → canvas overlay (skeleton + bbox + label)
       │         │
       │         └─► 125ms throttle (8 fps, matches training) →
       │              flatten to 132 floats with `lm.visibility ?? 1.0` guard
       │              ↓
       │              onLandmarks callback → LiveStreamPage.handleLandmarks
       │              ↓
       │              sliding buffer (window_size=20, stride=10, cap window+stride)
       │              ↓
       │              when buffer.length >= 20:
       │                POST /api/livestream/classify-pose
       │                body: { landmarks: [[132 floats] × 20], session_id }
       │                ↓
       │                Backend (FastAPI sync, ThreadPoolExecutor):
       │                  with threading.Lock: BiLSTM.predict()
       │                  if prob ≥ threshold and session_id:
       │                    insert StreamDetection row (best-effort)
       │                ↓
       │                response: { probability, label, mode, persisted }
       │              ↓
       │              if Suspicious + cooldown passed:
       │                setLatestAlert → AlertFeed + bbox red + notify()
       │
       ├──► onStreamReady callback → LiveStreamPage
       │         ↓
       │         new MediaRecorder(stream, { mimeType: pickMimeType() })
       │         (priority: video/mp4 → video/webm/vp9 → video/webm/vp8)
       │         ↓
       │         .start(1000)  [1-second timeslice chunks]
       │         ↓
       │         ondataavailable → chunks.push(Blob)
       │         ↓
       │         User clicks Save to Library:
       │           recorder.stop() → await 'stop' event → combined Blob
       │           POST /api/livestream/save-recording  (multipart: file + name)
       │           → Backend creates Video + full-duration Clip records
       │           → ClipLibrary.refreshKey++ → new clip visible
       │           → recorder restarts for next save
       │         User clicks Download Recording:
       │           same stop+collect → URL.createObjectURL → <a download> → restart
       │
       └──► WebSocket (/api/livestream/{session_id}/ws) — legacy path
                 ↓
                 Receives heartbeat + "ended" events from the backend's
                 session-based processor. Mostly idle for webcam mode since
                 cv2.VideoCapture(0) fails in Docker on macOS, but the WS
                 still opens so the existing UI status indicators work.
```

**Key properties**:
- **Raw webcam frames never reach the server** via the classify path. Only derived pose features (132 floats/frame @ 8 fps ≈ 8 KB/s). This preserves the browser-side processing privacy story even under real-time BiLSTM classification.
- **MediaRecorder keeps raw frames in browser memory only** until the user clicks Save to Library. At that explicit action, the blob is uploaded and persisted as a Video + Clip on the server. This is the **only path** by which raw webcam frames become server-side persistent data, and it requires explicit user action.
- **Backend never calls `cv2.VideoCapture(0)` for webcam classification** — the `/classify-pose` endpoint is fully stateless and operates on browser-derived features. This completely bypasses the Docker-on-macOS webcam access limitation.
- **Multi-session safety**: A module-level `threading.Lock` in `routers/livestream.py` serializes BiLSTM `predict()` calls across concurrent browser sessions, preventing race conditions inside the shared Keras model instance.

### RTSP (server-side, in-memory)

```
backend stream_processor.py (worker thread)
       ↓
       cv2.VideoCapture(rtsp_url)
       ↓
       loop: read frame → MediaPipe pose → feature engineer → buffer
       ↓
       when buffer reaches window_size: BiLSTM predict → cooldown → emit detection
       ↓
       discard frame (no cv2.VideoWriter, no ring buffer)
```

**RTSP frames are processed in memory and discarded.** Only the derived pose vector and the resulting detection events are persisted.

### Demo (uses an uploaded video)

Same path as RTSP, but the source is the first MP4 in `storage/uploads/`. This is for demonstrations when no webcam or RTSP camera is available.

### WebSocket protocol

The backend's `/api/livestream/{session_id}/ws` endpoint sends JSON messages:

```json
{ "type": "detection", "timestamp": "ISO8601", "frame_number": 1523, "label": "Suspicious", "confidence": 0.91 }
```
```json
{ "type": "heartbeat", "fps_processing": 4.2, "frames_analyzed": 1523, "active_detections": 0 }
```
```json
{ "type": "ended", "message": "Stream processing ended" }
```

The frontend's `AlertFeed` component subscribes and updates the UI.

### Vite dev proxy (Docker)

`vite.config.ts` proxies `/api` to `http://backend:8000` and explicitly enables `ws: true` so the WebSocket upgrade is forwarded. Without `ws: true`, HTTP requests work but WebSocket upgrade does not, breaking live stream functionality in Docker.

---

## 10. Critical Implementation Notes

### HTTP Range requests for video seeking
Browser video players require Range request support to seek without re-downloading the whole file. FastAPI's `FileResponse` handles this automatically, but only for static files. The video and clip stream endpoints use `FileResponse` for this reason.

### ffmpeg clip extraction (stream copy)
```python
ffmpeg.input(input_path, ss=start, to=end) \
    .output(output_path, c="copy", movflags="faststart") \
    .overwrite_output() \
    .run(quiet=True)
```
- `c="copy"` is stream copy: no re-encoding, near-instant, lossless. Requires aligned keyframes; if the requested start is between keyframes, ffmpeg seeks to the nearest preceding keyframe.
- `movflags="faststart"` moves the moov atom to the front of the file so the clip can be streamed before the full download completes.

### MediaPipe Tasks API (not the deprecated `solutions.pose`)
MediaPipe 0.10.33+ removed `mp.solutions.pose`. The current code uses the Tasks API:
```python
from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode
options = PoseLandmarkerOptions(
    base_options=BaseOptions(model_asset_path="ml/models/pose_landmarker_lite.task"),
    running_mode=RunningMode.VIDEO,
    num_poses=1,
)
with PoseLandmarker.create_from_options(options) as landmarker:
    result = landmarker.detect_for_video(mp_image, timestamp_ms)
```
The Tasks API requires an explicit model file (`pose_landmarker_lite.task`) rather than auto-downloading one.

### Live stream is run in a worker thread, not async
`stream_processor.py` spawns a `threading.Thread` for the OpenCV capture loop. This is intentional: OpenCV's `cv2.VideoCapture.read()` is synchronous and blocks until a frame is available. Wrapping it in async `run_in_executor` adds overhead with no real benefit. The thread pushes events into a thread-safe deque consumed by the WebSocket coroutine.

### File upload size limit
Configured in `backend/app/config.py`:
```python
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB
ALLOWED_EXTENSIONS = {".mp4"}
ALLOWED_MIME_TYPES = {"video/mp4"}
```
Validated on both ends: frontend pre-flight + backend final.

### Browser pose model loading
`@mediapipe/tasks-vision` downloads its WASM and the pose model from a CDN on first use. The first activation can take 1-3 seconds depending on the connection. Subsequent activations use the browser cache. The hook exposes a `loading` boolean for UX.

### Storage path resolution
`backend/app/config.py` uses `STORAGE_PATH` env var (defaulting to `./storage`) and exposes `resolve_path(relative)` which joins safely. All filepaths in the database are stored relative to `STORAGE_PATH`. This makes the bind mount portable: mount any host directory and the system finds its files.

### First-run demo data seeding
`backend/app/services/demo_seeder.py` runs on every application startup via the FastAPI lifespan hook. Its behavior is idempotent:

- If the `videos` table is **non-empty**, it skips entirely (nothing to seed).
- If the `backend/demo_videos/` directory is missing or empty, it skips.
- Otherwise, for each `*.mp4` in `backend/demo_videos/`, it:
  1. Copies the file to `storage/uploads/{video_uuid}.mp4` and creates a `Video` record (filename = original demo video name, e.g. `multiple_people_normal.mp4`)
  2. Runs `video_processor.create_clip()` — ffmpeg stream-copy with `faststart` — to produce an independent `storage/clips/{clip_uuid}.mp4`
  3. Creates a full-duration `Clip` record pointing at the **separate** clip file (same pattern as the `POST /api/clips` endpoint)

The Clip gets its own file (not a reference to the Video's file) deliberately — this mirrors the production clip-creation flow and ensures `DELETE /api/clips/{id}` cleanly removes the clip's backing file without side-effecting the Video's file. Disk footprint is 2× the demo videos (~40 MB) but this is a trivial amount of static data.

This gives anyone cloning the repository an immediately-usable populated demo state — 7 sample videos spanning normal and suspicious scenarios — without requiring them to drag-and-drop their own files first. The sample clips are third-party content, not covered by this project's MIT license; see [DISCLAIMER.md](./DISCLAIMER.md). Per-file failures (corrupt MP4, OpenCV error, ffmpeg stream-copy failure) are logged and skipped so one bad file does not block the rest of the seed; partial files from a failed attempt are cleaned up.

Seeding happens **at runtime** (lifespan startup), not at Docker build time. This is intentional: the bind-mounted `backend/storage/` directory overlays the image's built-in storage, so the seed must fire after the mount is live to ensure the UUID-named copies land on the host filesystem where subsequent user uploads also live.

---

## 11. Tier Selection and Fallback

`backend/app/services/activity_classifier.py` initializes once at module load and tries each tier in priority order:

```python
class ActivityClassifier:
    def __init__(self):
        self.lstm_model = self._try_load("ml/models/lstm_activity_classifier.keras")
        self.mobilenet_model = self._try_load("ml/models/mobilenet_shoplifting.h5")

        if self.lstm_model:
            self.mode = "lstm"           # Tier 2 — preferred
        elif self.mobilenet_model:
            self.mode = "mobilenet"      # Tier 1 — fallback
        else:
            self.mode = "mock"           # Tier 0 — dev fallback

    def analyze_video(self, video_path):
        if self.mode == "lstm":
            return self._analyze_lstm(video_path)
        elif self.mode == "mobilenet":
            return self._analyze_mobilenet(video_path)
        return self._analyze_mock(video_path)
```

The startup log line announces which tier is active. Mock mode returns hard-coded fake detections so the UI pipeline always has something to render — useful for development before any model is trained.

---

## 12. Docker Deployment

### `docker-compose.yml`
```yaml
services:
  backend:
    build: { context: ./backend, dockerfile: Dockerfile }
    ports: ["8000:8000"]
    volumes: ["./backend/storage:/app/storage"]
    environment:
      - STORAGE_PATH=/app/storage

  frontend:
    build: { context: ./frontend, dockerfile: Dockerfile }
    ports: ["5173:5173"]
    depends_on: [backend]
    environment:
      - VITE_API_URL=http://backend:8000
```

### `backend/Dockerfile`
```dockerfile
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p storage/uploads storage/clips

EXPOSE 8000
CMD ["python", "run.py"]
```

Key choices:
- `python:3.11-slim` (~150 MB base) keeps the image small.
- `ffmpeg` is a system binary, installed via apt — not a Python package.
- `libgl1` and `libglib2.0-0` are required by OpenCV and MediaPipe at runtime.
- The bind mount in compose makes `storage/` writable from both the host and the container.

### `frontend/Dockerfile`
```dockerfile
FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

Key choices:
- `node:22-alpine` satisfies Vite 8's Node 20.19+ / 22.12+ requirement safely (`node:20-alpine` may resolve to older 20.x tags).
- `npm ci` for deterministic, reproducible builds — requires `package-lock.json` (which is committed).
- `--host 0.0.0.0` makes Vite accessible from outside the container.
- Dev mode (with HMR) is used in development; production would use `npm run build` and serve via nginx.

### Vite proxy config (`frontend/vite.config.ts`)
```typescript
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        ws: true, // required for /api/livestream/{id}/ws upgrade
      },
    },
  },
});
```

`process.env.VITE_API_URL` resolves to `http://backend:8000` inside the Docker network, and `http://localhost:8000` for local manual development.

### Image sizes
- `backend`: ~3.6 GB (TensorFlow + MediaPipe + OpenCV + ffmpeg dominate)
- `frontend`: ~700 MB (Node 22 + node_modules)

These sizes are typical for an ML-bearing stack. A first build takes 5-10 minutes; subsequent builds use cached layers and complete in under a minute.

---

**End of Document**
