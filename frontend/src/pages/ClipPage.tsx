import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getClip, getClipStreamUrl } from '../api/client';
import type { Clip } from '../types';
import VideoPlayer from '../components/VideoPlayer';
import VideoMetadata from '../components/VideoMetadata';
import ClipCreator from '../components/ClipCreator';
import ClipSaveModal from '../components/ClipSaveModal';
import ClipLibrary from '../components/ClipLibrary';

export default function ClipPage() {
  const { id } = useParams<{ id: string }>();
  const [clip, setClip] = useState<Clip | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [saveModal, setSaveModal] = useState<{ start: number; end: number } | null>(null);
  const [clipRefreshKey, setClipRefreshKey] = useState(0);

  useEffect(() => {
    if (!id) return;
    getClip(id)
      .then(setClip)
      .catch(() => setError('Clip not found'));
  }, [id]);

  if (error) {
    return (
      <div className="text-center py-16">
        <p className="text-danger text-lg">{error}</p>
      </div>
    );
  }

  if (!clip) {
    return <p className="text-muted text-center py-16">Loading...</p>;
  }

  const clipDuration = clip.duration ?? (clip.end_time - clip.start_time);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white truncate" title={clip.name}>
          {clip.name}
        </h1>
        <p className="text-sm text-muted mt-1">
          Clip from{' '}
          <Link to={`/video/${clip.video_id}`} className="text-accent hover:underline">
            {clip.video_filename}
          </Link>
          {clip.source_clip_id && <span className="ml-2">(sub-clip)</span>}
        </p>
      </div>

      <VideoPlayer streamUrl={getClipStreamUrl(clip.id)} onTimeUpdate={setCurrentTime} />

      <VideoMetadata media={{
        duration: clipDuration,
        frame_count: clip.frame_count ?? 0,
        width: clip.width ?? 0,
        height: clip.height ?? 0,
        fps: clip.fps ?? 0,
        filesize: clip.filesize ?? 0,
        filename: clip.name,
      }} />

      <ClipCreator
        sourceId={clip.id}
        sourceType="clip"
        duration={clipDuration}
        currentTime={currentTime}
        onSaveClick={(start, end) => setSaveModal({ start, end })}
      />

      <ClipLibrary refreshKey={clipRefreshKey} />

      {saveModal && (
        <ClipSaveModal
          sourceId={clip.id}
          sourceType="clip"
          sourceName={clip.name}
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
