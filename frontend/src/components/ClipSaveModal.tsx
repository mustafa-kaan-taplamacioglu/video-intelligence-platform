import { useState } from 'react';
import { saveClip, saveSubClip } from '../api/client';

interface Props {
  sourceId: string;
  sourceType: 'video' | 'clip';
  sourceName: string;
  startTime: number;
  endTime: number;
  onClose: () => void;
  onSaved: () => void;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m.toString().padStart(2, '0')}:${s.padStart(4, '0')}`;
}

export default function ClipSaveModal({ sourceId, sourceType, sourceName, startTime, endTime, onClose, onSaved }: Props) {
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      if (sourceType === 'video') {
        await saveClip({
          video_id: sourceId,
          name: name.trim(),
          start_time: startTime,
          end_time: endTime,
        });
      } else {
        await saveSubClip(sourceId, {
          name: name.trim(),
          start_time: startTime,
          end_time: endTime,
        });
      }
      onSaved();
    } catch {
      setError('Failed to save clip');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-panel border border-gray-700 rounded-xl p-6 w-full max-w-md space-y-4" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-medium text-white">
          {sourceType === 'clip' ? 'Save Sub-Clip' : 'Save Clip'}
        </h3>

        <div>
          <label className="text-xs text-muted block mb-1">Clip Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Suspicious activity at entrance"
            autoFocus
            className="w-full bg-surface border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 focus:border-accent focus:outline-none"
          />
        </div>

        <div className="grid grid-cols-3 gap-3 text-sm">
          <div>
            <p className="text-xs text-muted">Source</p>
            <p className="font-mono text-gray-300 truncate" title={sourceName}>{sourceName}</p>
          </div>
          <div>
            <p className="text-xs text-muted">Start</p>
            <p className="font-mono text-gray-300">{formatTime(startTime)}</p>
          </div>
          <div>
            <p className="text-xs text-muted">End</p>
            <p className="font-mono text-gray-300">{formatTime(endTime)}</p>
          </div>
        </div>

        {error && <p className="text-danger text-sm">{error}</p>}

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-gray-300 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim() || saving}
            className="px-4 py-2 bg-accent hover:bg-accent/80 disabled:opacity-40 disabled:cursor-not-allowed rounded text-sm text-white font-medium transition-colors"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
