import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listClips, downloadClip, deleteClip } from '../api/client';
import type { Clip } from '../types';

interface Props {
  refreshKey: number;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m.toString().padStart(2, '0')}:${s.padStart(4, '0')}`;
}

export default function ClipLibrary({ refreshKey }: Props) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    loadClips();
  }, [refreshKey]);

  async function loadClips() {
    try {
      const data = await listClips();
      setClips(data);
    } finally {
      setLoading(false);
    }
  }

  async function handleDownload(clip: Clip) {
    const blob = await downloadClip(clip.id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${clip.name}.mp4`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleDelete(clip: Clip) {
    if (!confirm(`Delete clip "${clip.name}"?`)) return;
    setDeletingId(clip.id);
    try {
      await deleteClip(clip.id);
      setClips((prev) => prev.filter((c) => c.id !== clip.id));
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) return <p className="text-muted text-sm">Loading clips...</p>;

  if (clips.length === 0) {
    return (
      <div className="bg-panel border border-gray-800 rounded-lg p-6 text-center">
        <p className="text-muted text-sm">No saved clips yet</p>
      </div>
    );
  }

  return (
    <div className="bg-panel border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800">
        <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">Saved Clips</h3>
      </div>
      <div className="divide-y divide-gray-800">
        {clips.map((clip) => (
          <div key={clip.id} className="px-4 py-3 flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-100 font-medium truncate">{clip.name}</p>
              <p className="text-xs text-muted mt-0.5">
                <span className="font-mono">{clip.video_filename}</span>
                <span className="mx-2">|</span>
                <span className="font-mono">{formatTime(clip.start_time)} → {formatTime(clip.end_time)}</span>
                {clip.source_clip_id && <span className="ml-2 text-accent">sub-clip</span>}
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              <Link
                to={`/clip/${clip.id}`}
                className="px-3 py-1.5 bg-success/20 hover:bg-success/30 border border-success/30 rounded text-xs text-success font-medium transition-colors no-underline"
              >
                View
              </Link>
              <button
                onClick={() => handleDownload(clip)}
                className="px-3 py-1.5 bg-accent/20 hover:bg-accent/30 border border-accent/30 rounded text-xs text-accent font-medium transition-colors"
              >
                Download
              </button>
              <button
                onClick={() => handleDelete(clip)}
                disabled={deletingId === clip.id}
                className="px-3 py-1.5 bg-danger/10 hover:bg-danger/20 border border-danger/30 rounded text-xs text-danger font-medium transition-colors disabled:opacity-40"
              >
                {deletingId === clip.id ? '...' : 'Delete'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
