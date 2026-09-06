import { useEffect, useRef } from "react";
import type { Attempt, Passage } from "../api/types";

interface Props {
  attempt: Attempt;
  passage: Passage | null;
  focusedVerse: number | null;
  reciterName: string;
}

interface Boundary {
  verse: number;
  t: number;
  label: string;
}

function verseBoundaries(attempt: Attempt, passage: Passage | null): Boundary[] {
  if (!passage) return [];
  const inRange = passage.verses.filter(
    (v) => v.verse_number >= attempt.start_verse && v.verse_number <= attempt.end_verse,
  );
  if (!inRange.length) return [];
  const startMs = inRange[0].start_ms;
  const endMs = inRange[inRange.length - 1].end_ms;
  const span = endMs - startMs || 1;
  return inRange.map((v) => ({
    verse: v.verse_number,
    t: Math.max(0, Math.min(1, (v.start_ms - startMs) / span)),
    label: `V${v.verse_number}`,
  }));
}

function drawLine(
  ctx: CanvasRenderingContext2D,
  xs: number[],
  ys: number[],
  x: (t: number) => number,
  y: (s: number) => number,
  color: string,
  width: number,
) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineJoin = "round";
  ctx.beginPath();
  let started = false;
  for (let i = 0; i < xs.length; i++) {
    if (!isFinite(ys[i])) {
      started = false;
      continue;
    }
    const px = x(xs[i]);
    const py = y(ys[i]);
    if (!started) {
      ctx.moveTo(px, py);
      started = true;
    } else {
      ctx.lineTo(px, py);
    }
  }
  ctx.stroke();
}

export default function PitchChart({ attempt, passage, focusedVerse, reciterName }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function draw() {
      const c = canvasRef.current;
      if (!c) return;
      const ctx = c.getContext("2d");
      if (!ctx) return;
      const overlay = attempt.pitch_overlay;
      const cssW = c.clientWidth || 600;
      const cssH = 260;
      const dpr = window.devicePixelRatio || 1;
      c.width = cssW * dpr;
      c.height = cssH * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, cssW, cssH);

      const pad = { l: 14, r: 14, t: 14, b: 22 };
      const plotW = cssW - pad.l - pad.r;
      const plotH = cssH - pad.t - pad.b;

      const all = overlay.reference_semitones
        .concat(overlay.user_semitones_aligned)
        .filter((v) => isFinite(v));
      let lo = Math.min(...all);
      let hi = Math.max(...all);
      if (!isFinite(lo) || lo === hi) {
        lo = -6;
        hi = 6;
      }
      const range = hi - lo || 1;
      lo -= range * 0.12;
      hi += range * 0.12;

      const x = (t: number) => pad.l + t * plotW;
      const y = (semi: number) => pad.t + (1 - (semi - lo) / (hi - lo)) * plotH;

      const bounds = verseBoundaries(attempt, passage);
      ctx.strokeStyle = "#e7e1d8";
      ctx.fillStyle = "#9a9186";
      ctx.font = "11px Inter, sans-serif";
      ctx.lineWidth = 1;
      for (const b of bounds) {
        ctx.beginPath();
        ctx.moveTo(x(b.t), pad.t);
        ctx.lineTo(x(b.t), pad.t + plotH);
        ctx.stroke();
        if (b.label) ctx.fillText(b.label, x(b.t) + 3, pad.t + 11);
      }

      if (focusedVerse) {
        const seg = bounds.find((b) => b.verse === focusedVerse);
        const next = bounds.find((b) => b.verse === focusedVerse + 1);
        const x0 = seg ? x(seg.t) : pad.l;
        const x1 = next ? x(next.t) : pad.l + plotW;
        ctx.fillStyle = "rgba(63,111,94,0.08)";
        ctx.fillRect(x0, pad.t, x1 - x0, plotH);
      }

      drawLine(ctx, overlay.time_axis, overlay.reference_semitones, x, y, "#3f6f5e", 2);
      drawLine(ctx, overlay.time_axis, overlay.user_semitones_aligned, x, y, "#c1873b", 2);
    }

    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [attempt, passage, focusedVerse]);

  return (
    <figure className="chart-wrap">
      <canvas
        ref={canvasRef}
        className="pitch-chart"
        role="img"
        aria-label={`Pitch contour: your recitation compared to ${reciterName}'s, on a shared time axis.`}
      />
      <figcaption className="muted">
        <span className="key key-ref" /> {reciterName} &nbsp; <span className="key key-you" /> You
      </figcaption>
    </figure>
  );
}
