import type { Attempt } from "../api/types";
import { clampPercent } from "./resultsHelpers";

const SUB_LABELS: Record<string, string> = {
  melody: "Melody",
  pacing: "Pacing",
  tone: "Tone similarity",
  elongation: "Elongation timing",
};

const SUB_HINT: Record<string, string> = {
  melody: "How closely your pitch movement follows the reciter's.",
  pacing: "How evenly your tempo matches, verse to verse.",
  tone: "How close your vocal timbre is. Every voice is different.",
  elongation: "How your held (madd) syllables line up in length.",
};

export default function SubScoreGrid({ attempt }: { attempt: Attempt }) {
  return (
    <div className="subscore-grid">
      {Object.keys(SUB_LABELS)
        .filter((key) => key in attempt.sub_scores)
        .map((key) => (
          <div className="subscore-card" key={key}>
            <div className="subscore-name">{SUB_LABELS[key]}</div>
            <div className="subscore-val">{attempt.sub_scores[key]}</div>
            <div className="subscore-meter">
              <span style={{ width: `${clampPercent(attempt.sub_scores[key])}%` }} />
            </div>
            <p className="subscore-hint muted">{SUB_HINT[key]}</p>
          </div>
        ))}
    </div>
  );
}
