import axios from 'axios';
import type { Video, Clip, ClipCreateRequest, AnalysisResponse, PoseFrame, StreamSession } from '../types';

const api = axios.create({ baseURL: '/api' });

export async function uploadVideo(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<Video> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<Video>('/videos/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

export async function listVideos(): Promise<Video[]> {
  const { data } = await api.get<Video[]>('/videos');
  return data;
}

export async function getVideo(id: string): Promise<Video> {
  const { data } = await api.get<Video>(`/videos/${id}`);
  return data;
}

export function getStreamUrl(id: string): string {
  return `/api/videos/${id}/stream`;
}

export async function generateClip(
  videoId: string,
  startTime: number,
  endTime: number,
): Promise<Blob> {
  const { data } = await api.post(
    `/videos/${videoId}/clip`,
    { start_time: startTime, end_time: endTime },
    { responseType: 'blob' },
  );
  return data;
}

export async function saveClip(req: ClipCreateRequest): Promise<Clip> {
  const { data } = await api.post<Clip>('/clips', req);
  return data;
}

export async function listClips(): Promise<Clip[]> {
  const { data } = await api.get<Clip[]>('/clips');
  return data;
}

export async function downloadClip(clipId: string): Promise<Blob> {
  const { data } = await api.get(`/clips/${clipId}/download`, { responseType: 'blob' });
  return data;
}

export async function deleteClip(clipId: string): Promise<void> {
  await api.delete(`/clips/${clipId}`);
}

export async function getClip(id: string): Promise<Clip> {
  const { data } = await api.get<Clip>(`/clips/${id}`);
  return data;
}

export function getClipStreamUrl(id: string): string {
  return `/api/clips/${id}/stream`;
}

export async function saveSubClip(
  clipId: string,
  req: { name: string; start_time: number; end_time: number },
): Promise<Clip> {
  const { data } = await api.post<Clip>(`/clips/${clipId}/subclip`, req);
  return data;
}

// Detection API
export async function analyzeVideo(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<AnalysisResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<AnalysisResponse>('/detection/analyze', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

export async function getDetectionResults(videoId: string): Promise<AnalysisResponse> {
  const { data } = await api.get<AnalysisResponse>(`/detection/${videoId}/results`);
  return data;
}

export async function getPoseLandmarks(videoId: string, frameNumber: number): Promise<PoseFrame> {
  const { data } = await api.get<PoseFrame>(`/detection/${videoId}/pose/${frameNumber}`);
  return data;
}

// Livestream API
export async function startStream(source: string, sourceType: string, consentGiven: boolean): Promise<StreamSession> {
  const { data } = await api.post<StreamSession>('/livestream/start', {
    source,
    source_type: sourceType,
    consent_given: consentGiven,
  });
  return data;
}

export async function stopStream(sessionId: string): Promise<void> {
  await api.post(`/livestream/${sessionId}/stop`);
}

export function getStreamWsUrl(sessionId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/livestream/${sessionId}/ws`;
}

export interface PoseClassificationResponse {
  probability: number;
  label: string;
  mode: string;
  persisted: boolean;
}

/**
 * Stateless BiLSTM classifier for browser-extracted pose windows.
 * `landmarks` must be a (window_size × 132) array: 33 MediaPipe landmarks
 * flattened to (x, y, z, visibility) per frame. If `sessionId` is provided
 * and the classification crosses the alert threshold, the detection is
 * also persisted server-side to the stream_detections table.
 */
export async function classifyPoseWindow(
  landmarks: number[][],
  sessionId?: string,
): Promise<PoseClassificationResponse> {
  const { data } = await api.post<PoseClassificationResponse>(
    '/livestream/classify-pose',
    { landmarks, session_id: sessionId },
  );
  return data;
}

export interface LiveRecordingSaveResponse {
  video: Video;
  clip: Clip;
}

/**
 * Save a browser MediaRecorder blob as a Video + full-duration Clip.
 * Accepts both MP4 (Chrome/Safari MediaRecorder) and WebM (Firefox fallback).
 * On success, the clip appears in the ClipLibrary immediately.
 */
export async function saveLiveRecording(
  blob: Blob,
  name: string,
): Promise<LiveRecordingSaveResponse> {
  const ext = blob.type.includes('mp4') ? 'mp4' : 'webm';
  const form = new FormData();
  form.append('file', blob, `${name}.${ext}`);
  form.append('name', name);
  const { data } = await api.post<LiveRecordingSaveResponse>(
    '/livestream/save-recording',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}
