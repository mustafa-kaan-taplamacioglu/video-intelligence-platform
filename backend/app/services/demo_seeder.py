"""First-run demo data seeder.

On application startup, if the `videos` table is empty and the
`backend/demo_videos/` directory contains one or more MP4 files, each file is
copied into `storage/uploads/{uuid}.mp4`, its metadata is extracted via
OpenCV, and a matching `Video` + full-duration `Clip` record is inserted.

Why this exists:
  - The project ships with a handful of sample videos so that anyone cloning
    the repository gets an immediately-usable populated demo environment,
    without having to drag-and-drop their own files first.
  - Seeding happens at runtime (not Docker build time) so the bind-mounted
    `storage/` directory receives fresh UUID-named copies that coexist with
    any subsequent user uploads.

Idempotence:
  - Skips entirely if the `videos` table is non-empty.
  - Skips if the `demo_videos/` directory is missing or empty.
  - Per-file failures (corrupt MP4, OpenCV error) are logged and skipped;
    other files continue to seed.

Provenance note:
  - The committed demo videos are third-party clips collected from public
    sources on the internet. They depict real people, are not the author's own
    work, and are not covered by this project's MIT license. They exist only so
    a first run has something to display. See DISCLAIMER.md for the full data
    provenance statement and the takedown contact.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import CLIPS_DIR, UPLOADS_DIR
from app.models import Clip, Video
from app.services.video_processor import create_clip, extract_metadata

logger = logging.getLogger(__name__)

# backend/app/services/demo_seeder.py → parents: services → app → backend
# So demo_videos/ lives at backend/demo_videos/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_VIDEOS_DIR = _BACKEND_ROOT / "demo_videos"


def seed_demo_videos(db: Session) -> int:
    """Seed the database with demo videos on first run.

    Safe to call on every startup — idempotent. Returns the number of videos
    successfully seeded (zero on subsequent runs).
    """
    existing = db.query(Video).count()
    if existing > 0:
        logger.info(
            "Demo seed skipped: %d video(s) already present in database",
            existing,
        )
        return 0

    if not DEMO_VIDEOS_DIR.exists():
        logger.info("Demo seed skipped: %s not found", DEMO_VIDEOS_DIR)
        return 0

    mp4_files = sorted(DEMO_VIDEOS_DIR.glob("*.mp4"))
    if not mp4_files:
        logger.info("Demo seed skipped: no .mp4 files in %s", DEMO_VIDEOS_DIR)
        return 0

    logger.info("Demo seed starting: %d candidate file(s)", len(mp4_files))
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)

    seeded = 0
    for source in mp4_files:
        video_dest: Path | None = None
        clip_dest: Path | None = None
        try:
            video_id = str(uuid.uuid4())
            video_rel = f"uploads/{video_id}.mp4"
            video_dest = UPLOADS_DIR / f"{video_id}.mp4"

            # 1) Copy the demo file into storage/uploads/ with a UUID name so
            #    it coexists with any subsequent user uploads without collision.
            shutil.copy2(source, video_dest)

            # 2) Extract metadata via OpenCV (ffmpeg backend).
            meta = extract_metadata(str(video_dest))
            video_filesize = video_dest.stat().st_size

            video = Video(
                id=video_id,
                filename=source.name,
                filepath=video_rel,
                filesize=video_filesize,
                **meta,
            )
            db.add(video)

            # 3) Create an independent clip file (full duration, ffmpeg stream
            #    copy + faststart — identical to POST /api/clips flow). This
            #    gives the Clip its own filepath so deleting the clip does NOT
            #    delete the underlying Video file.
            clip_id = str(uuid.uuid4())
            clip_rel = f"clips/{clip_id}.mp4"
            clip_dest = CLIPS_DIR / f"{clip_id}.mp4"
            create_clip(
                str(video_dest),
                str(clip_dest),
                0.0,
                meta["duration"],
            )
            clip_meta = extract_metadata(str(clip_dest))
            clip_filesize = clip_dest.stat().st_size

            clip = Clip(
                id=clip_id,
                video_id=video_id,
                name=source.stem,  # filename without the .mp4 suffix
                start_time=0.0,
                end_time=meta["duration"],
                filepath=clip_rel,
                filesize=clip_filesize,
                **clip_meta,
            )
            db.add(clip)

            seeded += 1
            logger.info(
                "Seeded: %s (%.1fs, %dx%d @ %.1ffps)",
                source.name,
                meta["duration"],
                meta["width"],
                meta["height"],
                meta["fps"],
            )
        except Exception as exc:
            # A single bad file shouldn't block the rest of the seed.
            logger.warning("Failed to seed %s: %s", source.name, exc)
            db.rollback()
            # Clean up any partial files from a failed attempt.
            for path in (video_dest, clip_dest):
                try:
                    if path is not None and path.exists():
                        path.unlink()
                except Exception:
                    pass
            continue

    db.commit()
    logger.info("Demo seed complete: %d video(s) + %d clip(s) created", seeded, seeded)
    return seeded
