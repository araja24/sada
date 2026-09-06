import type { PerVerse } from "../api/types";

interface Props {
  perVerse: PerVerse[];
  focused: number | null;
  onPick: (verse: number) => void;
}

export default function VerseChips({ perVerse, focused, onPick }: Props) {
  return (
    <div className="verse-chips">
      <h3 className="visually-hidden">Per-verse scores</h3>
      {perVerse.map((pv) => (
        <button
          key={pv.verse}
          type="button"
          className={`verse-chip${pv.verse === focused ? " focused" : ""}`}
          aria-label={`Verse ${pv.verse}, score ${pv.score}. Focus its tips.`}
          onClick={() => onPick(pv.verse)}
        >
          <span className="vc-num">V{pv.verse}</span>
          <span className="vc-score">{pv.score}</span>
        </button>
      ))}
    </div>
  );
}
