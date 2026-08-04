"""Live stream analysis endpoints — start/stop sessions + WebSocket for real-time detections.

Also exposes two stateless endpoints used by browser-side webcam live streaming:
  - POST /classify-pose   — run BiLSTM on a browser-extracted pose window
  - POST /save-recording  — save a browser MediaRecorder blob as Video + Clip
"""

import asyncio
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session

from app.config import MAX_UPLOAD_SIZE, resolve_path
from app.database import get_db
from app.models import Clip, StreamDetection, StreamSession, Video
from app.schemas import (
    LiveRecordingSaveResponse,
    PoseClassificationResponse,
    PoseWindowRequest,
    StreamSessionResponse,
    StreamStartRequest,
)
from app.services.activity_classifier import get_classifier
from app.services.pose_extractor import engineer_features
from app.services.stream_processor import get_session as get_stream_processor
from app.services.stream_processor import start_session, stop_session
from app.services.video_processor import extract_metadata

router = APIRouter(prefix="/api/livestream", tags=["livestream"])

# Module-level lock to serialize BiLSTM predict() across concurrent sessions.
# TensorFlow 2.x is mostly thread-safe for inference but edge cases exist when
# multiple requests hit the same model instance simultaneously. Since the cost
# of a single predict() is ~20-50ms and alerts fire every ~1.3s per session,
# serialization has negligible user-visible latency impact even with a few
# concurrent webcams.
_classify_lock = threading.Lock()


@router.post("/start", response_model=StreamSessionResponse)
def start_stream(req: StreamStartRequest, db: Session = Depends(get_db)):
    """Start processing a live stream. Requires explicit privacy consent."""
    if not req.consent_given:
        raise HTTPException(
            status_code=400,
            detail="Privacy consent is required before processing video. "
                   "Please acknowledge that only pose keypoints are analyzed and no PII is stored.",
        )

    if req.source_type not in ("webcam", "rtsp", "demo"):
        raise HTTPException(status_code=400, detail="Unsupported source type. Use: webcam, rtsp, or demo")

    session_id = str(uuid.uuid4())

    session = StreamSession(
        id=session_id,
        source_url=req.source,
        source_type=req.source_type,
        status="active",
        consent_given=1,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    try:
        start_session(session_id, req.source, req.source_type)
    except Exception as e:
        session.status = "error"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start stream: {str(e)}")

    return StreamSessionResponse(
        id=session.id,
        source_url=session.source_url,
        source_type=session.source_type,
        status=session.status,
        consent_given=True,
        started_at=session.started_at,
    )


@router.post("/{session_id}/stop")
def stop_stream(session_id: str, db: Session = Depends(get_db)):
    """Stop a live stream processing session."""
    session = db.query(StreamSession).filter(StreamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    stop_session(session_id)
    session.status = "stopped"
    session.stopped_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "stopped", "session_id": session_id}


@router.get("/{session_id}", response_model=StreamSessionResponse)
def get_stream_session(session_id: str, db: Session = Depends(get_db)):
    """Get stream session info."""
    session = db.query(StreamSession).filter(StreamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return StreamSessionResponse(
        id=session.id,
        source_url=session.source_url,
        source_type=session.source_type,
        status=session.status,
        started_at=session.started_at,
    )


@router.post("/save-recording", response_model=LiveRecordingSaveResponse)
async def save_live_recording(
    name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Save a browser MediaRecorder blob as a Video + full-duration Clip.

    The browser records its webcam stream in-memory via MediaRecorder. When
    the user clicks "Save to Library", the blob is uploaded here with a
    user-provided name. We persist the file to storage/uploads/, extract
    metadata via OpenCV (supports both MP4 and WebM through the ffmpeg
    backend), create a Video row, and auto-create a Clip row spanning the
    full duration so it shows up in the ClipLibrary immediately.

    Accepted formats: video/mp4 (Chrome/Safari MediaRecorder) and video/webm
    (Firefox and fallback). This is the only endpoint in the project that
    accepts non-MP4 video — the existing /api/videos/upload strictly enforces
    MP4 and is not changed.
    """
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Recording too large (max {MAX_UPLOAD_SIZE // 1024 // 1024} MB)",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Empty recording blob")

    mime = (file.content_type or "").lower()
    if "mp4" in mime:
        ext = "mp4"
    elif "webm" in mime:
        ext = "webm"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported recording format: {mime}. Expected video/mp4 or video/webm",
        )

    clean_name = name.strip() or "Live recording"
    video_id = str(uuid.uuid4())
    relative_path = f"uploads/{video_id}.{ext}"
    abs_path = Path(resolve_path(relative_path))
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    with open(abs_path, "wb") as f:
        f.write(content)

    # Extract metadata via OpenCV (ffmpeg backend reads WebM on Linux container)
    try:
        meta = extract_metadata(str(abs_path))
    except Exception as e:
        # Clean up the partial file so we don't leak disk space
        try:
            os.remove(abs_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=400, detail=f"Failed to process recording: {e}"
        )

    # Create Video record
    video = Video(
        id=video_id,
        filename=f"{clean_name}.{ext}",
        filepath=relative_path,
        filesize=len(content),
        **meta,
    )
    db.add(video)

    # Create Clip record spanning full duration (same filepath — no extra disk)
    clip_id = str(uuid.uuid4())
    clip = Clip(
        id=clip_id,
        video_id=video_id,
        name=clean_name,
        start_time=0.0,
        end_time=meta["duration"],
        filepath=relative_path,
        filesize=len(content),
        **meta,
    )
    db.add(clip)
    db.commit()
    db.refresh(video)
    db.refresh(clip)

    return LiveRecordingSaveResponse(
        video={
            "id": video.id,
            "filename": video.filename,
            "filesize": video.filesize,
            "duration": video.duration,
            "frame_count": video.frame_count,
            "width": video.width,
            "height": video.height,
            "fps": video.fps,
            "created_at": video.created_at.isoformat() if video.created_at else None,
        },
        clip={
            "id": clip.id,
            "video_id": clip.video_id,
            "video_filename": video.filename,
            "name": clip.name,
            "start_time": clip.start_time,
            "end_time": clip.end_time,
            "created_at": clip.created_at.isoformat() if clip.created_at else None,
        },
    )


@router.post("/classify-pose", response_model=PoseClassificationResponse)
def classify_pose_window(req: PoseWindowRequest, db: Session = Depends(get_db)):
    """Stateless BiLSTM classifier for browser-extracted pose windows.

    Used by the webcam live-stream flow where the backend does not access
    the camera. The browser computes 33 MediaPipe landmarks per frame, flattens
    them to (x, y, z, visibility) = 132 floats, buffers a window of
    `classifier.window_size` frames, and POSTs it here. We run feature
    engineering → scaler → BiLSTM → return probability + label.

    If `session_id` is provided and the classification exceeds the alert
    threshold, the detection is persisted to the stream_detections table.
    Writes are best-effort: a DB failure does not fail the response.

    Concurrency: a module-level threading.Lock serializes predict() across
    concurrent sessions since TF 2.x inference isn't guaranteed thread-safe
    at the model instance level.
    """
    classifier = get_classifier()
    if classifier.mode != "lstm" or classifier.lstm_model is None:
        return PoseClassificationResponse(
            probability=0.0, label="Normal", mode=classifier.mode
        )

    raw = np.array(req.landmarks, dtype=np.float32)
    if raw.ndim != 2 or raw.shape[1] != 132:
        raise HTTPException(
            status_code=400,
            detail=f"landmarks must be shape (N, 132); got {list(raw.shape)}",
        )
    if raw.shape[0] != classifier.window_size:
        raise HTTPException(
            status_code=400,
            detail=(
                f"window must contain exactly {classifier.window_size} frames; "
                f"got {raw.shape[0]}"
            ),
        )

    features = engineer_features(raw)
    if classifier.scaler is not None:
        features = classifier.scaler.transform(features)
    window_input = np.expand_dims(features, axis=0).astype(np.float32)

    with _classify_lock:
        try:
            prediction = classifier.lstm_model.predict(window_input, verbose=0)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"BiLSTM inference failed: {e}"
            )

    # Handle both binary sigmoid (shape (1,1)) and multi-class softmax outputs
    if prediction.ndim == 2 and prediction.shape[1] == 1:
        prob = float(prediction[0, 0])
        label = (
            classifier.labels[1]
            if prob >= classifier.threshold
            else classifier.labels[0]
        )
    else:
        prob = float(1.0 - prediction[0, 0])
        class_idx = int(np.argmax(prediction[0]))
        label = classifier.labels[class_idx]

    # Optional DB persistence (only if alert crossed threshold)
    persisted = False
    if (
        req.session_id
        and len(classifier.labels) >= 2
        and label == classifier.labels[1]
        and prob >= classifier.threshold
    ):
        try:
            session_row = (
                db.query(StreamSession)
                .filter(StreamSession.id == req.session_id)
                .first()
            )
            if session_row is not None:
                db.add(
                    StreamDetection(
                        id=str(uuid.uuid4()),
                        session_id=req.session_id,
                        timestamp=datetime.now(timezone.utc),
                        frame_num=0,  # not applicable for browser-sourced windows
                        label=label,
                        confidence=prob,
                    )
                )
                db.commit()
                persisted = True
        except Exception:
            # Best-effort: DB failure must not fail the classification response
            db.rollback()

    return PoseClassificationResponse(
        probability=prob, label=label, mode="lstm", persisted=persisted
    )


@router.websocket("/{session_id}/ws")
async def stream_ws(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time detection results."""
    await websocket.accept()

    processor = get_stream_processor(session_id)
    if not processor:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return

    heartbeat_interval = 0
    try:
        while processor.running:
            # Send any new detections
            new_detections = processor.get_new_detections()
            for det in new_detections:
                await websocket.send_json(det)

            # Periodic heartbeat
            heartbeat_interval += 1
            if heartbeat_interval >= 10:  # every ~5 seconds
                await websocket.send_json(processor.get_status())
                heartbeat_interval = 0

            await asyncio.sleep(0.5)

        # Stream ended
        await websocket.send_json({"type": "ended", "message": "Stream processing ended"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await websocket.close()
