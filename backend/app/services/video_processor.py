import cv2
import ffmpeg


def extract_metadata(filepath: str) -> dict:
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {filepath}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()

    return {
        "duration": duration,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "fps": fps,
    }


def create_clip(input_path: str, output_path: str, start_time: float, end_time: float):
    (
        ffmpeg
        .input(input_path, ss=start_time, to=end_time)
        .output(output_path, c="copy", movflags="faststart")
        .overwrite_output()
        .run(quiet=True)
    )
