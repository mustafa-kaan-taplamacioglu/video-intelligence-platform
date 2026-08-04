import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import resolve_path
from app.database import get_db
from app.models import Clip, Video
from app.schemas import ClipCreateRequest, ClipResponse, SubClipCreateRequest
from app.services.file_manager import delete_file
from app.services.video_processor import create_clip, extract_metadata

router = APIRouter(prefix="/api/clips", tags=["clips"])


def _build_clip_response(clip: Clip, video_filename: str) -> ClipResponse:
    return ClipResponse(
        id=clip.id,
        video_id=clip.video_id,
        video_filename=video_filename,
        name=clip.name,
        start_time=clip.start_time,
        end_time=clip.end_time,
        created_at=clip.created_at,
        source_clip_id=clip.source_clip_id,
        filesize=clip.filesize,
        duration=clip.duration,
        frame_count=clip.frame_count,
        width=clip.width,
        height=clip.height,
        fps=clip.fps,
    )


@router.post("", response_model=ClipResponse, status_code=201)
def save_clip(req: ClipCreateRequest, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == req.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if req.start_time < 0 or req.end_time > video.duration:
        raise HTTPException(status_code=400, detail="Timestamps out of video bounds")

    clip_id = str(uuid.uuid4())
    relative_path = f"clips/{clip_id}.mp4"
    abs_path = resolve_path(relative_path)

    try:
        create_clip(resolve_path(video.filepath), abs_path, req.start_time, req.end_time)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate clip: {str(e)}")

    metadata = extract_metadata(abs_path)

    clip = Clip(
        id=clip_id,
        video_id=req.video_id,
        name=req.name,
        start_time=req.start_time,
        end_time=req.end_time,
        filepath=relative_path,
        filesize=os.path.getsize(abs_path),
        **metadata,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)

    return _build_clip_response(clip, video.filename)


@router.get("", response_model=list[ClipResponse])
def list_clips(db: Session = Depends(get_db)):
    clips = db.query(Clip, Video.filename).join(Video).order_by(Clip.created_at.desc()).all()
    return [_build_clip_response(clip, filename) for clip, filename in clips]


# Specific path routes MUST come before /{clip_id} catch-all
@router.get("/{clip_id}/download")
def download_clip(clip_id: str, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    abs_path = resolve_path(clip.filepath) if clip.filepath else ""
    if not clip.filepath or not os.path.exists(abs_path):
        video = db.query(Video).filter(Video.id == clip.video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Source video not found")

        relative_path = f"clips/{clip.id}.mp4"
        abs_path = resolve_path(relative_path)
        try:
            create_clip(resolve_path(video.filepath), abs_path, clip.start_time, clip.end_time)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to regenerate clip: {str(e)}")

        clip.filepath = relative_path
        db.commit()

    return FileResponse(
        path=abs_path,
        media_type="video/mp4",
        filename=f"{clip.name}.mp4",
        headers={"Content-Disposition": f'attachment; filename="{clip.name}.mp4"'},
    )


@router.get("/{clip_id}/stream")
async def stream_clip(clip_id: str, request: Request, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    filepath = resolve_path(clip.filepath)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Clip file not found on disk")

    file_size = os.path.getsize(filepath)
    range_header = request.headers.get("range")

    if range_header:
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
        filename=f"{clip.name}.mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.post("/{clip_id}/subclip", response_model=ClipResponse, status_code=201)
def create_subclip(clip_id: str, req: SubClipCreateRequest, db: Session = Depends(get_db)):
    parent_clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not parent_clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    clip_duration = parent_clip.duration or (parent_clip.end_time - parent_clip.start_time)
    if req.start_time < 0 or req.end_time > clip_duration:
        raise HTTPException(status_code=400, detail="Timestamps out of clip bounds")

    subclip_id = str(uuid.uuid4())
    relative_path = f"clips/{subclip_id}.mp4"
    abs_path = resolve_path(relative_path)

    try:
        create_clip(resolve_path(parent_clip.filepath), abs_path, req.start_time, req.end_time)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate sub-clip: {str(e)}")

    metadata = extract_metadata(abs_path)

    subclip = Clip(
        id=subclip_id,
        video_id=parent_clip.video_id,
        source_clip_id=clip_id,
        name=req.name,
        start_time=req.start_time,
        end_time=req.end_time,
        filepath=relative_path,
        filesize=os.path.getsize(abs_path),
        **metadata,
    )
    db.add(subclip)
    db.commit()
    db.refresh(subclip)

    video = db.query(Video).filter(Video.id == parent_clip.video_id).first()
    return _build_clip_response(subclip, video.filename if video else "unknown")


@router.get("/{clip_id}", response_model=ClipResponse)
def get_clip(clip_id: str, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    video = db.query(Video).filter(Video.id == clip.video_id).first()
    return _build_clip_response(clip, video.filename if video else "unknown")


@router.delete("/{clip_id}", status_code=204)
def delete_clip(clip_id: str, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    delete_file(clip.filepath)
    db.delete(clip)
    db.commit()
