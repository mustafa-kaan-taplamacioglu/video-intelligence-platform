import type { DetectionItem } from '../types';

interface Props {
  duration: number;
  detections: DetectionItem[];
  currentTime: number;
  onSeek: (time: number) => void;
  probabilityCurve?: number[];
  curveTimestamps?: number[];
}

function probabilityToColor(p: number): string {
  // 0 → green, 0.5 → amber, 1 → red
  if (p < 0.4) return 'rgba(93, 202, 165, 0.5)'; // success/green
  if (p < 0.7) return 'rgba(239, 159, 39, 0.6)'; // warning/amber
  return 'rgba(226, 75, 74, 0.75)';              // danger/red
}

export default function DetectionTimeline({
  duration,
  detections,
  currentTime,
  onSeek,
  probabilityCurve,
  curveTimestamps,
}: Props) {
  const hasCurve = probabilityCurve && curveTimestamps && probabilityCurve.length > 0;

  return (
    <div className="bg-panel border border-gray-800 rounded-lg p-4 space-y-2">
      <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">Detection Timeline</h3>

      <div
        className="relative h-12 bg-gray-800 rounded cursor-pointer overflow-hidden"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const pct = (e.clientX - rect.left) / rect.width;
          onSeek(pct * duration);
        }}
      >
        {/* Probability heatmap (gradient from curve) */}
        {hasCurve ? (
          <>
            {probabilityCurve!.map((prob, i) => {
              const ts = curveTimestamps![i];
              const nextTs = curveTimestamps![i + 1] ?? ts + (duration / probabilityCurve!.length);
              const left = (ts / duration) * 100;
              const width = ((nextTs - ts) / duration) * 100;
              return (
                <div
                  key={i}
                  className="absolute top-0 h-full"
                  style={{
                    left: `${left}%`,
                    width: `${Math.max(width, 0.5)}%`,
                    background: probabilityToColor(prob),
                  }}
                  title={`${ts.toFixed(1)}s — ${(prob * 100).toFixed(0)}%`}
                />
              );
            })}
          </>
        ) : (
          // Fallback: green background
          <div className="absolute inset-0 bg-success/20" />
        )}

        {/* Peak detection markers (vertical lines) */}
        {detections.map((det, i) => {
          const center = (det.start_time + det.end_time) / 2;
          const left = (center / duration) * 100;
          return (
            <div
              key={i}
              className="absolute top-0 h-full w-0.5 bg-white shadow-[0_0_4px_rgba(255,255,255,0.8)]"
              style={{ left: `${left}%` }}
              title={`${det.label} at ${center.toFixed(1)}s (${(det.confidence * 100).toFixed(0)}%)`}
            />
          );
        })}

        {/* Detection markers (small dots above timeline) */}
        {detections.map((det, i) => {
          const center = (det.start_time + det.end_time) / 2;
          const left = (center / duration) * 100;
          return (
            <div
              key={`dot-${i}`}
              className="absolute -top-1 w-2 h-2 rounded-full bg-danger border border-white z-20"
              style={{ left: `calc(${left}% - 4px)` }}
            />
          );
        })}

        {/* Playhead */}
        <div
          className="absolute top-0 h-full w-0.5 bg-cyan-400 z-30 pointer-events-none"
          style={{ left: `${(currentTime / duration) * 100}%` }}
        />
      </div>

      {/* Legend */}
      <div className="flex gap-4 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded" style={{ background: 'rgba(93,202,165,0.5)' }} />
          Normal
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded" style={{ background: 'rgba(239,159,39,0.6)' }} />
          Uncertain
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded" style={{ background: 'rgba(226,75,74,0.75)' }} />
          Suspicious
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-danger border border-white" />
          Detection peak
        </span>
        <span className="ml-auto">{detections.length} peak{detections.length !== 1 ? 's' : ''}</span>
      </div>
    </div>
  );
}
