import { useEffect, useRef, useCallback } from 'react';
import videojs from 'video.js';
import type Player from 'video.js/dist/types/player';
import { getPoseLandmarks } from '../api/client';
import type { DetectionItem, PoseLandmark } from '../types';

interface Props {
  streamUrl: string;
  videoId: string;
  detections: DetectionItem[];
  fps: number;
  onTimeUpdate?: (time: number) => void;
  seekTo?: number | null;
}

// MediaPipe pose skeleton connections
const POSE_CONNECTIONS: [number, number][] = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],   // torso + arms
  [11, 23], [12, 24], [23, 24],                         // torso to hips
  [23, 25], [25, 27], [24, 26], [26, 28],               // legs
  [15, 17], [15, 19], [16, 18], [16, 20],               // hands
  [0, 1], [0, 4], [1, 2], [2, 3], [4, 5], [5, 6],      // face
  [9, 10],                                                // mouth
];

function getDetectionAtTime(detections: DetectionItem[], time: number): DetectionItem | null {
  return detections.find(d => time >= d.start_time && time <= d.end_time) || null;
}

function getSkeletonColor(detection: DetectionItem | null): string {
  if (!detection) return '#5DCAA5'; // green = normal
  const label = detection.label;
  if (label === 'Suspicious' || label === 'Shoplifting' || label === 'Stealing') return '#E24B4A'; // red
  return '#EF9F27'; // amber
}

export default function DetectionPlayer({ streamUrl, videoId, detections, fps, onTimeUpdate, seekTo }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const playerRef = useRef<Player | null>(null);
  const animFrameRef = useRef<number>(0);
  const lastPoseFrameRef = useRef<number>(-1);
  const landmarksRef = useRef<PoseLandmark[]>([]);

  const drawPose = useCallback((landmarks: PoseLandmark[], detection: DetectionItem | null) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Match canvas to video dimensions
    const videoEl = containerRef.current?.querySelector('video');
    if (videoEl) {
      canvas.width = videoEl.clientWidth;
      canvas.height = videoEl.clientHeight;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (landmarks.length === 0) return;

    const W = canvas.width;
    const H = canvas.height;
    const color = getSkeletonColor(detection);

    // Draw skeleton connections
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.8;
    for (const [i, j] of POSE_CONNECTIONS) {
      if (i >= landmarks.length || j >= landmarks.length) continue;
      const a = landmarks[i];
      const b = landmarks[j];
      if (a.visibility < 0.5 || b.visibility < 0.5) continue;
      ctx.beginPath();
      ctx.moveTo(a.x * W, a.y * H);
      ctx.lineTo(b.x * W, b.y * H);
      ctx.stroke();
    }

    // Draw keypoints
    ctx.fillStyle = color;
    for (const lm of landmarks) {
      if (lm.visibility < 0.5) continue;
      ctx.beginPath();
      ctx.arc(lm.x * W, lm.y * H, 4, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1.0;

    // --- Bounding box around person ---
    const visible = landmarks.filter((lm) => lm.visibility > 0.5);
    if (visible.length >= 5) {
      const xs = visible.map((lm) => lm.x);
      const ys = visible.map((lm) => lm.y);
      const padX = 0.05;  // 5% horizontal padding
      const padY = 0.08;  // 8% vertical padding (to catch head)
      const x1 = Math.max(0, Math.min(...xs) - padX) * W;
      const y1 = Math.max(0, Math.min(...ys) - padY) * H;
      const x2 = Math.min(1, Math.max(...xs) + padX) * W;
      const y2 = Math.min(1, Math.max(...ys) + padY) * H;
      const boxW = x2 - x1;
      const boxH = y2 - y1;

      // Draw rectangle
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.globalAlpha = 0.9;
      ctx.strokeRect(x1, y1, boxW, boxH);

      // Label text: "Suspicious (87%)" or "Person"
      const labelText = detection
        ? `${detection.label} ${(detection.confidence * 100).toFixed(0)}%`
        : 'Person';

      ctx.font = 'bold 13px system-ui, sans-serif';
      const metrics = ctx.measureText(labelText);
      const labelPadX = 8;
      const labelPadY = 5;
      const labelW = metrics.width + labelPadX * 2;
      const labelH = 22;
      // Position label above box; if too close to top, put it inside at top-left
      const labelY = y1 - labelH >= 0 ? y1 - labelH : y1;
      const labelX = x1;

      // Filled background
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.92;
      ctx.fillRect(labelX, labelY, labelW, labelH);

      // Label text (white)
      ctx.fillStyle = '#ffffff';
      ctx.globalAlpha = 1.0;
      ctx.fillText(labelText, labelX + labelPadX, labelY + labelH - labelPadY);
    }

    ctx.globalAlpha = 1.0;
  }, []);

  // Fetch pose landmarks periodically as video plays
  const fetchAndDrawPose = useCallback(async () => {
    const player = playerRef.current;
    if (!player || player.paused()) {
      animFrameRef.current = requestAnimationFrame(fetchAndDrawPose);
      return;
    }

    const currentTime = player.currentTime() ?? 0;
    const frameNumber = Math.floor(currentTime * (fps || 30));
    const detection = getDetectionAtTime(detections, currentTime);

    // Only fetch new landmarks every ~0.5s (not every frame)
    if (Math.abs(frameNumber - lastPoseFrameRef.current) > Math.max(1, fps / 2)) {
      lastPoseFrameRef.current = frameNumber;
      try {
        const pose = await getPoseLandmarks(videoId, frameNumber);
        landmarksRef.current = pose.landmarks;
      } catch {
        // Silently skip failed pose fetches
      }
    }

    drawPose(landmarksRef.current, detection);
    animFrameRef.current = requestAnimationFrame(fetchAndDrawPose);
  }, [videoId, detections, fps, drawPose]);

  useEffect(() => {
    if (!containerRef.current) return;

    const videoEl = document.createElement('video-js');
    videoEl.classList.add('vjs-big-play-centered');
    containerRef.current.appendChild(videoEl);

    const player = videojs(videoEl, {
      controls: true,
      responsive: true,
      fluid: true,
      sources: [{ src: streamUrl, type: 'video/mp4' }],
    });

    if (onTimeUpdate) {
      player.on('timeupdate', () => {
        onTimeUpdate(player.currentTime() ?? 0);
      });
    }

    player.on('play', () => {
      animFrameRef.current = requestAnimationFrame(fetchAndDrawPose);
    });

    player.on('pause', () => {
      cancelAnimationFrame(animFrameRef.current);
    });

    playerRef.current = player;

    return () => {
      cancelAnimationFrame(animFrameRef.current);
      if (playerRef.current) {
        playerRef.current.dispose();
        playerRef.current = null;
      }
    };
  }, [streamUrl]);

  // Handle seekTo from parent
  useEffect(() => {
    if (seekTo != null && playerRef.current) {
      playerRef.current.currentTime(seekTo);
    }
  }, [seekTo]);

  return (
    <div ref={containerRef} className="relative rounded-lg overflow-hidden">
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full pointer-events-none z-10"
      />
    </div>
  );
}
