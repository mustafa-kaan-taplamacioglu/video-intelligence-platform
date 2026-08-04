import { useEffect, useRef } from 'react';
import { useBrowserPose } from '../hooks/useBrowserPose';

interface Props {
  active: boolean;
  alertLabel?: string;
  alertConfidence?: number;
  onMetadata?: (width: number, height: number) => void;
  /**
   * Fires (on a 125ms / 8 fps throttle) with the flattened 132-float pose
   * vector [x,y,z,visibility,...] whenever the browser-side MediaPipe detects
   * a person. Consumed by the parent to POST to the backend BiLSTM classifier.
   */
  onLandmarks?: (raw: number[]) => void;
  /**
   * Fires when the webcam MediaStream is acquired (or released). Parent uses
   * this to build a MediaRecorder for clip save/download, without having to
   * re-request getUserMedia itself.
   */
  onStreamReady?: (stream: MediaStream | null) => void;
}

// MediaPipe pose skeleton connections (same as DetectionPlayer)
const POSE_CONNECTIONS: [number, number][] = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],   // torso + arms
  [11, 23], [12, 24], [23, 24],                         // torso to hips
  [23, 25], [25, 27], [24, 26], [26, 28],               // legs
  [15, 17], [15, 19], [16, 18], [16, 20],               // hands
  [0, 1], [0, 4], [1, 2], [2, 3], [4, 5], [5, 6],      // face
  [9, 10],                                                // mouth
];

function getSkeletonColor(alertLabel?: string): string {
  if (!alertLabel) return '#5DCAA5'; // green = normal
  if (alertLabel === 'Suspicious' || alertLabel === 'Shoplifting' || alertLabel === 'Stealing') {
    return '#E24B4A'; // red
  }
  return '#EF9F27'; // amber
}

export default function LiveStreamView({
  active,
  alertLabel,
  alertConfidence,
  onMetadata,
  onLandmarks,
  onStreamReady,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Keep the latest onStreamReady callback in a ref so that the getUserMedia
  // effect (which depends on `active`) does not re-run every time the parent
  // re-renders with a new inline callback identity.
  const onStreamReadyRef = useRef<typeof onStreamReady>(onStreamReady);
  useEffect(() => {
    onStreamReadyRef.current = onStreamReady;
  }, [onStreamReady]);

  // Attach/detach webcam stream
  useEffect(() => {
    let cancelled = false;

    if (active) {
      navigator.mediaDevices
        .getUserMedia({ video: true, audio: false })
        .then((stream) => {
          if (cancelled) {
            stream.getTracks().forEach((t) => t.stop());
            return;
          }
          streamRef.current = stream;
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
          }
          // Notify parent so it can attach a MediaRecorder
          onStreamReadyRef.current?.(stream);
        })
        .catch(() => {
          // getUserMedia failed — silently ignore (permission denied, no camera)
        });
    }

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
      // Signal release so parent can tear down its MediaRecorder
      onStreamReadyRef.current?.(null);
    };
  }, [active]);

  const { landmarks, loading, error } = useBrowserPose(videoRef, active, onLandmarks);

  // Draw skeleton + bbox + label whenever landmarks update
  useEffect(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Match canvas to video element dimensions
    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (landmarks.length === 0) return;

    const W = canvas.width;
    const H = canvas.height;
    const color = getSkeletonColor(alertLabel);

    // --- Skeleton connections ---
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.8;
    for (const [i, j] of POSE_CONNECTIONS) {
      if (i >= landmarks.length || j >= landmarks.length) continue;
      const a = landmarks[i];
      const b = landmarks[j];
      const av = a.visibility ?? 1;
      const bv = b.visibility ?? 1;
      if (av < 0.5 || bv < 0.5) continue;
      ctx.beginPath();
      ctx.moveTo(a.x * W, a.y * H);
      ctx.lineTo(b.x * W, b.y * H);
      ctx.stroke();
    }

    // --- Keypoints ---
    ctx.fillStyle = color;
    for (const lm of landmarks) {
      const v = lm.visibility ?? 1;
      if (v < 0.5) continue;
      ctx.beginPath();
      ctx.arc(lm.x * W, lm.y * H, 4, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1.0;

    // --- Bounding box ---
    const visible = landmarks.filter((lm) => (lm.visibility ?? 1) > 0.5);
    if (visible.length >= 5) {
      const xs = visible.map((lm) => lm.x);
      const ys = visible.map((lm) => lm.y);
      const padX = 0.05;
      const padY = 0.08;
      const x1 = Math.max(0, Math.min(...xs) - padX) * W;
      const y1 = Math.max(0, Math.min(...ys) - padY) * H;
      const x2 = Math.min(1, Math.max(...xs) + padX) * W;
      const y2 = Math.min(1, Math.max(...ys) + padY) * H;
      const boxW = x2 - x1;
      const boxH = y2 - y1;

      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.globalAlpha = 0.9;
      ctx.strokeRect(x1, y1, boxW, boxH);

      const labelText = alertLabel
        ? `${alertLabel} ${alertConfidence != null ? `${(alertConfidence * 100).toFixed(0)}%` : ''}`.trim()
        : 'Person';

      ctx.font = 'bold 13px system-ui, sans-serif';
      const metrics = ctx.measureText(labelText);
      const labelPadX = 8;
      const labelPadY = 5;
      const labelW = metrics.width + labelPadX * 2;
      const labelH = 22;
      const labelY = y1 - labelH >= 0 ? y1 - labelH : y1;
      const labelX = x1;

      ctx.fillStyle = color;
      ctx.globalAlpha = 0.92;
      ctx.fillRect(labelX, labelY, labelW, labelH);

      ctx.fillStyle = '#ffffff';
      ctx.globalAlpha = 1.0;
      ctx.fillText(labelText, labelX + labelPadX, labelY + labelH - labelPadY);
    }

    ctx.globalAlpha = 1.0;
  }, [landmarks, alertLabel, alertConfidence]);

  return (
    <div className="relative bg-black rounded-lg overflow-hidden aspect-video">
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        onLoadedMetadata={() => {
          const v = videoRef.current;
          if (v && onMetadata) onMetadata(v.videoWidth, v.videoHeight);
        }}
        className="w-full h-full object-cover"
      />
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full pointer-events-none z-10"
      />

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60 z-20">
          <div className="text-center space-y-2">
            <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-gray-300 text-sm">Loading AI model...</p>
          </div>
        </div>
      )}

      {/* Error overlay */}
      {error && !loading && (
        <div className="absolute top-4 right-4 bg-danger/90 text-white px-3 py-1.5 rounded text-xs z-20">
          Pose model error: {error}
        </div>
      )}

      {/* Status badge */}
      {!loading && !error && (
        alertLabel ? (
          <div className="absolute top-4 left-4 bg-danger/90 text-white px-4 py-2 rounded-lg text-sm font-bold animate-pulse z-20">
            {alertLabel}{alertConfidence != null ? ` — ${(alertConfidence * 100).toFixed(0)}%` : ''}
          </div>
        ) : (
          <div className="absolute top-4 left-4 bg-success/80 text-white px-3 py-1.5 rounded-lg text-xs font-medium z-20">
            MONITORING
          </div>
        )
      )}
    </div>
  );
}
