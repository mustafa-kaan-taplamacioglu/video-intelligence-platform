import os
import shutil

from fastapi import UploadFile

from app.config import UPLOADS_DIR, STORAGE_PATH


async def save_upload(file: UploadFile, uuid: str) -> str:
    """Save uploaded file. Returns path relative to STORAGE_PATH for DB storage."""
    abs_path = UPLOADS_DIR / f"{uuid}.mp4"
    with open(str(abs_path), "wb") as f:
        shutil.copyfileobj(file.file, f)
    # Return relative path for portability between local and Docker
    return str(abs_path.relative_to(STORAGE_PATH))


def delete_file(relative_path: str):
    """Delete a file given its path relative to STORAGE_PATH."""
    if not relative_path:
        return
    abs_path = STORAGE_PATH / relative_path
    if abs_path.exists():
        os.remove(str(abs_path))
