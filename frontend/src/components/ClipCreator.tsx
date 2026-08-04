import { useState } from 'react';
import { generateClip } from '../api/client';

interface Props {
  sourceId: string;
  sourceType: 'video' | 'clip';
  duration: number;
  currentTime: number;
  onSaveClick: (start: number, end: number) => void;
}

function parseTime(val: string): number | null {
  const parts = val.split(':').map(Number);
  if (parts.some(isNaN)) return null;
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return null;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m.toString().padStart(2, '0')}:${s.padStart(4, '0')}`;
}

export default function ClipCreator({ sourceId, sourceType, duration, currentTime, onSaveClick }: Props) {
  const [startStr, setStartStr] = useState('0');
  const [endStr, setEndStr] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = parseTime(startStr);
  const end = parseTime(endStr);
  const valid = start !== null && end !== null && start < end && start >= 0 && end <= duration;

  const startPct = start !== null ? (start / duration) * 100 : 0;
  const endPct = end !== null ? (end / duration) * 100 : 0;

  async function handleGenerate() {
    if (!valid || start === null || end === null) return;
    setError(null);
    setLoading(true);
    try {
      // For videos, use the dedicated clip endpoint. For clips, save as subclip then trigger download.
      if (sourceType === 'video') {
        const blob = await generateClip(sourceId, start, end);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `clip_${start.toFixed(1)}-${end.toFixed(1)}.mp4`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        // For clips, use the save flow (subclip endpoint returns metadata, not blob)
        // Just trigger save modal instead
        onSaveClick(start, end);
        setLoading(false);
        return;
      }
    } catch {
      setError('Failed to generate clip');
    } finally {
      setLoading(false);
    }
  }

  function handleSave() {
    if (!valid || start === null || end === null) return;
    onSaveClick(start, end);
  }

  return (
    <div className="bg-panel border border-gray-800 rounded-lg p-4 space-y-4">
      <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">Clip Tool</h3>

      <div className="relative h-2 bg-gray-700 rounded-full">
        {valid && (
          <div
            className="absolute h-full bg-accent/40 rounded-full"
            style={{ left: `${startPct}%`, width: `${endPct - startPct}%` }}
          />
        )}
        <div
          className="absolute h-full w-0.5 bg-warning"
          style={{ left: `${(currentTime / duration) * 100}%` }}
        />
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-[120px]">
          <label className="text-xs text-muted block mb-1">Start Time</label>
          <div className="flex gap-1">
            <input
              type="text"
              value={startStr}
              onChange={(e) => setStartStr(e.target.value)}
              placeholder="0:00"
              className="w-full bg-surface border border-gray-700 rounded px-3 py-2 text-sm font-mono text-gray-100 focus:border-accent focus:outline-none"
            />
            <button
              onClick={() => setStartStr(formatTime(currentTime))}
              className="px-2 py-2 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-300 whitespace-nowrap"
              title="Set to current time"
            >
              Now
            </button>
          </div>
        </div>

        <div className="flex-1 min-w-[120px]">
          <label className="text-xs text-muted block mb-1">End Time</label>
          <div className="flex gap-1">
            <input
              type="text"
              value={endStr}
              onChange={(e) => setEndStr(e.target.value)}
              placeholder="0:00"
              className="w-full bg-surface border border-gray-700 rounded px-3 py-2 text-sm font-mono text-gray-100 focus:border-accent focus:outline-none"
            />
            <button
              onClick={() => setEndStr(formatTime(currentTime))}
              className="px-2 py-2 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-300 whitespace-nowrap"
              title="Set to current time"
            >
              Now
            </button>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleGenerate}
            disabled={!valid || loading}
            className="px-4 py-2 bg-accent hover:bg-accent/80 disabled:opacity-40 disabled:cursor-not-allowed rounded text-sm text-white font-medium transition-colors"
          >
            {loading ? 'Generating...' : 'Download Clip'}
          </button>
          <button
            onClick={handleSave}
            disabled={!valid || loading}
            className="px-4 py-2 bg-success/20 hover:bg-success/30 border border-success/40 disabled:opacity-40 disabled:cursor-not-allowed rounded text-sm text-success font-medium transition-colors"
          >
            Save Clip
          </button>
        </div>
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}
    </div>
  );
}
