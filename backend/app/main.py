import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import UPLOADS_DIR, CLIPS_DIR
from app.database import engine, Base, SessionLocal
from app.routers import videos, clips, detection, livestream
from app.services.demo_seeder import seed_demo_videos

logger = logging.getLogger(__name__)


def _migrate_tables(eng):
    """Add new columns to existing tables (SQLite ALTER TABLE)."""
    migrations = {
        "clips": [
            ("source_clip_id", "TEXT REFERENCES clips(id) ON DELETE SET NULL"),
            ("filesize", "INTEGER"),
            ("duration", "REAL"),
            ("frame_count", "INTEGER"),
            ("width", "INTEGER"),
            ("height", "INTEGER"),
            ("fps", "REAL"),
        ],
        "stream_sessions": [
            ("consent_given", "INTEGER DEFAULT 0"),
        ],
    }
    with eng.connect() as conn:
        for table, columns in migrations.items():
            for col_name, col_type in columns:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                except Exception:
                    pass
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (won't add columns to existing tables)
    Base.metadata.create_all(bind=engine)
    # Migrate existing tables with new columns
    _migrate_tables(engine)
    # Create storage directories
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    # Seed demo videos on first run (idempotent — skips if DB already populated)
    db = SessionLocal()
    try:
        seeded = seed_demo_videos(db)
        if seeded > 0:
            logger.info("Startup: seeded %d demo video(s) into database", seeded)
    except Exception as exc:
        logger.warning("Startup: demo seed raised %s — continuing", exc)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Video Intelligence Platform",
    description="Real-time video activity detection: upload, playback, metadata, clipping, and AI inference (MediaPipe pose + LSTM)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router)
app.include_router(clips.router)
app.include_router(detection.router)
app.include_router(livestream.router)
