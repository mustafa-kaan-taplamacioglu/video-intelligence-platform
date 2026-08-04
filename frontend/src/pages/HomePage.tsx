import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import VideoUploader from '../components/VideoUploader';
import { listVideos } from '../api/client';
import type { Video } from '../types';

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function HomePage() {
  const [videos, setVideos] = useState<Video[]>([]);

  useEffect(() => {
    listVideos().then(setVideos);
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white mb-1">Upload Video</h1>
        <p className="text-muted text-sm mb-4">Upload an MP4 file to analyze and create clips</p>
        <VideoUploader />
      </div>

      {videos.length > 0 && (
        <div>
          <h2 className="text-lg font-medium text-white mb-3">Uploaded Videos</h2>
          <div className="grid gap-3">
            {videos.map((v) => (
              <Link
                key={v.id}
                to={`/video/${v.id}`}
                className="flex items-center gap-4 bg-panel border border-gray-800 rounded-lg p-4 hover:border-gray-600 transition-colors no-underline"
              >
                <div className="w-10 h-10 bg-accent/20 rounded-lg flex items-center justify-center shrink-0">
                  <svg viewBox="0 0 24 24" className="w-5 h-5 text-accent" fill="currentColor">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-100 font-medium truncate">{v.filename}</p>
                  <p className="text-xs text-muted mt-0.5 font-mono">
                    {v.width}×{v.height} · {formatDuration(v.duration)} · {v.fps.toFixed(0)} fps
                  </p>
                </div>
                <span className="text-xs text-muted shrink-0">
                  {(v.filesize / (1024 * 1024)).toFixed(1)} MB
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
