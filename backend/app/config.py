import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

STORAGE_PATH = Path(os.environ.get("STORAGE_PATH", str(BASE_DIR / "storage")))
UPLOADS_DIR = STORAGE_PATH / "uploads"
CLIPS_DIR = STORAGE_PATH / "clips"

# Ensure storage directories exist before SQLAlchemy tries to create the DB file
STORAGE_PATH.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{STORAGE_PATH / 'database.db'}"

MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = {".mp4"}
ALLOWED_MIME_TYPES = {"video/mp4"}


def resolve_path(relative_path: str) -> str:
    """Convert a relative storage path to an absolute path."""
    return str(STORAGE_PATH / relative_path)
