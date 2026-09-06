import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Passage } from "../api/types";
import ErrorBanner from "../components/ErrorBanner";
import ReferencePlayer from "../components/ReferencePlayer";

export default function PassageRoute() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const reciterId = Number(params.get("reciter"));

  const [passage, setPassage] = useState<Passage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startVerse, setStartVerse] = useState<number | null>(null);
  const [endVerse, setEndVerse] = useState<number | null>(null);
  const [pendingStart, setPendingStart] = useState<number | null>(null);
  const [speaking, setSpeaking] = useState<number | null>(null);

  useEffect(() => {
    if (!reciterId) {
      navigate("/reciters", { replace: true });
      return;
    }
    api
      .passage(reciterId)
      .then((p) => {
        setPassage(p);
        setStartVerse(p.verses[0].verse_number);
        setEndVerse(p.verses[p.verses.length - 1].verse_number);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : String(err)));
  }, [reciterId, navigate]);

  // Two-tap range: the first tap collapses the range onto one verse, the
  // second extends it.
  function pickVerse(n: number) {
    if (pendingStart === null) {
      setPendingStart(n);
      setStartVerse(n);
      setEndVerse(n);
    } else {
      setStartVerse(Math.min(pendingStart, n));
      setEndVerse(Math.max(pendingStart, n));
      setPendingStart(null);
    }
  }

  if (!passage || startVerse === null || endVerse === null) {
    return (
      <section className="step">
        <ol className="verse-list">
          <li className="muted">Loading verses…</li>
        </ol>
        <ErrorBanner message={error} />
      </section>
    );
  }

  return (
    <section className="step" aria-labelledby="passage-title">
      <button className="btn btn-quiet back-btn" onClick={() => navigate(-1)}>
        Back
      </button>
      <h2 id="passage-title">Choose your verses</h2>
      <p className="muted">
        Tap a verse to set where you'll start, then tap another to set where you'll
        stop. Default is the whole surah.
      </p>
      <ol className="verse-list" dir="rtl" lang="ar" aria-live="polite">
        {passage.verses.map((v) => {
          const n = v.verse_number;
          const classes = ["verse-row"];
          if (n >= startVerse && n <= endVerse) classes.push("in-range");
          if (n === startVerse || n === endVerse) classes.push("endpoint");
          if (n === speaking) classes.push("speaking");
          return (
            <li
              key={n}
              className={classes.join(" ")}
              role="button"
              tabIndex={0}
              onClick={() => pickVerse(n)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  pickVerse(n);
                }
              }}
            >
              <span className="text">{v.arabic_text || `(verse ${n})`}</span>
              <span className="num">{n}</span>
            </li>
          );
        })}
      </ol>

      <div className="passage-actions">
        <div className="range-readout">
          {startVerse === endVerse
            ? `Verse ${startVerse} selected`
            : `Verses ${startVerse}–${endVerse} selected`}
        </div>
        <ReferencePlayer
          passage={passage}
          startVerse={startVerse}
          endVerse={endVerse}
          onSpeakingVerseChange={setSpeaking}
        />
        <button
          className="btn btn-primary"
          onClick={() =>
            navigate(`/record?reciter=${reciterId}&start=${startVerse}&end=${endVerse}`)
          }
        >
          Continue to recording
        </button>
      </div>
      <ErrorBanner message={error} />
    </section>
  );
}
