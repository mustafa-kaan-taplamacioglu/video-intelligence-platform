import { useEffect, useRef } from 'react';
import videojs from 'video.js';
import type Player from 'video.js/dist/types/player';

interface Props {
  streamUrl: string;
  onTimeUpdate?: (time: number) => void;
}

export default function VideoPlayer({ streamUrl, onTimeUpdate }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<Player | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const videoEl = document.createElement('video-js');
    videoEl.classList.add('vjs-big-play-centered');
    containerRef.current.appendChild(videoEl);

    const player = videojs(videoEl, {
      controls: true,
      responsive: true,
      fluid: true,
      sources: [{ src: streamUrl, type: 'video/mp4' }],
    });

    if (onTimeUpdate) {
      player.on('timeupdate', () => {
        onTimeUpdate(player.currentTime() ?? 0);
      });
    }

    playerRef.current = player;

    return () => {
      if (playerRef.current) {
        playerRef.current.dispose();
        playerRef.current = null;
      }
    };
  }, [streamUrl]);

  return <div ref={containerRef} className="rounded-lg overflow-hidden" />;
}
