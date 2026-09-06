import type { Attempt } from "../api/types";

export default function OverallScore({ attempt }: { attempt: Attempt }) {
  return (
    <div className="overall">
      <div className="overall-score">
        {attempt.overall_score}
        <span className="overall-outof">/ 100</span>
      </div>
      <div className="overall-label">{attempt.label}</div>
      <p className="muted">
        {attempt.start_verse === attempt.end_verse
          ? `Verse ${attempt.start_verse}`
          : `Verses ${attempt.start_verse}–${attempt.end_verse}`}
      </p>
    </div>
  );
}
