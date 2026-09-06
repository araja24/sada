import type { Tip } from "../api/types";
import { groupByVerse } from "./resultsHelpers";

interface Props {
  tips: Tip[];
  focusedVerse: number | null;
}

export default function TipsList({ tips, focusedVerse }: Props) {
  const shown = focusedVerse ? tips.filter((t) => t.verse === focusedVerse) : tips;

  return (
    <div className="tips-wrap">
      <h3>{focusedVerse ? `Tips for verse ${focusedVerse}` : "Tips"}</h3>
      {shown.length === 0 ? (
        <p className="muted">
          {focusedVerse
            ? "Nothing stood out for this verse. Nicely done."
            : "Nothing specific stood out across these verses. Keep practicing with the reciter."}
        </p>
      ) : (
        groupByVerse(shown).map((group) => (
          <div className="tip-group" key={group.verse}>
            <h4>Verse {group.verse}</h4>
            <ul className="tip-list">
              {group.tips.map((t, i) => (
                <li className={`tip tip-${t.type}`} key={i}>
                  {t.text}
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </div>
  );
}
