import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Attempt, Passage } from "../api/types";
import ErrorBanner from "../components/ErrorBanner";
import OverallScore from "../components/OverallScore";
import PitchChart from "../components/PitchChart";
import SubScoreGrid from "../components/SubScoreGrid";
import TipsList from "../components/TipsList";
import VerseChips from "../components/VerseChips";
import { useSession } from "../state/SessionContext";

export default function Results() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const navigate = useNavigate();
  const { user } = useSession();

  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [passage, setPassage] = useState<Passage | null>(null);
  const [reciterName, setReciterName] = useState("the reciter");
  const [focused, setFocused] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!attemptId) return;
    let cancelled = false;
    (async () => {
      try {
        const a = await api.attempt(attemptId);
        if (cancelled) return;
        setAttempt(a);
        const [p, reciters] = await Promise.all([api.passage(a.reciter_id), api.reciters()]);
        if (cancelled) return;
        setPassage(p);
        const match = reciters.find((r) => r.id === a.reciter_id);
        if (match) setReciterName(match.name);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [attemptId]);

  if (error) {
    return (
      <section className="step">
        <ErrorBanner message={error} />
      </section>
    );
  }

  if (!attempt) {
    return (
      <section className="step step-centered">
        <div className="spinner" aria-hidden="true" />
        <h2>Loading your results…</h2>
      </section>
    );
  }

  return (
    <section className="step" aria-labelledby="results-title">
      <h2 id="results-title" className="visually-hidden">
        Your results
      </h2>
      <OverallScore attempt={attempt} />
      <SubScoreGrid attempt={attempt} />
      <VerseChips
        perVerse={attempt.per_verse}
        focused={focused}
        onPick={(v) => setFocused((cur) => (cur === v ? null : v))}
      />
      <PitchChart
        attempt={attempt}
        passage={passage}
        focusedVerse={focused}
        reciterName={reciterName}
      />
      <TipsList tips={attempt.tips} focusedVerse={focused} />
      <div className="results-actions">
        <button
          className="btn btn-primary"
          onClick={() =>
            navigate(
              `/record?reciter=${attempt.reciter_id}&start=${attempt.start_verse}&end=${attempt.end_verse}`,
            )
          }
        >
          Try again
        </button>
        {!user && (
          <button className="btn btn-quiet" onClick={() => navigate("/signup")}>
            Save your attempts
          </button>
        )}
      </div>
    </section>
  );
}
