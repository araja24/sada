import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import { formatDuration, useRecorder } from "../hooks/useRecorder";

export default function Record() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const reciterId = Number(params.get("reciter"));
  const startVerse = Number(params.get("start"));
  const endVerse = Number(params.get("end"));

  const [error, setError] = useState<string | null>(null);
  const onError = useCallback((message: string) => setError(message), []);
  const { state, start, stop, reset, markSubmitting, markSubmitFailed } = useRecorder(onError);

  useEffect(() => {
    if (!reciterId || !startVerse || !endVerse) navigate("/reciters", { replace: true });
  }, [reciterId, startVerse, endVerse, navigate]);

  async function submit() {
    if (!state.blob) return;
    setError(null);
    markSubmitting();
    const form = new FormData();
    form.append("reciter_id", String(reciterId));
    form.append("start_verse", String(startVerse));
    form.append("end_verse", String(endVerse));
    form.append("audio", state.blob, "recitation.webm");
    try {
      const attempt = await api.submitAttempt(form);
      navigate(`/results/${attempt.attempt_id}`);
    } catch (err) {
      // Stay here with the take intact (friendly message).
      markSubmitFailed();
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  if (state.status === "submitting") {
    return (
      <section className="step step-centered">
        <div className="spinner" aria-hidden="true" />
        <h2>Listening to your recitation…</h2>
        <p className="muted">This usually takes a few seconds.</p>
      </section>
    );
  }

  return (
    <section className="step" aria-labelledby="record-title">
      <button className="btn btn-quiet back-btn" onClick={() => navigate(-1)}>
        Back
      </button>
      <h2 id="record-title">Record your recitation</h2>
      <div className="recorder">
        <p className="muted">
          {`Recite verses ${startVerse}–${endVerse} in one take, imitating the reciter. Recording stops automatically at 3:00.`}
        </p>
        <div className={`rec-timer${state.status === "recording" ? " live" : ""}`} aria-live="off">
          {formatDuration(state.elapsedSeconds)}
        </div>
        <div className="rec-cap muted">of 3:00 max</div>
        <div className="rec-controls">
          {state.status === "idle" && (
            <button className="btn btn-primary" onClick={() => void start()}>
              ● Start recording
            </button>
          )}
          {state.status === "recording" && (
            <button className="btn btn-quiet" onClick={stop}>
              ■ Stop
            </button>
          )}
          {state.status === "recorded" && (
            <>
              <audio className="rec-preview" controls src={state.objectUrl ?? undefined} />
              <button className="btn btn-quiet" onClick={reset}>
                Re-record
              </button>
              <button className="btn btn-primary" onClick={() => void submit()}>
                Submit for analysis
              </button>
            </>
          )}
        </div>
      </div>
      <ErrorBanner message={error} />
    </section>
  );
}
