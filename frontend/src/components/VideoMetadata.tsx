import type { MediaInfo } from '../types';

interface Props {
  media: MediaInfo;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m.toString().padStart(2, '0')}:${s.padStart(4, '0')}`;
}

function formatFileSize(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

export default function VideoMetadata({ media }: Props) {
  const metrics = [
    { label: 'Duration', value: formatDuration(media.duration) },
    { label: 'Frames', value: media.frame_count.toLocaleString() },
    { label: 'Resolution', value: `${media.width} × ${media.height}` },
    { label: 'FPS', value: media.fps.toFixed(2) + ' fps' },
    { label: 'File Size', value: formatFileSize(media.filesize) },
    { label: 'Filename', value: media.filename },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {metrics.map((m) => (
        <div key={m.label} className="bg-panel border border-gray-800 rounded-lg p-3">
          <p className="text-xs text-muted uppercase tracking-wider">{m.label}</p>
          <p className="text-sm font-mono text-gray-100 mt-1 truncate" title={m.value}>{m.value}</p>
        </div>
      ))}
    </div>
  );
}
