import { useState, useRef, type DragEvent, type ChangeEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadVideo } from '../api/client';

const MAX_SIZE = 500 * 1024 * 1024;

export default function VideoUploader() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  function validate(file: File): string | null {
    if (!file.name.toLowerCase().endsWith('.mp4')) return 'Only MP4 files are allowed';
    if (file.type !== 'video/mp4') return 'Only video/mp4 MIME type is allowed';
    if (file.size > MAX_SIZE) return 'File too large. Maximum size is 500MB';
    return null;
  }

  async function handleFile(file: File) {
    const err = validate(file);
    if (err) { setError(err); return; }

    setError(null);
    setUploading(true);
    setProgress(0);

    try {
      const video = await uploadVideo(file, setProgress);
      navigate(`/video/${video.id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Upload failed';
      setError(msg);
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all
          ${dragging ? 'border-accent bg-accent/10' : 'border-gray-700 hover:border-gray-500 bg-panel'}`}
      >
        <input ref={inputRef} type="file" accept="video/mp4,.mp4" onChange={onChange} className="hidden" />

        {uploading ? (
          <div className="space-y-3">
            <p className="text-gray-300">Uploading...</p>
            <div className="w-full bg-gray-700 rounded-full h-2 max-w-md mx-auto">
              <div
                className="bg-accent h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-sm text-muted">{progress}%</p>
          </div>
        ) : (
          <div className="space-y-2">
            <svg className="w-12 h-12 text-gray-500 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-gray-300">Drag & drop an MP4 file here, or click to select</p>
            <p className="text-xs text-muted">MP4 only — Max 500MB</p>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-danger/10 border border-danger/30 rounded-lg px-4 py-3 text-danger text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
