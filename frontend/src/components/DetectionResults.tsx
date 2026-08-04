import type { DetectionItem } from '../types';

interface Props {
  detections: DetectionItem[];
  onJumpTo: (time: number) => void;
  onCreateClip: (start: number, end: number) => void;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m.toString().padStart(2, '0')}:${s.padStart(4, '0')}`;
}

const LABEL_STYLES: Record<string, string> = {
  Suspicious: 'text-danger bg-danger/10 border-danger/30',
  Shoplifting: 'text-danger bg-danger/10 border-danger/30',
  Stealing: 'text-danger bg-danger/10 border-danger/30',
  Burglary: 'text-warning bg-warning/10 border-warning/30',
  Robbery: 'text-warning bg-warning/10 border-warning/30',
};

export default function DetectionResults({ detections, onJumpTo, onCreateClip }: Props) {
  if (detections.length === 0) {
    return (
      <div className="bg-panel border border-gray-800 rounded-lg p-6 text-center">
        <p className="text-success text-sm">No suspicious activity detected</p>
      </div>
    );
  }

  return (
    <div className="bg-panel border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800">
        <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">
          Detections ({detections.length})
        </h3>
      </div>
      <div className="divide-y divide-gray-800">
        {detections.map((det, i) => {
          const style = LABEL_STYLES[det.label] || 'text-muted bg-gray-800 border-gray-700';
          return (
            <div key={i} className="px-4 py-3 flex items-center gap-4">
              <span className={`px-2 py-1 rounded border text-xs font-medium ${style}`}>
                {det.label}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-mono text-gray-300">
                  {formatTime(det.start_time)} → {formatTime(det.end_time)}
                </p>
                <p className="text-xs text-muted">
                  Confidence: {(det.confidence * 100).toFixed(0)}%
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => onJumpTo(det.start_time)}
                  className="px-3 py-1.5 bg-accent/20 hover:bg-accent/30 border border-accent/30 rounded text-xs text-accent font-medium transition-colors"
                >
                  Jump to
                </button>
                <button
                  onClick={() => onCreateClip(det.start_time, det.end_time)}
                  className="px-3 py-1.5 bg-success/20 hover:bg-success/30 border border-success/30 rounded text-xs text-success font-medium transition-colors"
                >
                  Create Clip
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
