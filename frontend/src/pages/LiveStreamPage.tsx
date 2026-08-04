import { useState, useEffect, useRef, useCallback } from 'react';
import {
  startStream,
  stopStream,
  getStreamWsUrl,
  listVideos,
  classifyPoseWindow,
  saveLiveRecording,
} from '../api/client';
import type { StreamDetectionEvent, Video } from '../types';
import AlertFeed from '../components/AlertFeed';
import ClipLibrary from '../components/ClipLibrary';
import LiveStreamView from '../components/LiveStreamView';
import ClipCreator from '../components/ClipCreator';
import ClipSaveModal from '../components/ClipSaveModal';
import { notify, requestNotificationPermission } from '../utils/notifications';

function formatSessionDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m.toString().padStart(2, '0')}:${s.padStart(4, '0')}`;
}

// BiLSTM sliding-window classifier parameters (must match backend config.json).
const WINDOW_SIZE = 20;
const STRIDE = 10;
const SUSPICIOUS_THRESHOLD = 0.5;
const CLASSIFY_ALERT_COOLDOWN_MS = 3000;

// MediaRecorder codec priority. MP4 first (Chrome/Safari), WebM as fallback
// (Firefox and older browsers). Tested at runtime via isTypeSupported.
const MIME_CANDIDATES = [
  'video/mp4;codecs=avc1.42E01E',
  'video/webm;codecs=vp9',
  'video/webm;codecs=vp8',
  'video/webm',
];

function pickMimeType(): string | null {
  if (typeof MediaRecorder === 'undefined') return null;
  for (const mt of MIME_CANDIDATES) {
    try {
      if (MediaRecorder.isTypeSupported(mt)) return mt;
    } catch {
      /* some browsers throw on exotic codec strings */
    }
  }
  return null;
}

const PRIVACY_NOTICE = `This tool processes live video using pose estimation only. No facial recognition or person re-identification is performed.

How each source type is handled:
• Webcam — pose detection runs in your browser (MediaPipe WebAssembly). Raw webcam frames never leave your device.
• RTSP / IP camera — frames are processed in server memory only and are NOT persisted to disk. Only the derived pose landmarks and detection events reach the UI.
• Demo — a previously uploaded video file is analyzed; you can manage or delete it from the Videos tab.

The AI classifier consumes only 33 pose landmarks (normalized coordinates, velocities, visibility). All processing happens locally on this server; no video, frames, or results are sent to any third party.

This prototype is not production-compliant with GDPR, CCPA/CPRA, or KVKK; see LegalandOtherCompliances.md for a full disclosure of current gaps.

By proceeding, you confirm that you have the right to process this video source and consent to pose-based activity analysis.`;

const ALERT_DECAY_MS = 5000; // Alert badge stays red for 5 seconds after last detection

export default function LiveStreamPage() {
  const [source, setSource] = useState('');
  const [sourceType, setSourceType] = useState('webcam');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<StreamDetectionEvent[]>([]);
  const [status, setStatus] = useState<StreamDetectionEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [consentGiven, setConsentGiven] = useState(false);
  const [showConsent, setShowConsent] = useState(false);
  const [clipRefreshKey, setClipRefreshKey] = useState(0);
  const [latestAlert, setLatestAlert] = useState<StreamDetectionEvent | null>(null);
  const [demoVideo, setDemoVideo] = useState<Video | null>(null);
  const [saveModal, setSaveModal] = useState<{ start: number; end: number } | null>(null);
  const [sessionElapsed, setSessionElapsed] = useState(0);
  const [webcamRes, setWebcamRes] = useState<{ w: number; h: number } | null>(null);
  const [recording, setRecording] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const alertTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Browser-side pose → backend BiLSTM: sliding-window buffer + alert cooldown
  const landmarkBufferRef = useRef<number[][]>([]);
  const lastClassifyAlertRef = useRef<number>(0);
  // Track the sessionId in a ref so handleLandmarks can read the latest value
  // without forcing useBrowserPose to re-initialize on every session change
  const sessionIdRef = useRef<string | null>(null);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  // MediaRecorder state for webcam clip save/download
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingChunksRef = useRef<Blob[]>([]);
  const recordedMimeRef = useRef<string>('');
  const webcamStreamRef = useRef<MediaStream | null>(null);

  // Fetch first uploaded video on mount — used as clip source in demo mode
  useEffect(() => {
    listVideos()
      .then((videos) => { if (videos.length > 0) setDemoVideo(videos[0]); })
      .catch(() => {});
  }, []);

  // Session duration ticker (resets on new session)
  useEffect(() => {
    if (!sessionId) {
      setSessionElapsed(0);
      setWebcamRes(null);
      // Reset classify buffer so the next session starts fresh
      landmarkBufferRef.current = [];
      lastClassifyAlertRef.current = 0;
      return;
    }
    const startedAt = Date.now();
    setSessionElapsed(0);
    const intervalId = setInterval(() => {
      setSessionElapsed((Date.now() - startedAt) / 1000);
    }, 500);
    return () => clearInterval(intervalId);
  }, [sessionId]);

  // -------------------------------------------------------------------------
  // Browser pose → backend BiLSTM classifier pipeline
  // -------------------------------------------------------------------------
  // Fires at ~8 fps (125ms throttle inside useBrowserPose) with a flattened
  // 132-float pose vector. We accumulate into a sliding window of 20 frames
  // (2.5s @ 8fps — matches BiLSTM training), then POST to /classify-pose.
  // If the classifier returns Suspicious above the threshold, we surface it
  // through the same AlertFeed + notify() pipeline as WS-sourced detections.
  const handleLandmarks = useCallback(async (raw: number[]) => {
    landmarkBufferRef.current.push(raw);

    // Cap buffer to prevent memory growth under slow backend responses
    const maxBuffer = WINDOW_SIZE + STRIDE;
    if (landmarkBufferRef.current.length > maxBuffer) {
      landmarkBufferRef.current = landmarkBufferRef.current.slice(-maxBuffer);
    }

    if (landmarkBufferRef.current.length < WINDOW_SIZE) return;

    // Slide the window forward: take the oldest WINDOW_SIZE frames, drop STRIDE
    const windowFrames = landmarkBufferRef.current.slice(0, WINDOW_SIZE);
    landmarkBufferRef.current = landmarkBufferRef.current.slice(STRIDE);

    try {
      const result = await classifyPoseWindow(
        windowFrames,
        sessionIdRef.current ?? undefined,
      );
      if (result.label !== 'Suspicious' || result.probability < SUSPICIOUS_THRESHOLD) {
        return;
      }

      const now = Date.now();
      if (now - lastClassifyAlertRef.current < CLASSIFY_ALERT_COOLDOWN_MS) return;
      lastClassifyAlertRef.current = now;

      const event: StreamDetectionEvent = {
        type: 'detection',
        timestamp: new Date().toISOString(),
        label: result.label,
        confidence: result.probability,
        frame_number: 0,
      };
      setEvents((prev) => [event, ...prev].slice(0, 200));
      setLatestAlert(event);
      clearTimeout(alertTimerRef.current);
      alertTimerRef.current = setTimeout(
        () => setLatestAlert(null),
        ALERT_DECAY_MS,
      );
      notify({
        title: `🚨 ${event.label} detected`,
        body: `Confidence · ${(result.probability * 100).toFixed(0)}%`,
        tag: 'live-stream-detection',
      });
    } catch {
      // Silently drop — classifier errors must not break the camera UX
    }
  }, []);

  // -------------------------------------------------------------------------
  // MediaRecorder lifecycle for webcam clip save/download
  // -------------------------------------------------------------------------
  const startRecorder = useCallback((stream: MediaStream) => {
    const mimeType = pickMimeType();
    if (!mimeType) {
      // MediaRecorder unsupported in this browser — skip recording silently
      setRecording(false);
      mediaRecorderRef.current = null;
      return;
    }
    try {
      recordedMimeRef.current = mimeType;
      recordingChunksRef.current = [];
      const r = new MediaRecorder(stream, { mimeType });
      r.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          recordingChunksRef.current.push(e.data);
        }
      };
      r.start(1000); // 1-second timeslice
      mediaRecorderRef.current = r;
      setRecording(true);
    } catch {
      setRecording(false);
      mediaRecorderRef.current = null;
    }
  }, []);

  const stopRecorder = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const r = mediaRecorderRef.current;
      const mime = recordedMimeRef.current;
      if (!r) {
        resolve(null);
        return;
      }
      if (r.state === 'inactive') {
        const blob = new Blob(recordingChunksRef.current, { type: mime });
        resolve(blob.size > 0 ? blob : null);
        return;
      }
      r.addEventListener(
        'stop',
        () => {
          const blob = new Blob(recordingChunksRef.current, { type: mime });
          resolve(blob.size > 0 ? blob : null);
        },
        { once: true },
      );
      try {
        r.stop();
      } catch {
        resolve(null);
      }
    });
  }, []);

  const handleStreamReady = useCallback(
    (stream: MediaStream | null) => {
      webcamStreamRef.current = stream;
      if (stream) {
        startRecorder(stream);
      } else {
        // Stream released — stop recorder cleanly, drop any buffered chunks
        const r = mediaRecorderRef.current;
        if (r && r.state !== 'inactive') {
          try {
            r.stop();
          } catch {
            /* noop */
          }
        }
        mediaRecorderRef.current = null;
        recordingChunksRef.current = [];
        recordedMimeRef.current = '';
        setRecording(false);
      }
    },
    [startRecorder],
  );

  const handleDownloadRecording = useCallback(async () => {
    const blob = await stopRecorder();
    if (!blob) return;
    const ext = blob.type.includes('mp4') ? 'mp4' : 'webm';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `live-recording-${Date.now()}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    // Restart recorder for subsequent save/download within the same session
    const stream = webcamStreamRef.current;
    if (stream && sessionIdRef.current) {
      startRecorder(stream);
    }
  }, [stopRecorder, startRecorder]);

  const handleSaveRecording = useCallback(async () => {
    const name = window.prompt('Enter recording name:');
    if (!name || !name.trim()) return;

    const blob = await stopRecorder();
    if (!blob) {
      alert('Recording is empty — nothing to save yet');
      return;
    }

    try {
      await saveLiveRecording(blob, name.trim());
      setClipRefreshKey((k) => k + 1);
    } catch (e) {
      alert(
        'Failed to save recording: ' +
          (e instanceof Error ? e.message : String(e)),
      );
    }

    // Restart recorder for subsequent saves within the same session
    const stream = webcamStreamRef.current;
    if (stream && sessionIdRef.current) {
      startRecorder(stream);
    }
  }, [stopRecorder, startRecorder]);

  const connectWs = useCallback((sid: string) => {
    const ws = new WebSocket(getStreamWsUrl(sid));
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setError('WebSocket connection failed');
    ws.onmessage = (e) => {
      const data: StreamDetectionEvent = JSON.parse(e.data);
      if (data.type === 'detection') {
        setEvents((prev) => [data, ...prev].slice(0, 200));
        setLatestAlert(data);
        clearTimeout(alertTimerRef.current);
        alertTimerRef.current = setTimeout(() => setLatestAlert(null), ALERT_DECAY_MS);

        // Desktop notification when tab is not visible — no spam while user
        // is already watching the AlertFeed (notify() skips when visible).
        const confidencePct = data.confidence != null
          ? ` · ${(data.confidence * 100).toFixed(0)}%`
          : '';
        const frameInfo = data.frame_number != null
          ? ` · frame ${data.frame_number.toLocaleString()}`
          : '';
        notify({
          title: `🚨 ${data.label ?? 'Suspicious activity'} detected`,
          body: `Confidence${confidencePct}${frameInfo}`,
          tag: 'live-stream-detection',
        });
      } else if (data.type === 'heartbeat') {
        setStatus(data);
      } else if (data.type === 'ended') {
        setConnected(false);
      }
    };
  }, []);

  function handleConnectClick() {
    if (!consentGiven) {
      setShowConsent(true);
      return;
    }
    doConnect();
  }

  async function doConnect() {
    if (!source.trim() && sourceType !== 'webcam' && sourceType !== 'demo') return;
    setError(null);
    setConnecting(true);
    setEvents([]);
    setLatestAlert(null);

    // Ask for notification permission in response to the user's Connect click
    // (browsers require a user gesture). No-op if already granted or denied.
    void requestNotificationPermission();

    try {
      const session = await startStream(
        sourceType === 'webcam' ? (source.trim() || '0') : sourceType === 'demo' ? 'demo' : source.trim(),
        sourceType,
        true,
      );
      setSessionId(session.id);
      connectWs(session.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start stream');
    } finally {
      setConnecting(false);
    }
  }

  function handleConsentAccept() {
    setConsentGiven(true);
    setShowConsent(false);
    doConnect();
  }

  async function handleStop() {
    if (sessionId) {
      try { await stopStream(sessionId); } catch {}
    }
    wsRef.current?.close();
    setSessionId(null);
    setConnected(false);
    setLatestAlert(null);
  }

  useEffect(() => {
    return () => {
      wsRef.current?.close();
      clearTimeout(alertTimerRef.current);
      // Stop MediaRecorder on unmount to release the stream cleanly
      const r = mediaRecorderRef.current;
      if (r && r.state !== 'inactive') {
        try {
          r.stop();
        } catch {
          /* noop */
        }
      }
      mediaRecorderRef.current = null;
      recordingChunksRef.current = [];
    };
  }, []);

  const detectionCount = events.filter((e) => e.type === 'detection').length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white mb-1">Live Stream Analysis</h1>
        <p className="text-muted text-sm mb-4">
          Connect to your own camera for real-time suspicious activity detection
        </p>
      </div>

      {/* Privacy notice banner */}
      <div className="bg-accent/5 border border-accent/20 rounded-lg px-4 py-3 text-xs text-gray-400">
        <span className="text-accent font-medium">Privacy:</span> Pose-only inference. Webcam frames stay in your browser (client-side MediaPipe); RTSP frames are processed in server memory only and not stored. All processing is local. Prototype, not production-compliant — see LegalandOtherCompliances.md.
      </div>

      {/* Stream input */}
      <div className="bg-panel border border-gray-800 rounded-lg p-4 space-y-3">
        <div className="flex gap-3 flex-wrap">
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            disabled={!!sessionId}
            className="bg-surface border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 focus:border-accent focus:outline-none disabled:opacity-50"
          >
            <option value="webcam">Webcam</option>
            <option value="rtsp">RTSP / IP Camera</option>
            <option value="demo">Demo (Sample Video)</option>
          </select>
          <input
            type="text"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder={
              sourceType === 'webcam' ? 'Device index (default: 0)' :
              sourceType === 'demo' ? 'Uses first uploaded video' :
              'Enter your RTSP camera URL...'
            }
            className="flex-1 min-w-[200px] bg-surface border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 focus:border-accent focus:outline-none"
            disabled={!!sessionId || sourceType === 'demo'}
          />
          {!sessionId ? (
            <button
              onClick={handleConnectClick}
              disabled={connecting}
              className="px-6 py-2 bg-accent hover:bg-accent/80 disabled:opacity-40 disabled:cursor-not-allowed rounded text-sm text-white font-medium transition-colors"
            >
              {connecting ? 'Connecting...' : 'Connect'}
            </button>
          ) : (
            <button
              onClick={handleStop}
              className="px-6 py-2 bg-danger hover:bg-danger/80 rounded text-sm text-white font-medium transition-colors"
            >
              Stop
            </button>
          )}
        </div>
        {error && <p className="text-danger text-sm">{error}</p>}
      </div>

      {/* Active session: side-by-side layout */}
      {sessionId && (
        <>
          {/* Alert badge (prominent status indicator) */}
          <div className="flex gap-4 items-center flex-wrap">
            {latestAlert ? (
              <span className="flex items-center gap-2 text-sm font-bold text-danger">
                <span className="w-3 h-3 rounded-full bg-danger animate-pulse" />
                ALERT: {latestAlert.label} ({latestAlert.confidence ? `${(latestAlert.confidence * 100).toFixed(0)}%` : ''})
              </span>
            ) : (
              <span className="flex items-center gap-2 text-sm font-medium text-success">
                <span className={`w-2 h-2 rounded-full ${connected ? 'bg-success animate-pulse' : 'bg-gray-500'}`} />
                {connected ? 'MONITORING' : 'DISCONNECTED'}
              </span>
            )}
          </div>

          {/* Two-column layout: video preview + alerts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: webcam preview or status display */}
            <div className="lg:col-span-2 space-y-4">
              {sourceType === 'webcam' ? (
                <LiveStreamView
                  // Camera lifecycle is tied to the user's intent (an active
                  // session), NOT to the WebSocket connection state. The WS
                  // can drop for many reasons (backend cv2.VideoCapture failing
                  // in Docker, idle timeouts, the backend processor finishing,
                  // network blips) but the webcam should keep streaming and
                  // the browser-side pose overlay should keep working until
                  // the user explicitly clicks Stop.
                  active={!!sessionId}
                  alertLabel={latestAlert?.label}
                  alertConfidence={latestAlert?.confidence}
                  onMetadata={(w, h) => setWebcamRes({ w, h })}
                  onLandmarks={handleLandmarks}
                  onStreamReady={handleStreamReady}
                />
              ) : (
                <div className="bg-panel border border-gray-800 rounded-lg p-8 aspect-video flex flex-col items-center justify-center">
                  {latestAlert ? (
                    <>
                      <div className="w-16 h-16 bg-danger/20 rounded-full flex items-center justify-center mb-4 animate-pulse">
                        <svg className="w-8 h-8 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                        </svg>
                      </div>
                      <p className="text-danger font-bold text-lg">{latestAlert.label}</p>
                      <p className="text-muted text-sm mt-1">Confidence: {latestAlert.confidence ? `${(latestAlert.confidence * 100).toFixed(0)}%` : ''}</p>
                    </>
                  ) : (
                    <>
                      <div className="w-16 h-16 bg-success/20 rounded-full flex items-center justify-center mb-4">
                        <svg className="w-8 h-8 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                      <p className="text-success font-medium">All Clear</p>
                      <p className="text-muted text-sm mt-1">
                        {sourceType === 'demo' ? 'Processing demo video...' :
                         sourceType === 'rtsp' ? 'Processing RTSP stream...' :
                         'Processing stream...'}
                      </p>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Right: alert feed */}
            <div className="lg:col-span-1 min-h-[400px]">
              <AlertFeed events={events} />
            </div>
          </div>

          {/* Live metric cards (same visual style as Videos page VideoMetadata) */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="bg-panel border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-muted uppercase tracking-wider">Duration</p>
              <p className="text-sm font-mono text-gray-100 mt-1">{formatSessionDuration(sessionElapsed)}</p>
            </div>
            <div className="bg-panel border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-muted uppercase tracking-wider">Frames Analyzed</p>
              <p className="text-sm font-mono text-gray-100 mt-1">
                {status?.frames_analyzed?.toLocaleString() ?? '0'}
              </p>
            </div>
            <div className="bg-panel border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-muted uppercase tracking-wider">Resolution</p>
              <p className="text-sm font-mono text-gray-100 mt-1">
                {sourceType === 'webcam'
                  ? (webcamRes ? `${webcamRes.w} × ${webcamRes.h}` : '—')
                  : sourceType === 'demo' && demoVideo
                    ? `${demoVideo.width} × ${demoVideo.height}`
                    : '—'}
              </p>
            </div>
            <div className="bg-panel border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-muted uppercase tracking-wider">FPS Processing</p>
              <p className="text-sm font-mono text-gray-100 mt-1">
                {status?.fps_processing != null ? `${status.fps_processing.toFixed(1)} fps` : '— fps'}
              </p>
            </div>
            <div className="bg-panel border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-muted uppercase tracking-wider">Source</p>
              <p className="text-sm font-mono text-gray-100 mt-1 truncate" title={sourceType}>
                {sourceType.toUpperCase()}
              </p>
            </div>
            <div className="bg-panel border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-muted uppercase tracking-wider">Alerts</p>
              <p className="text-sm font-mono text-gray-100 mt-1">
                {detectionCount} alert{detectionCount !== 1 ? 's' : ''}
              </p>
            </div>
          </div>

          {/* Clip tool — three modes:
               - demo: reuse ClipCreator against the source video file
               - webcam: MediaRecorder in the browser, with Save/Download
               - rtsp: disabled (no in-browser stream to record) */}
          {sourceType === 'demo' && demoVideo ? (
            <ClipCreator
              sourceId={demoVideo.id}
              sourceType="video"
              duration={demoVideo.duration}
              currentTime={0}
              onSaveClick={(start, end) => setSaveModal({ start, end })}
            />
          ) : sourceType === 'webcam' ? (
            <div className="bg-panel border border-gray-800 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">
                  Clip Tool
                </h3>
                {recording ? (
                  <span className="flex items-center gap-2 text-xs text-danger font-medium">
                    <span className="w-2 h-2 rounded-full bg-danger animate-pulse" />
                    RECORDING
                  </span>
                ) : (
                  <span className="text-xs text-muted">Idle</span>
                )}
              </div>
              <p className="text-xs text-muted">
                {recording
                  ? 'Browser is capturing your webcam stream in memory. Click Save to upload as a clip or Download to grab a local copy.'
                  : 'Recording starts automatically when a session is active.'}
              </p>
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={handleDownloadRecording}
                  disabled={!recording}
                  className="px-4 py-2 bg-accent hover:bg-accent/80 disabled:opacity-40 disabled:cursor-not-allowed rounded text-sm text-white font-medium transition-colors"
                >
                  Download Recording
                </button>
                <button
                  onClick={handleSaveRecording}
                  disabled={!recording}
                  className="px-4 py-2 bg-success/20 hover:bg-success/30 border border-success/40 disabled:opacity-40 disabled:cursor-not-allowed rounded text-sm text-success font-medium transition-colors"
                >
                  Save to Library
                </button>
              </div>
              <p className="text-[10px] text-muted italic">
                Recording happens in your browser. Frames stay on your device until
                you explicitly click <span className="text-accent">Save to Library</span>,
                at which point the blob is uploaded and persisted as a clip. Clicking
                Save or Download restarts a fresh recording.
              </p>
            </div>
          ) : (
            <div className="bg-panel border border-gray-800 rounded-lg p-4 space-y-2 opacity-60">
              <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">Clip Tool</h3>
              <p className="text-xs text-muted">
                Clip generation is disabled for live RTSP sources in this prototype —
                no raw frames are stored on the server. Switch to{' '}
                <span className="text-accent">Webcam</span> for browser-side recording
                or <span className="text-accent">Demo</span> to clip the source video,
                or upload a video and clip it from the <span className="text-accent">Videos</span> tab.
              </p>
            </div>
          )}
        </>
      )}

      <ClipLibrary refreshKey={clipRefreshKey} />

      {/* Clip save modal */}
      {saveModal && demoVideo && (
        <ClipSaveModal
          sourceId={demoVideo.id}
          sourceType="video"
          sourceName={demoVideo.filename}
          startTime={saveModal.start}
          endTime={saveModal.end}
          onClose={() => setSaveModal(null)}
          onSaved={() => {
            setSaveModal(null);
            setClipRefreshKey((k) => k + 1);
          }}
        />
      )}

      {/* Consent modal */}
      {showConsent && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setShowConsent(false)}>
          <div className="bg-panel border border-gray-700 rounded-xl p-6 w-full max-w-lg space-y-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-medium text-white">Privacy & Consent</h3>
            <p className="text-sm text-gray-300 whitespace-pre-line">{PRIVACY_NOTICE}</p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowConsent(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-gray-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConsentAccept}
                className="px-4 py-2 bg-accent hover:bg-accent/80 rounded text-sm text-white font-medium transition-colors"
              >
                I Understand and Consent
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
