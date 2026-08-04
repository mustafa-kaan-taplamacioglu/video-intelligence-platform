from datetime import datetime
from pydantic import BaseModel, field_validator


class VideoResponse(BaseModel):
    id: str
    filename: str
    filesize: int
    duration: float
    frame_count: int
    width: int
    height: int
    fps: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipRequest(BaseModel):
    start_time: float
    end_time: float

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be greater than start_time")
        return v


class ClipCreateRequest(BaseModel):
    video_id: str
    name: str
    start_time: float
    end_time: float

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be greater than start_time")
        return v


class SubClipCreateRequest(BaseModel):
    name: str
    start_time: float
    end_time: float

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be greater than start_time")
        return v


class DetectionItem(BaseModel):
    start_time: float
    end_time: float
    label: str
    confidence: float


class DetectionSummary(BaseModel):
    total_detections: int
    by_class: dict[str, int]
    risk_level: str


class AnalysisResponse(BaseModel):
    video_id: str
    duration: float
    fps_analyzed: float
    detections: list[DetectionItem]
    summary: DetectionSummary
    probability_curve: list[float] = []
    curve_timestamps: list[float] = []


class StreamStartRequest(BaseModel):
    source: str
    source_type: str  # "rtsp", "webcam", "demo"
    consent_given: bool


class StreamSessionResponse(BaseModel):
    id: str
    source_url: str
    source_type: str
    status: str
    consent_given: bool = False
    started_at: datetime


class StreamDetectionResponse(BaseModel):
    type: str = "detection"
    timestamp: str
    frame_number: int
    label: str
    confidence: float


class ClipResponse(BaseModel):
    id: str
    video_id: str
    video_filename: str
    name: str
    start_time: float
    end_time: float
    created_at: datetime
    source_clip_id: str | None = None
    filesize: int | None = None
    duration: float | None = None
    frame_count: int | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None


class PoseWindowRequest(BaseModel):
    """Browser-side pose window streamed to the stateless /classify-pose
    endpoint. Each inner list is 132 floats: 33 MediaPipe landmarks ×
    (x, y, z, visibility)."""
    landmarks: list[list[float]]
    session_id: str | None = None


class PoseClassificationResponse(BaseModel):
    """Response from /classify-pose — a single BiLSTM inference result."""
    probability: float
    label: str
    mode: str = "lstm"
    persisted: bool = False


class LiveRecordingSaveResponse(BaseModel):
    """Response from /save-recording — newly-created Video + Clip records."""
    video: dict
    clip: dict
