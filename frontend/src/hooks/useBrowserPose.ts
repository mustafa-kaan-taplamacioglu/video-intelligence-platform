import { useEffect, useRef, useState, type RefObject } from 'react';
import { PoseLandmarker, FilesetResolver, type NormalizedLandmark } from '@mediapipe/tasks-vision';

interface UseBrowserPoseResult {
  landmarks: NormalizedLandmark[];
  loading: boolean;
  error: string | null;
}

const WASM_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.33/wasm';
const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task';

// Pose detection runs at ~15 fps for a smooth canvas overlay.
const THROTTLE_MS = 66;

// Landmarks sent to the backend classifier are throttled separately at 125ms
// (8 fps) to match the BiLSTM training sample rate exactly. Downsampling in
// the browser reduces WebSocket/HTTP traffic and ensures the velocity features
// computed on the backend use the same dt as during training.
const SEND_INTERVAL_MS = 125;

export function useBrowserPose(
  videoRef: RefObject<HTMLVideoElement | null>,
  enabled: boolean,
  onLandmarks?: (raw: number[]) => void,
): UseBrowserPoseResult {
  const [landmarks, setLandmarks] = useState<NormalizedLandmark[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const landmarkerRef = useRef<PoseLandmarker | null>(null);
  const rafRef = useRef<number>(0);
  const lastDetectRef = useRef<number>(0);
  const lastSentRef = useRef<number>(0);
  const mountedRef = useRef<boolean>(true);

  // Keep the latest callback in a ref so the RAF loop can read it without
  // re-initializing the MediaPipe landmarker when the callback identity
  // changes across parent renders.
  const onLandmarksRef = useRef<typeof onLandmarks>(onLandmarks);
  useEffect(() => {
    onLandmarksRef.current = onLandmarks;
  }, [onLandmarks]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled) {
      // cleanup on disable
      cancelAnimationFrame(rafRef.current);
      setLandmarks([]);
      if (landmarkerRef.current) {
        try { landmarkerRef.current.close(); } catch { /* noop */ }
        landmarkerRef.current = null;
      }
      return;
    }

    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);
      try {
        const vision = await FilesetResolver.forVisionTasks(WASM_CDN);
        const landmarker = await PoseLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: MODEL_URL,
            delegate: 'GPU',
          },
          runningMode: 'VIDEO',
          numPoses: 1,
        });

        if (cancelled || !mountedRef.current) {
          landmarker.close();
          return;
        }

        landmarkerRef.current = landmarker;
        setLoading(false);

        const detect = () => {
          const video = videoRef.current;
          const lm = landmarkerRef.current;

          if (!video || !lm || video.readyState < 2) {
            rafRef.current = requestAnimationFrame(detect);
            return;
          }

          const now = performance.now();
          if (now - lastDetectRef.current >= THROTTLE_MS) {
            lastDetectRef.current = now;
            try {
              const result = lm.detectForVideo(video, now);
              if (result.landmarks && result.landmarks.length > 0) {
                const firstPersonLandmarks = result.landmarks[0];
                setLandmarks(firstPersonLandmarks);

                // Send raw landmarks to backend on a separate 125ms throttle
                // (8 fps — matches BiLSTM training sample rate). Decoupled from
                // the 66ms detect throttle so canvas stays smooth while the
                // backend stream rate is exact.
                const cb = onLandmarksRef.current;
                if (cb && now - lastSentRef.current >= SEND_INTERVAL_MS) {
                  lastSentRef.current = now;
                  const flat: number[] = [];
                  for (const lm_ of firstPersonLandmarks) {
                    flat.push(
                      lm_.x,
                      lm_.y,
                      lm_.z,
                      lm_.visibility ?? 1.0, // guard: MediaPipe JS may omit visibility
                    );
                  }
                  if (flat.length === 33 * 4) {
                    cb(flat);
                  }
                }
              } else {
                setLandmarks([]);
              }
            } catch {
              // swallow — detection can fail transiently
            }
          }

          rafRef.current = requestAnimationFrame(detect);
        };

        rafRef.current = requestAnimationFrame(detect);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Failed to load pose model';
        setError(msg);
        setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      cancelAnimationFrame(rafRef.current);
      if (landmarkerRef.current) {
        try { landmarkerRef.current.close(); } catch { /* noop */ }
        landmarkerRef.current = null;
      }
    };
  }, [enabled, videoRef]);

  return { landmarks, loading, error };
}
