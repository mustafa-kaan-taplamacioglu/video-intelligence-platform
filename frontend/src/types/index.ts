export interface Video {
  id: string;
  filename: string;
  filesize: number;
  duration: number;
  frame_count: number;
  width: number;
  height: number;
  fps: number;
  created_at: string;
}

export interface Clip {
  id: string;
  video_id: string;
  video_filename: string;
  name: string;
  start_time: number;
  end_time: number;
  created_at: string;
  source_clip_id?: string;
  filesize?: number;
  duration?: number;
  frame_count?: number;
  width?: number;
  height?: number;
  fps?: number;
}

export interface ClipCreateRequest {
  video_id: string;
  name: string;
  start_time: number;
  end_time: number;
}

export interface MediaInfo {
  duration: number;
  frame_count: number;
  width: number;
  height: number;
  fps: number;
  filesize: number;
  filename: string;
}

export interface DetectionItem {
  start_time: number;
  end_time: number;
  label: string;
  confidence: number;
}

export interface DetectionSummary {
  total_detections: number;
  by_class: Record<string, number>;
  risk_level: string;
}

export interface AnalysisResponse {
  video_id: string;
  duration: number;
  fps_analyzed: number;
  detections: DetectionItem[];
  summary: DetectionSummary;
  probability_curve?: number[];
  curve_timestamps?: number[];
}

export interface PoseLandmark {
  id: number;
  name: string;
  x: number;
  y: number;
  z: number;
  visibility: number;
}

export interface PoseFrame {
  frame_number: number;
  timestamp: number;
  landmarks: PoseLandmark[];
  detection: { label: string; confidence: number } | null;
}

export interface StreamSession {
  id: string;
  source_url: string;
  source_type: string;
  status: string;
  consent_given?: boolean;
  started_at: string;
}

export interface StreamDetectionEvent {
  type: 'detection' | 'heartbeat' | 'ended' | 'error';
  timestamp?: string;
  frame_number?: number;
  label?: string;
  confidence?: number;
  fps_processing?: number;
  frames_analyzed?: number;
  message?: string;
}
