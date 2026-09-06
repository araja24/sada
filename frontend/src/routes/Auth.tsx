import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FormEvent } from "react";
import { api, ApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import { useSession } from "../state/SessionContext";

export default function Auth({ mode }: { mode: "signup" | "login" }) {
  const navigate = useNavigate();
  const { refresh } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isSignup = mode === "signup";

  // React Router tracks its position in the history stack on history.state.idx.
  // idx 0 means this is the first entry, so there is nothing to go back to.
  function leaveAuth() {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (idx > 0) navigate(-1);
    else navigate("/", { replace: true });
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const call = isSignup ? api.signup : api.login;
      await call(email.trim(), password);
      await refresh();
      leaveAuth();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="step" aria-labelledby="auth-title">
      <button className="btn btn-quiet back-btn" onClick={leaveAuth}>
        Back
      </button>
      <h2 id="auth-title">{isSignup ? "Save your attempts" : "Welcome back"}</h2>
      {isSignup && (
        <p className="muted" id="auth-intro">
          Create an account (or log in) to keep your recitation history across
          devices. Any attempts you've already made in this browser will move to
          your account.
        </p>
      )}
      <form onSubmit={onSubmit} noValidate id="auth-form">
        <div className="field">
          <label htmlFor="auth-email">Email</label>
          <input
            type="email"
            id="auth-email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="auth-password">
            Password <span className="muted">(at least 8 characters)</span>
          </label>
          <input
            type="password"
            id="auth-password"
            autoComplete={isSignup ? "new-password" : "current-password"}
            minLength={8}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {isSignup ? "Sign up" : "Log in"}
        </button>
        <button
          className="btn btn-quiet"
          id="auth-toggle"
          type="button"
          onClick={() => navigate(isSignup ? "/login" : "/signup", { replace: true })}
        >
          {isSignup ? "I already have an account" : "I need to create an account"}
        </button>
      </form>
      <ErrorBanner message={error} />
    </section>
  );
}
