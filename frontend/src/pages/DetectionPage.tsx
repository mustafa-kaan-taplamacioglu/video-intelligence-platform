import { useState, useRef, useEffect, type DragEvent, type ChangeEvent } from 'react';
import { analyzeVideo, getStreamUrl, getVideo } from '../api/client';
import type { AnalysisResponse, Video } from '../types';
import DetectionPlayer from '../components/DetectionPlayer';
import DetectionTimeline from '../components/DetectionTimeline';
import DetectionResults from '../components/DetectionResults';
import VideoMetadata from '../components/VideoMetadata';
import ClipCreator from '../components/ClipCreator';
import ClipSaveModal from '../components/ClipSaveModal';
import ClipLibrary from '../components/ClipLibrary';
import { notify, requestNotificationPermission } from '../utils/notifications';

const PRIVACY_NOTICE = `This tool analyzes uploaded videos using pose estimation. No facial recognition or person re-identification is performed.

How your video is handled:
• Your uploaded video is stored on this server so it can be played back, clipped, and re-analyzed. You can delete uploaded videos and any generated clips at any time from the Videos tab.
• The AI classifier consumes only 33 pose landmarks (normalized coordinates, velocities, visibility) — raw pixels never reach the model.
• All processing happens locally on this server. No video, frames, or results are transmitted to any third party.

This prototype is not production-compliant with GDPR, CCPA/CPRA, or KVKK; see LegalandOtherCompliances.md for a full disclosure of current gaps.

By proceeding, you confirm that you have the right to process this video and consent to pose-based activity analysis.`;

export default function DetectionPage() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [video, setVideo] = useState<Video | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [seekTo, setSeekTo] = useState<number | null>(null);
  const [consentGiven, setConsentGiven] = useState(false);
  const [showConsent, setShowConsent] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [clipRefreshKey, setClipRefreshKey] = useState(0);
  const [saveModal, setSaveModal] = useState<{ start: number; end: number } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch full video metadata once analysis completes
  useEffect(() => {
    if (!result?.video_id) {
      setVideo(null);
      return;
    }
    let cancelled = false;
    getVideo(result.video_id)
      .then((v) => { if (!cancelled) setVideo(v); })
      .catch(() => { if (!cancelled) setVideo(null); });
    return () => { cancelled = true; };
  }, [result?.video_id]);

  function validate(file: File): string | null {
    if (!file.name.toLowerCase().endsWith('.mp4')) return 'Only MP4 files are allowed';
    if (file.size > 500 * 1024 * 1024) return 'File too large. Maximum size is 500MB';
    return null;
  }

  function requestConsent(file: File) {
    const err = validate(file);
    if (err) { setError(err); return; }
    if (consentGiven) {
      doAnalyze(file);
    } else {
      setPendingFile(file);
      setShowConsent(true);
    }
  }

  function handleConsentAccept() {
    setConsentGiven(true);
    setShowConsent(false);
    if (pendingFile) {
      doAnalyze(pendingFile);
      setPendingFile(null);
    }
  }

  async function doAnalyze(file: File) {
    setError(null);
    setUploading(true);
    setProgress(0);
    setResult(null);

    // Request notification permission in response to the user's action so
    // they can be notified when the (potentially long) analysis finishes.
    // No-op if already granted or denied.
    void requestNotificationPermission();

    try {
      const res = await analyzeVideo(file, setProgress);
      setResult(res);

      // Notify on completion — suppressed automatically if the tab is
      // currently focused (the UI already transitions to results).
      const count = res.summary.total_detections;
      notify({
        title: '✅ Video analysis complete',
        body: `${count} detection${count !== 1 ? 's' : ''} · Risk: ${res.summary.risk_level}`,
        tag: 'analysis-complete',
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Analysis failed';
      setError(msg);
      notify({
        title: '❌ Analysis failed',
        body: msg,
        tag: 'analysis-failed',
      });
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) requestConsent(file);
  }

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) requestConsent(file);
  }

  function handleSeek(time: number) {
    setSeekTo(time);
    // Reset after a tick so it can be triggered again for the same time
    setTimeout(() => setSeekTo(null), 100);
  }

  function handleCreateClip(start: number, end: number) {
    if (!result) return;
    setSaveModal({ start, end });
  }

  function handleAnalyzeAnother() {
    setResult(null);
    setVideo(null);
    setSaveModal(null);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white mb-1">AI Video Analysis</h1>
        <p className="text-muted text-sm mb-4">
          Upload a video to detect suspicious activities using MediaPipe Pose + LSTM
        </p>
      </div>

      {/* Privacy notice banner */}
      <div className="bg-accent/5 border border-accent/20 rounded-lg px-4 py-3 text-xs text-gray-400">
        <span className="text-accent font-medium">Privacy:</span> Pose-only inference (no facial recognition). Uploaded videos are stored on this server so you can replay and clip them — delete any time. All processing is local. Prototype, not production-compliant — see LegalandOtherCompliances.md.
      </div>

      {/* Upload zone */}
      {!result && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
            ${dragging ? 'border-accent bg-accent/10' : 'border-gray-700 hover:border-gray-500 bg-panel'}`}
        >
          <input ref={inputRef} type="file" accept="video/mp4,.mp4" onChange={onChange} className="hidden" />
          {uploading ? (
            <div className="space-y-3">
              <p className="text-gray-300">Analyzing video...</p>
              <div className="w-full bg-gray-700 rounded-full h-2 max-w-md mx-auto">
                <div className="bg-accent h-2 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
              </div>
              <p className="text-sm text-muted">{progress}% uploaded — processing with AI pipeline</p>
            </div>
          ) : (
            <div className="space-y-2">
              <svg className="w-10 h-10 text-gray-500 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              <p className="text-gray-300">Drop an MP4 file for AI analysis</p>
              <p className="text-xs text-muted">MediaPipe Pose Estimation + LSTM Activity Detection</p>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="bg-danger/10 border border-danger/30 rounded-lg px-4 py-3 text-danger text-sm">{error}</div>
      )}

      {/* Analysis Results */}
      {result && (
        <>
          {/* Summary badges */}
          <div className="flex gap-3 flex-wrap items-center">
            <span className={`px-3 py-1.5 rounded-full text-sm font-medium ${
              result.summary.risk_level === 'HIGH' ? 'bg-danger/20 text-danger' :
              result.summary.risk_level === 'MEDIUM' ? 'bg-warning/20 text-warning' :
              'bg-success/20 text-success'
            }`}>
              Risk: {result.summary.risk_level}
            </span>
            <span className="px-3 py-1.5 rounded-full text-sm font-medium bg-panel border border-gray-700 text-gray-300">
              {result.summary.total_detections} detection{result.summary.total_detections !== 1 ? 's' : ''}
            </span>
            {Object.entries(result.summary.by_class).map(([label, count]) => (
              <span key={label} className="px-3 py-1.5 rounded-full text-sm font-medium bg-panel border border-gray-700 text-gray-300">
                {label}: {count}
              </span>
            ))}
            <span className="px-3 py-1.5 rounded-full text-sm font-mono bg-panel border border-gray-700 text-muted">
              {result.fps_analyzed} fps
            </span>
            <button
              onClick={handleAnalyzeAnother}
              className="ml-auto px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-300 transition-colors"
            >
              Analyze Another
            </button>
          </div>

          {/* Detection Player with pose overlay */}
          <DetectionPlayer
            streamUrl={getStreamUrl(result.video_id)}
            videoId={result.video_id}
            detections={result.detections}
            fps={result.fps_analyzed}
            onTimeUpdate={setCurrentTime}
            seekTo={seekTo}
          />

          {/* Video metadata cards (same style as Videos page) */}
          {video && (
            <VideoMetadata media={{
              duration: video.duration,
              frame_count: video.frame_count,
              width: video.width,
              height: video.height,
              fps: video.fps,
              filesize: video.filesize,
              filename: video.filename,
            }} />
          )}

          {/* Clip tool (download + save) */}
          {video && (
            <ClipCreator
              sourceId={video.id}
              sourceType="video"
              duration={video.duration}
              currentTime={currentTime}
              onSaveClick={(start, end) => setSaveModal({ start, end })}
            />
          )}

          {/* Color-coded detection timeline */}
          <DetectionTimeline
            duration={result.duration}
            detections={result.detections}
            currentTime={currentTime}
            onSeek={handleSeek}
            probabilityCurve={result.probability_curve}
            curveTimestamps={result.curve_timestamps}
          />

          {/* Detection results table */}
          <DetectionResults
            detections={result.detections}
            onJumpTo={handleSeek}
            onCreateClip={handleCreateClip}
          />
        </>
      )}

      <ClipLibrary refreshKey={clipRefreshKey} />

      {/* Clip save modal */}
      {saveModal && video && (
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

      {/* Consent modal */}
      {showConsent && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => { setShowConsent(false); setPendingFile(null); }}>
          <div className="bg-panel border border-gray-700 rounded-xl p-6 w-full max-w-lg space-y-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-medium text-white">Privacy & Consent</h3>
            <p className="text-sm text-gray-300 whitespace-pre-line">{PRIVACY_NOTICE}</p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setShowConsent(false); setPendingFile(null); }}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-gray-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConsentAccept}
                className="px-4 py-2 bg-accent hover:bg-accent/80 rounded text-sm text-white font-medium transition-colors"
              >
                I Understand and Consent
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
