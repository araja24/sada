import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Reciter } from "../api/types";
import ErrorBanner from "../components/ErrorBanner";

export default function Reciters() {
  const navigate = useNavigate();
  const [reciters, setReciters] = useState<Reciter[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .reciters()
      .then(setReciters)
      .catch((err) => setError(err instanceof ApiError ? err.message : String(err)));
  }, []);

  return (
    <section className="step" aria-labelledby="reciter-title">
      <button className="btn btn-quiet back-btn" onClick={() => navigate(-1)}>
        Back
      </button>
      <h2 id="reciter-title">Choose a reciter to echo</h2>
      <p className="muted">Your recitation will be compared to this reciter's recorded Al-Fatiha.</p>
      <div className="card-grid" aria-live="polite">
        {reciters === null && <p className="muted">Loading reciters…</p>}
        {reciters?.length === 0 && (
          <p className="muted">
            No reciter reference data has been built yet. Run <code>scripts/build_reference.py</code> to add one.
          </p>
        )}
        {reciters?.map((r) => (
          <button
            key={r.id}
            type="button"
            className="reciter-card"
            onClick={() => navigate(`/verses?reciter=${r.id}`)}
          >
            <h3>{r.name}</h3>
            <p>{r.description || ""}</p>
          </button>
        ))}
      </div>
      <ErrorBanner message={error} />
    </section>
  );
}
