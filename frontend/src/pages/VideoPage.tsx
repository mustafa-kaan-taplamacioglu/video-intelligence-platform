import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getVideo, getStreamUrl } from '../api/client';
import type { Video } from '../types';
import VideoPlayer from '../components/VideoPlayer';
import VideoMetadata from '../components/VideoMetadata';
import ClipCreator from '../components/ClipCreator';
import ClipSaveModal from '../components/ClipSaveModal';
import ClipLibrary from '../components/ClipLibrary';

export default function VideoPage() {
  const { id } = useParams<{ id: string }>();
  const [video, setVideo] = useState<Video | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [saveModal, setSaveModal] = useState<{ start: number; end: number } | null>(null);
  const [clipRefreshKey, setClipRefreshKey] = useState(0);

  useEffect(() => {
    if (!id) return;
    getVideo(id)
      .then(setVideo)
      .catch(() => setError('Video not found'));
  }, [id]);

  if (error) {
    return (
      <div className="text-center py-16">
        <p className="text-danger text-lg">{error}</p>
      </div>
    );
  }

  if (!video) {
    return <p className="text-muted text-center py-16">Loading...</p>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white truncate" title={video.filename}>
        {video.filename}
      </h1>

      <VideoPlayer streamUrl={getStreamUrl(video.id)} onTimeUpdate={setCurrentTime} />

      <VideoMetadata media={{
        duration: video.duration,
        frame_count: video.frame_count,
        width: video.width,
        height: video.height,
        fps: video.fps,
        filesize: video.filesize,
        filename: video.filename,
      }} />

      <ClipCreator
        sourceId={video.id}
        sourceType="video"
        duration={video.duration}
        currentTime={currentTime}
        onSaveClick={(start, end) => setSaveModal({ start, end })}
      />

      <ClipLibrary refreshKey={clipRefreshKey} />

      {saveModal && (
        <ClipSaveModal
          sourceId={video.id}
          sourceType="video"
          sourceName={video.filename}
          startTime={saveModal.start}
          endTime={saveModal.end}
          onClose={() => setSaveModal(null)}
          onSaved={() => {
            setSaveModal(null);
            setClipRefreshKey((k) => k + 1);
          }}
        />
      )}
    </div>
  );
}
