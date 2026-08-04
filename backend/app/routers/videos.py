import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES, MAX_UPLOAD_SIZE, CLIPS_DIR, resolve_path
from app.database import get_db
from app.models import Video
from app.schemas import VideoResponse, ClipRequest
from app.services.file_manager import save_upload
from app.services.video_processor import extract_metadata, create_clip

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.post("/upload", response_model=VideoResponse, status_code=201)
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Validate extension
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only MP4 files are allowed")

    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Only video/mp4 MIME type is allowed")

    # Check file size by reading content
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 500MB")
    await file.seek(0)

    # Save file
    video_id = str(uuid.uuid4())
    relative_path = await save_upload(file, video_id)
    abs_path = resolve_path(relative_path)

    # Extract metadata
    try:
        metadata = extract_metadata(abs_path)
    except Exception as e:
        os.remove(abs_path)
        raise HTTPException(status_code=400, detail=f"Failed to process video: {str(e)}")

    # Create database record (store relative path for portability)
    video = Video(
        id=video_id,
        filename=file.filename,
        filepath=relative_path,
        filesize=len(content),
        **metadata,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    return video


@router.get("", response_model=list[VideoResponse])
def list_videos(db: Session = Depends(get_db)):
    return db.query(Video).order_by(Video.created_at.desc()).all()


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(video_id: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.get("/{video_id}/stream")
async def stream_video(video_id: str, request: Request, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    filepath = resolve_path(video.filepath)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    file_size = os.path.getsize(filepath)
    range_header = request.headers.get("range")

    if range_header:
        # Parse range header: "bytes=start-end"
        range_str = range_header.replace("bytes=", "")
        parts = range_str.split("-")
        start = int(parts[0])
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iter_file():
            with open(filepath, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
            },
        )

    return FileResponse(
        path=filepath,
        media_type="video/mp4",
        filename=video.filename,
        headers={"Accept-Ranges": "bytes"},
    )


@router.post("/{video_id}/clip")
def generate_clip(video_id: str, clip_req: ClipRequest, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if clip_req.start_time < 0 or clip_req.end_time > video.duration:
        raise HTTPException(status_code=400, detail="Timestamps out of video bounds")

    # Generate clip to temp file
    clip_filename = f"clip_{clip_req.start_time:.1f}-{clip_req.end_time:.1f}.mp4"
    output_path = str(CLIPS_DIR / f"temp_{uuid.uuid4()}.mp4")

    try:
        create_clip(resolve_path(video.filepath), output_path, clip_req.start_time, clip_req.end_time)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate clip: {str(e)}")

    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=clip_filename,
        headers={"Content-Disposition": f'attachment; filename="{clip_filename}"'},
    )
