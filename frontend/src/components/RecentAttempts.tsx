import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { AttemptSummary } from "../api/types";
import { useSession } from "../state/SessionContext";
import { useAuthModal } from "../state/AuthModalContext";

export default function RecentAttempts() {
  const [rows, setRows] = useState<AttemptSummary[]>([]);
  const navigate = useNavigate();
  const { user } = useSession();
  const { openAuth } = useAuthModal();

  useEffect(() => {
    let cancelled = false;
    api
      .recentAttempts()
      .then((r) => {
        if (!cancelled) setRows(r ?? []);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!rows.length) return null;

  return (
    <div className="recent" id="recent-attempts">
      <h2 className="recent-title">{user ? "Your attempts" : "Your recent attempts"}</h2>
      <ul className="recent-list">
        {rows.map((r) => (
          <li key={r.attempt_id}>
            <button
              type="button"
              className="recent-item"
              onClick={() => navigate(`/results/${r.attempt_id}`)}
            >
              <span className="recent-score">{r.overall_score}</span>
              <span className="recent-meta">
                <strong>{r.label}</strong>
                <span className="muted">
                  {" · verses "}
                  {r.start_verse}
                  {"–"}
                  {r.end_verse}
                  {" · "}
                  {new Date(r.created_at).toLocaleDateString()}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {!user && (
        <button type="button" className="btn btn-quiet back-btn" onClick={() => openAuth("signup")}>
          Sign up to keep these
        </button>
      )}
    </div>
  );
}
