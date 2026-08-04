from sqlalchemy import Column, Text, Integer, Float, DateTime, ForeignKey, func

from app.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(Text, primary_key=True)
    filename = Column(Text, nullable=False)
    filepath = Column(Text, nullable=False)
    filesize = Column(Integer, nullable=False)
    duration = Column(Float, nullable=False)
    frame_count = Column(Integer, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    fps = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Clip(Base):
    __tablename__ = "clips"

    id = Column(Text, primary_key=True)
    video_id = Column(Text, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    source_clip_id = Column(Text, ForeignKey("clips.id", ondelete="SET NULL"), nullable=True)
    name = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    filepath = Column(Text, nullable=True)
    filesize = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id = Column(Text, primary_key=True)
    video_id = Column(Text, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    label = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class StreamSession(Base):
    __tablename__ = "stream_sessions"

    id = Column(Text, primary_key=True)
    source_url = Column(Text, nullable=False)
    source_type = Column(Text, nullable=False)  # "rtsp", "webcam", "demo"
    status = Column(Text, server_default="active")
    consent_given = Column(Integer, server_default="0")
    started_at = Column(DateTime, server_default=func.now())
    stopped_at = Column(DateTime, nullable=True)


class StreamDetection(Base):
    __tablename__ = "stream_detections"

    id = Column(Text, primary_key=True)
    session_id = Column(Text, ForeignKey("stream_sessions.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    frame_num = Column(Integer, nullable=False)
    label = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
