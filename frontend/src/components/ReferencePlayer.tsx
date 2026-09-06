import { useEffect, useRef, useState } from "react";
import type { Passage } from "../api/types";

interface Props {
  passage: Passage;
  startVerse: number;
  endVerse: number;
  onSpeakingVerseChange: (verse: number | null) => void;
}

export default function ReferencePlayer({
  passage,
  startVerse,
  endVerse,
  onSpeakingVerseChange,
}: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);

  const inRange = passage.verses.filter(
    (v) => v.verse_number >= startVerse && v.verse_number <= endVerse,
  );

  // Seek to the range start whenever the selection changes, so "Listen" plays
  // the chosen verses rather than always starting from verse 1.
  useEffect(() => {
    const audio = audioRef.current;
    const first = inRange[0];
    if (audio && first) audio.currentTime = first.start_ms / 1000;
  }, [startVerse, endVerse]);

  // Stop playback and clear the highlight when the component unmounts.
  useEffect(() => {
    return () => onSpeakingVerseChange(null);
  }, [onSpeakingVerseChange]);

  function onTimeUpdate() {
    const audio = audioRef.current;
    if (!audio) return;
    const ms = audio.currentTime * 1000;
    let active: number | null = null;
    for (const v of inRange) {
      if (ms >= v.start_ms && ms <= v.end_ms) active = v.verse_number;
    }
    onSpeakingVerseChange(active);
    const last = inRange[inRange.length - 1];
    if (last && ms > last.end_ms + 400) audio.pause();
  }

  return (
    <div className="ref-player">
      <button
        className="btn btn-quiet"
        aria-pressed={playing}
        onClick={() => {
          const audio = audioRef.current;
          if (!audio) return;
          if (audio.paused) void audio.play();
          else audio.pause();
        }}
      >
        {playing ? "⏸ Pause" : "▶ Listen to the reciter"}
      </button>
      <audio
        ref={audioRef}
        preload="none"
        src={passage.reference_audio_url}
        onPlay={() => setPlaying(true)}
        onPause={() => {
          setPlaying(false);
          onSpeakingVerseChange(null);
        }}
        onEnded={() => onSpeakingVerseChange(null)}
        onTimeUpdate={onTimeUpdate}
      />
    </div>
  );
}
