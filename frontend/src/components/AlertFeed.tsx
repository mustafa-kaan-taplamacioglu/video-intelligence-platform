import type { StreamDetectionEvent } from '../types';

interface Props {
  events: StreamDetectionEvent[];
}

const LABEL_STYLES: Record<string, string> = {
  Suspicious: 'border-danger/40 bg-danger/10',
  Shoplifting: 'border-danger/40 bg-danger/10',
  Stealing: 'border-danger/40 bg-danger/10',
  Burglary: 'border-warning/40 bg-warning/10',
  Robbery: 'border-warning/40 bg-warning/10',
};

export default function AlertFeed({ events }: Props) {
  const detections = events.filter((e) => e.type === 'detection');

  if (detections.length === 0) {
    return (
      <div className="bg-panel border border-gray-800 rounded-lg p-6 text-center h-full flex items-center justify-center">
        <p className="text-muted text-sm">No alerts yet — monitoring...</p>
      </div>
    );
  }

  return (
    <div className="bg-panel border border-gray-800 rounded-lg overflow-hidden flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-800 shrink-0">
        <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">
          Alerts ({detections.length})
        </h3>
      </div>
      <div className="divide-y divide-gray-800 overflow-y-auto flex-1">
        {detections.map((evt, i) => {
          const style = LABEL_STYLES[evt.label || ''] || 'border-gray-700 bg-gray-800/50';
          return (
            <div key={i} className={`px-4 py-3 border-l-2 ${style}`}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-100">{evt.label}</span>
                <span className="text-xs text-muted">
                  {evt.confidence ? `${(evt.confidence * 100).toFixed(0)}%` : ''}
                </span>
              </div>
              <p className="text-xs text-muted mt-0.5 font-mono">
                Frame #{evt.frame_number} — {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : ''}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
