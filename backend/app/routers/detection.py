"""AI video analysis endpoints — MediaPipe pose + LSTM activity detection."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.config import ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES, MAX_UPLOAD_SIZE, resolve_path
from app.database import get_db
from app.models import Video, DetectionResult
from app.schemas import AnalysisResponse, DetectionItem, DetectionSummary
from app.services.file_manager import save_upload
from app.services.video_processor import extract_metadata
from app.services.activity_classifier import get_classifier

router = APIRouter(prefix="/api/detection", tags=["detection"])


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_video(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a video and run AI activity detection."""
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only MP4 files are allowed")
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Only video/mp4 MIME type is allowed")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 500MB")
    await file.seek(0)

    # Save file
    video_id = str(uuid.uuid4())
    relative_path = await save_upload(file, video_id)
    abs_path = resolve_path(relative_path)

    # Extract video metadata
    try:
        meta = extract_metadata(abs_path)
    except Exception as e:
        os.remove(abs_path)
        raise HTTPException(status_code=400, detail=f"Failed to process video: {str(e)}")

    # Save video record
    video = Video(
        id=video_id,
        filename=file.filename,
        filepath=relative_path,
        filesize=len(content),
        **meta,
    )
    db.add(video)
    db.commit()

    # Run detection pipeline (auto-dispatches to lstm/mobilenet/mock)
    classifier = get_classifier()

    try:
        result = classifier.analyze_video_full(abs_path)
        detections = result["detections"]
        probability_curve = result.get("probability_curve", [])
        curve_timestamps = result.get("curve_timestamps", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

    # Save detection results to DB
    for det in detections:
        db.add(DetectionResult(
            id=str(uuid.uuid4()),
            video_id=video_id,
            start_time=det.start_time,
            end_time=det.end_time,
            label=det.label,
            confidence=det.confidence,
        ))
    db.commit()

    # Build response
    detection_items = [
        DetectionItem(
            start_time=d.start_time,
            end_time=d.end_time,
            label=d.label,
            confidence=d.confidence,
        )
        for d in detections
    ]

    by_class: dict[str, int] = {}
    for d in detections:
        by_class[d.label] = by_class.get(d.label, 0) + 1

    risk_level = "LOW"
    if len(detections) >= 3:
        risk_level = "HIGH"
    elif len(detections) >= 1:
        risk_level = "MEDIUM"

    fps_analyzed = classifier.config.get(
        "mobilenet_target_fps" if classifier.mode == "mobilenet" else "target_fps", 5
    )

    return AnalysisResponse(
        video_id=video_id,
        duration=meta["duration"],
        fps_analyzed=fps_analyzed,
        detections=detection_items,
        summary=DetectionSummary(
            total_detections=len(detections),
            by_class=by_class,
            risk_level=risk_level,
        ),
        probability_curve=probability_curve,
        curve_timestamps=curve_timestamps,
    )


@router.get("/{video_id}/pose/{frame_number}")
def get_pose(video_id: str, frame_number: int, db: Session = Depends(get_db)):
    """Get pose landmarks for a specific frame (for overlay rendering)."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    abs_path = resolve_path(video.filepath)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    import cv2
    cap = cv2.VideoCapture(abs_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_number < 0 or frame_number >= total:
        cap.release()
        raise HTTPException(status_code=400, detail="Frame number out of range")

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise HTTPException(status_code=500, detail="Failed to read frame")

    # Extract pose landmarks for this frame using MediaPipe Tasks API
    landmarks = []
    landmark_names = ["nose", "left_eye_inner", "left_eye", "left_eye_outer",
        "right_eye_inner", "right_eye", "right_eye_outer", "left_ear", "right_ear",
        "mouth_left", "mouth_right", "left_shoulder", "right_shoulder",
        "left_elbow", "right_elbow", "left_wrist", "right_wrist",
        "left_pinky", "right_pinky", "left_index", "right_index",
        "left_thumb", "right_thumb", "left_hip", "right_hip",
        "left_knee", "right_knee", "left_ankle", "right_ankle",
        "left_heel", "right_heel", "left_foot_index", "right_foot_index"]

    try:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode
        from pathlib import Path

        pose_model_path = Path(__file__).resolve().parent.parent.parent / "ml" / "models" / "pose_landmarker_lite.task"
        if pose_model_path.exists():
            options = PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(pose_model_path)),
                running_mode=RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=0.3,
                min_pose_presence_confidence=0.3,
                min_tracking_confidence=0.3,
            )
            with PoseLandmarker.create_from_options(options) as landmarker:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = landmarker.detect(mp_image)
                if result.pose_landmarks and len(result.pose_landmarks) > 0:
                    for i, lm in enumerate(result.pose_landmarks[0]):
                        landmarks.append({
                            "id": i,
                            "name": landmark_names[i] if i < len(landmark_names) else f"landmark_{i}",
                            "x": round(lm.x, 4),
                            "y": round(lm.y, 4),
                            "z": round(lm.z, 4),
                            "visibility": round(lm.visibility, 4),
                        })
    except Exception as e:
        import logging
        logging.warning(f"Pose extraction failed: {e}")

    # Fallback: empty landmarks list (frontend will skip drawing)

    timestamp = round(frame_number / fps, 2)

    # Check if this frame has a detection
    detection = None
    det_result = (
        db.query(DetectionResult)
        .filter(
            DetectionResult.video_id == video_id,
            DetectionResult.start_time <= timestamp,
            DetectionResult.end_time >= timestamp,
        )
        .first()
    )
    if det_result:
        detection = {"label": det_result.label, "confidence": det_result.confidence}

    return {
        "frame_number": frame_number,
        "timestamp": timestamp,
        "landmarks": landmarks,
        "detection": detection,
    }


@router.get("/{video_id}/results", response_model=AnalysisResponse)
def get_results(video_id: str, db: Session = Depends(get_db)):
    """Retrieve analysis results for a previously analyzed video."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    results = (
        db.query(DetectionResult)
        .filter(DetectionResult.video_id == video_id)
        .order_by(DetectionResult.start_time)
        .all()
    )

    detection_items = [
        DetectionItem(
            start_time=r.start_time,
            end_time=r.end_time,
            label=r.label,
            confidence=r.confidence,
        )
        for r in results
    ]

    by_class: dict[str, int] = {}
    for r in results:
        by_class[r.label] = by_class.get(r.label, 0) + 1

    risk_level = "LOW"
    if len(results) >= 3:
        risk_level = "HIGH"
    elif len(results) >= 1:
        risk_level = "MEDIUM"

    return AnalysisResponse(
        video_id=video_id,
        duration=video.duration,
        fps_analyzed=get_classifier().config["target_fps"],
        detections=detection_items,
        summary=DetectionSummary(
            total_detections=len(results),
            by_class=by_class,
            risk_level=risk_level,
        ),
    )
