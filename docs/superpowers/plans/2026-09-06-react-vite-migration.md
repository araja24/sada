# React + Vite Frontend Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Sada's four hand-written vanilla frontend files with a TypeScript React single-page app built by Vite, served by the same FastAPI process, with no visual change.

**Architecture:** `frontend/` becomes the Vite project root. Wizard steps become real react-router URLs whose state lives in the URL, so every route survives a refresh. FastAPI serves the committed `frontend/dist` build with an SPA catch-all fallback. The stylesheet and every CSS class name carry across unchanged, so the port is pixel-identical.

**Tech Stack:** Vite 8.2.2, React 19.2.8, react-router-dom 7.18.3, TypeScript 7.0.2, Vitest 5.0.0, @vitejs/plugin-react 6.1.1. Backend unchanged: FastAPI, SQLAlchemy, SQLite.

**Spec:** [`docs/superpowers/specs/2026-09-06-react-vite-migration-design.md`](../specs/2026-09-06-react-vite-migration-design.md)

## Global Constraints

Every task's requirements implicitly include this section.

- **No em dashes** (`—`) anywhere: user-facing copy, comments, commit messages. Use commas, periods or parentheses. En dashes (`–`) in numeric verse ranges such as `Verses 1–7` are correct and must be preserved.
- **No arrow glyphs** (`←`, `->`) in button labels. The back buttons read exactly `Back`. Glyphs `▶ ⏸ ● ■` in the player and recorder are kept.
- **Preserve every CSS class name and DOM structure** from the current markup. `src/styles.css` is moved unchanged and must not be edited in any task except where a task explicitly says so. If a component needs a style that does not exist, that is a signal the markup drifted.
- **All API calls use `credentials: "same-origin"`.** Auth is a same-origin HttpOnly cookie (ADR-0002); do not add tokens, headers or CORS.
- **TypeScript strict mode on.** No `any` in committed code.
- **`frontend/dist/` is committed to git.** It is deliberately not gitignored. `frontend/node_modules/` is gitignored.
- **Run every command from `frontend/`** for npm, and from the repo root for pytest.
- Python interpreter is `./.venv/Scripts/python.exe` (Windows, no system python).
- The reference audio lives under `/api/reciters/{slug}/audio`, so a single `/api` dev-proxy rule covers everything.

## File Structure

| File | Responsibility |
|---|---|
| `frontend/package.json`, `vite.config.ts`, `tsconfig*.json` | Build, dev proxy, test config |
| `frontend/index.html` | Vite entry document |
| `frontend/public/favicon.svg` | Moved from `frontend/favicon.svg` |
| `frontend/src/main.tsx` | Mount point, imports the stylesheet |
| `frontend/src/App.tsx` | Layout shell and route table |
| `frontend/src/styles.css` | Moved unchanged from `frontend/css/styles.css` |
| `frontend/src/api/types.ts` | Mirrors `app/schemas.py` |
| `frontend/src/api/client.ts` | Single `request()` chokepoint, `ApiError`, friendly messages |
| `frontend/src/state/SessionContext.tsx` | Signed-in user, the only global state |
| `frontend/src/hooks/useRecorder.ts` | MediaRecorder lifecycle + pure `recorderReducer` |
| `frontend/src/components/*.tsx` | Navbar, Footer, ErrorBanner, RecentAttempts, ReferencePlayer, Recorder, PitchChart, OverallScore, SubScoreGrid, VerseChips, TipsList |
| `frontend/src/routes/*.tsx` | Welcome, Auth, Reciters, Passage, Record, Results |
| `app/settings.py` | `FRONTEND_DIR` default moves to `frontend/dist` |
| `app/main.py` | `_mount_frontend` gains the SPA catch-all |
| `tests/test_api.py` | Static-serving tests rewritten for hashed asset names |

Deleted in Task 11: `frontend/js/`, `frontend/css/`, `frontend/favicon.svg`.

---

### Task 1: Vite scaffold, backend serving, SPA fallback

Sets up the build and switches FastAPI to serve `dist`. Ends with a working (if nearly empty) React app on `/` and green pytest.

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`
- Move: `frontend/css/styles.css` -> `frontend/src/styles.css`; `frontend/favicon.svg` -> `frontend/public/favicon.svg`
- Modify: `frontend/index.html` (replace wholesale), `.gitignore`, `app/settings.py:52`, `app/main.py:65-72`
- Test: `tests/test_api.py:302-310`

**Interfaces:**
- Consumes: nothing.
- Produces: a buildable Vite project; `npm run build` writes `frontend/dist`. `App` is the default export of `src/App.tsx`. FastAPI serves `dist` with an SPA fallback.

- [ ] **Step 1: Write the failing backend tests**

Replace `tests/test_api.py:302-310` (`test_static_frontend_is_served`) with:

```python
def test_static_frontend_is_served(client):
    root = client.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers["content-type"]


def test_spa_deep_link_falls_back_to_index(client):
    """react-router owns /results/:id; the server must return the shell, not 404."""
    resp = client.get("/results/abc123")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_unknown_api_path_404s_as_json_not_spa(client):
    """The catch-all must never swallow /api/*, or client errors become HTML."""
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert "application/json" in resp.headers["content-type"]


def test_docs_not_shadowed_by_spa(client):
    assert "text/html" in client.get("/docs").headers["content-type"]
    assert client.get("/openapi.json").json()["info"]["title"] == "Sada"


def test_favicon_is_served(client):
    resp = client.get("/favicon.svg")
    assert resp.status_code == 200


def test_spa_fallback_rejects_path_traversal(client):
    resp = client.get("/../../app/settings.py")
    assert resp.status_code in (200, 404)
    assert "SESSION_SECRET_KEY" not in resp.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k "spa or static or favicon" -v`

Expected: FAIL. `/results/abc123` returns 404 because `StaticFiles(html=True)` does not fall back.

- [ ] **Step 3: Scaffold the Vite project**

Create `frontend/package.json`:

```json
{
  "name": "sada-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "react-router-dom": "7.18.3"
  },
  "devDependencies": {
    "@types/react": "19.2.8",
    "@types/react-dom": "19.2.8",
    "@vitejs/plugin-react": "6.1.1",
    "typescript": "7.0.2",
    "vite": "8.2.2",
    "vitest": "5.0.0"
  }
}
```

If `@types/react` 19.2.8 does not exist on npm, use the latest 19.x that does. If TypeScript 7.0.2 errors out with the React template, pin `typescript` to the latest 5.x; the spec permits this and nothing else changes.

Create `frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API and the reference audio both live under /api, so one proxy rule
// covers dev. Build output is committed, so outDir stays inside frontend/.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "noEmit": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Move the stylesheet and favicon, write the entry files**

```bash
cd frontend
mkdir -p src public
git mv css/styles.css src/styles.css
git mv favicon.svg public/favicon.svg
```

Replace `frontend/index.html` entirely with:

```html
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Sada: recitation style coach</title>
  <meta name="description" content="Match the style of your Quran recitation (melody, pacing, tone, elongation) to a professional reciter's." />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

const container = document.getElementById("root");
if (!container) throw new Error("Missing #root element");

createRoot(container).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

Create `frontend/src/App.tsx` as a placeholder that Task 3 replaces:

```tsx
export default function App() {
  return <main id="app">Sada</main>;
}
```

- [ ] **Step 5: Install and build**

Run:
```bash
cd frontend && npm install && npm run build
```
Expected: `frontend/dist/index.html` and `frontend/dist/assets/*.js` exist.

- [ ] **Step 6: Point the backend at dist and add the SPA fallback**

In `app/settings.py:52`, change the default:

```python
FRONTEND_DIR = Path(os.environ.get("SADA_FRONTEND_DIR", REPO_ROOT / "frontend" / "dist"))
```

Replace `_mount_frontend` in `app/main.py:65-72` with:

```python
def _mount_frontend(app: FastAPI) -> None:
    """Serve the built Vite SPA.

    StaticFiles(html=True) 404s on client-side routes like /results/abc123,
    so the hashed assets get a real mount and everything else falls through
    to index.html. Registered last so it never shadows /api/* or /docs.
    """
    index = settings.FRONTEND_DIR / "index.html"
    if not index.exists():
        return
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    assets = settings.FRONTEND_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    root = settings.FRONTEND_DIR.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        # An unknown /api/* path must 404 as JSON, not as the SPA shell.
        if full_path.startswith("api/") or full_path in {"docs", "redoc", "openapi.json"}:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (settings.FRONTEND_DIR / full_path).resolve()
        if full_path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)
```

Add `HTTPException` to the fastapi import at `app/main.py:12`:

```python
from fastapi import FastAPI, HTTPException
```

- [ ] **Step 7: Run the full test suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, 150 tests (146 unchanged + the 6 new static tests replacing 1).

- [ ] **Step 8: Update .gitignore**

Append to `.gitignore`:

```
# Node / Vite. dist/ is deliberately NOT ignored: Render's python runtime has
# no Node, so the build output is committed (see ADR-0003).
frontend/node_modules/
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "Scaffold Vite + React frontend and serve it from FastAPI

Adds the Vite/TypeScript project in frontend/, moves the stylesheet and
favicon into it, and switches FRONTEND_DIR to frontend/dist.

_mount_frontend now serves hashed assets from /assets and falls back to
index.html for client-side routes, while still 404ing unknown /api paths
as JSON and refusing path traversal.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: API types and client

**Files:**
- Create: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class ApiError extends Error { status: number; body: unknown }`
  - `messageFromBody(body: unknown, status: number): string` (exported for tests)
  - `api.reciters(): Promise<Reciter[]>`, `api.passage(reciterId: number): Promise<Passage>`, `api.submitAttempt(form: FormData): Promise<Attempt>`, `api.attempt(id: string): Promise<Attempt>`, `api.recentAttempts(): Promise<AttemptSummary[]>`, `api.me(): Promise<User | null>`, `api.signup(email: string, password: string): Promise<User>`, `api.login(email: string, password: string): Promise<User>`, `api.logout(): Promise<null>`
  - Types `Reciter`, `Word`, `PassageVerse`, `Passage`, `PitchOverlay`, `Tip`, `PerVerse`, `Attempt`, `AttemptSummary`, `User`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/api/client.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { messageFromBody } from "./client";

describe("messageFromBody", () => {
  it("prefers a string detail from the API", () => {
    expect(messageFromBody({ detail: "That email is already registered." }, 400))
      .toBe("That email is already registered.");
  });

  it("unwraps FastAPI validation arrays", () => {
    const body = { detail: [{ msg: "Enter a valid email address." }] };
    expect(messageFromBody(body, 422)).toBe("Enter a valid email address.");
  });

  it("explains an oversized upload", () => {
    expect(messageFromBody(null, 413)).toBe("That recording is too large. Try a shorter take.");
  });

  it("uses a calm message for server errors", () => {
    expect(messageFromBody(null, 500))
      .toBe("Something went wrong on our end. Please try again in a moment.");
  });

  it("falls back for anything else", () => {
    expect(messageFromBody(null, 418)).toBe("That didn't work. Please try again.");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL, cannot resolve `./client`.

- [ ] **Step 3: Write the types**

Create `frontend/src/api/types.ts`:

```ts
/* Mirrors app/schemas.py. Keep the two in sync by hand. */

export interface Reciter {
  id: number;
  slug: string;
  name: string;
  description: string;
}

export interface Word {
  word_index: number;
  arabic_text: string;
  start_ms: number;
  end_ms: number;
}

export interface PassageVerse {
  verse_number: number;
  verse_key: string;
  arabic_text: string;
  words: Word[];
  start_ms: number;
  end_ms: number;
}

export interface Passage {
  reciter_slug: string;
  surah: string;
  reference_audio_url: string;
  verses: PassageVerse[];
}

export interface PitchOverlay {
  time_axis: number[];
  reference_semitones: number[];
  user_semitones_aligned: number[];
}

export interface Tip {
  verse: number;
  word_index: number | null;
  type: string;
  text: string;
}

export interface PerVerse {
  verse: number;
  score: number;
}

export interface Attempt {
  attempt_id: string;
  reciter_id: number;
  start_verse: number;
  end_verse: number;
  overall_score: number;
  label: string;
  sub_scores: Record<string, number>;
  per_verse: PerVerse[];
  pitch_overlay: PitchOverlay;
  tips: Tip[];
  created_at: string;
}

export interface AttemptSummary {
  attempt_id: string;
  reciter_id: number;
  reciter_slug: string;
  start_verse: number;
  end_verse: number;
  overall_score: number;
  label: string;
  created_at: string;
}

export interface User {
  id: number;
  email: string;
}
```

- [ ] **Step 4: Write the client**

Create `frontend/src/api/client.ts`:

```ts
/* Thin fetch wrappers around the Sada API (PRD §6). Every call goes through
   request() so error handling and the friendly-message extraction live in
   one place. */
import type { Attempt, AttemptSummary, Passage, Reciter, User } from "./types";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function messageFromBody(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0] && typeof detail[0].msg === "string") {
      return detail[0].msg;
    }
  }
  if (status === 413) return "That recording is too large. Try a shorter take.";
  if (status >= 500) return "Something went wrong on our end. Please try again in a moment.";
  return "That didn't work. Please try again.";
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(path, { credentials: "same-origin", ...options });
  } catch {
    throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0);
  }
  const isJson = (resp.headers.get("content-type") || "").includes("application/json");
  const body = isJson ? await resp.json().catch(() => null) : null;
  if (!resp.ok) throw new ApiError(messageFromBody(body, resp.status), resp.status, body);
  return body as T;
}

function jsonBody(obj: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(obj),
  };
}

export const api = {
  reciters: () => request<Reciter[]>("/api/reciters"),
  passage: (reciterId: number) =>
    request<Passage>(`/api/passages/fatiha?reciter_id=${encodeURIComponent(reciterId)}`),
  submitAttempt: (form: FormData) =>
    request<Attempt>("/api/attempts", { method: "POST", body: form }),
  attempt: (id: string) => request<Attempt>(`/api/attempts/${encodeURIComponent(id)}`),
  recentAttempts: () => request<AttemptSummary[]>("/api/attempts"),
  me: () => request<User | null>("/api/auth/me"),
  signup: (email: string, password: string) =>
    request<User>("/api/auth/signup", jsonBody({ email, password })),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", jsonBody({ email, password })),
  logout: () => request<null>("/api/auth/logout", { method: "POST" }),
};
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npm test && npm run typecheck`
Expected: PASS, 5 tests.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api
git commit -m "Port the API client and add types mirroring app/schemas.py

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: App shell, session state, navbar

**Files:**
- Create: `frontend/src/state/SessionContext.tsx`, `frontend/src/components/Navbar.tsx`, `frontend/src/components/Footer.tsx`, `frontend/src/components/ErrorBanner.tsx`
- Modify: `frontend/src/App.tsx` (replace the placeholder)

**Interfaces:**
- Consumes: `api` from Task 2.
- Produces:
  - `SessionProvider` component, `useSession(): { user: User | null; loading: boolean; refresh(): Promise<void>; logout(): Promise<void> }`
  - `<ErrorBanner message={string | null} />`
  - Routes `/`, `/login`, `/signup`, `/reciters`, `/verses`, `/record`, `/results/:attemptId` rendering placeholder components that later tasks replace.

- [ ] **Step 1: Write the session context**

Create `frontend/src/state/SessionContext.tsx`:

```tsx
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { User } from "../api/types";

interface SessionValue {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me && me.email ? me : null);
    } catch {
      // The nav is optional chrome; a failed lookup just means signed out.
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    await refresh();
  }, [refresh]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <SessionContext.Provider value={{ user, loading, refresh, logout }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
```

- [ ] **Step 2: Write the navbar, footer and error banner**

Create `frontend/src/components/Navbar.tsx`. This preserves the sticky navbar markup exactly, including the `Practice` and `My attempts` behaviour:

```tsx
import { useNavigate } from "react-router-dom";
import { useSession } from "../state/SessionContext";

export default function Navbar() {
  const navigate = useNavigate();
  const { user, loading, logout } = useSession();

  function goToAttempts() {
    navigate("/");
    // The recent list lives on the welcome route; give it a frame to render.
    requestAnimationFrame(() => {
      const box = document.getElementById("recent-attempts");
      if (box) box.scrollIntoView({ behavior: "smooth", block: "start" });
      else if (!user) navigate("/login");
    });
  }

  return (
    <nav className="navbar" aria-label="Primary">
      <div className="navbar-inner">
        <a
          className="wordmark"
          href="/"
          aria-label="Sada home"
          onClick={(e) => {
            e.preventDefault();
            navigate("/");
          }}
        >
          صدى<span>Sada</span>
        </a>
        <div className="navbar-links">
          <button type="button" className="navlink" onClick={() => navigate("/reciters")}>
            Practice
          </button>
          <button type="button" className="navlink" onClick={goToAttempts}>
            My attempts
          </button>
          <span className="account-nav" hidden={loading}>
            {user ? (
              <>
                <span className="muted">{user.email}</span>
                <button type="button" className="btn btn-quiet back-btn" onClick={() => void logout()}>
                  Log out
                </button>
              </>
            ) : (
              <>
                <button type="button" className="btn btn-quiet back-btn" onClick={() => navigate("/login")}>
                  Log in
                </button>
                <button type="button" className="btn btn-quiet back-btn" onClick={() => navigate("/signup")}>
                  Sign up
                </button>
              </>
            )}
          </span>
        </div>
      </div>
    </nav>
  );
}
```

Create `frontend/src/components/Footer.tsx`:

```tsx
export default function Footer() {
  return (
    <footer className="site-footer">
      <p id="privacy-note">
        As a guest, Sada stores only your recitation attempts, keyed to a random
        ID in a cookie, with no account and no personal data. If you sign up, we also
        store your email and a one-way hash of your password so your attempt
        history follows you across devices. We never share any of it.
      </p>
    </footer>
  );
}
```

Create `frontend/src/components/ErrorBanner.tsx`:

```tsx
import { useEffect, useRef } from "react";

export default function ErrorBanner({ message }: { message: string | null }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (message && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [message]);

  if (!message) return null;
  return (
    <div className="error-banner" role="alert" ref={ref}>
      {message}
    </div>
  );
}
```

- [ ] **Step 3: Write the app shell and route table**

Replace `frontend/src/App.tsx`:

```tsx
import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import { SessionProvider } from "./state/SessionContext";

function Placeholder({ name }: { name: string }) {
  return <section className="step">{name}</section>;
}

export default function App() {
  return (
    <SessionProvider>
      <Navbar />
      <main id="app">
        <Routes>
          <Route path="/" element={<Placeholder name="Welcome" />} />
          <Route path="/login" element={<Placeholder name="Log in" />} />
          <Route path="/signup" element={<Placeholder name="Sign up" />} />
          <Route path="/reciters" element={<Placeholder name="Reciters" />} />
          <Route path="/verses" element={<Placeholder name="Verses" />} />
          <Route path="/record" element={<Placeholder name="Record" />} />
          <Route path="/results/:attemptId" element={<Placeholder name="Results" />} />
        </Routes>
      </main>
      <Footer />
    </SessionProvider>
  );
}
```

- [ ] **Step 4: Verify it builds and renders**

Run: `cd frontend && npm run build`
Expected: PASS.

Then run the app and confirm the navbar renders and is sticky:
```bash
cd .. && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```
Open `http://localhost:8000/`. Expected: the sticky navbar with wordmark, `Practice`, `My attempts`, and `Log in` / `Sign up`. Clicking `Practice` changes the URL to `/reciters` and shows the placeholder. Refreshing `/reciters` still works (proves the SPA fallback).

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "Add the app shell: session context, navbar, footer, routes

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Welcome route and recent attempts

**Files:**
- Create: `frontend/src/routes/Welcome.tsx`, `frontend/src/components/RecentAttempts.tsx`
- Modify: `frontend/src/App.tsx` (swap the `/` placeholder)

**Interfaces:**
- Consumes: `api`, `useSession`, `AttemptSummary`.
- Produces: `<Welcome />` at `/`, `<RecentAttempts />` rendering `#recent-attempts`.

- [ ] **Step 1: Write RecentAttempts**

Create `frontend/src/components/RecentAttempts.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { AttemptSummary } from "../api/types";
import { useSession } from "../state/SessionContext";

export default function RecentAttempts() {
  const [rows, setRows] = useState<AttemptSummary[]>([]);
  const navigate = useNavigate();
  const { user } = useSession();

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
        <button type="button" className="btn btn-quiet back-btn" onClick={() => navigate("/signup")}>
          Sign up to keep these
        </button>
      )}
    </div>
  );
}
```

Note `–` is the en dash in the verse range, which the Global Constraints require keeping.

- [ ] **Step 2: Write the Welcome route**

Create `frontend/src/routes/Welcome.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import RecentAttempts from "../components/RecentAttempts";

export default function Welcome() {
  const navigate = useNavigate();
  return (
    <section className="step" aria-labelledby="welcome-title">
      <h1 id="welcome-title">Echo a reciter's style</h1>
      <p className="lede">
        Sada listens to how you recite Surah Al-Fatiha and compares the{" "}
        <em>style</em> of your delivery (melody, pacing, tone, and elongation
        timing) to a professional reciter you choose. It is a practice companion,
        not a correctness or tajweed checker.
      </p>
      <button className="btn btn-primary" onClick={() => navigate("/reciters")}>
        Start practicing
      </button>
      <RecentAttempts />
    </section>
  );
}
```

- [ ] **Step 3: Wire it into App.tsx**

In `frontend/src/App.tsx`, add `import Welcome from "./routes/Welcome";` and change the `/` route to `element={<Welcome />}`.

- [ ] **Step 4: Verify**

Run: `cd frontend && npm run build`
Expected: PASS.

With uvicorn running, open `/`. Expected: the hero copy and `Start practicing`. If you have prior attempts, the recent list renders and clicking one navigates to `/results/<id>` (the placeholder, until Task 9).

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "Port the welcome route and the recent-attempts list

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Auth route

**Files:**
- Create: `frontend/src/routes/Auth.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api`, `useSession`, `ErrorBanner`.
- Produces: `<Auth mode="signup" | "login" />` rendered at `/signup` and `/login`.

- [ ] **Step 1: Write the Auth route**

Create `frontend/src/routes/Auth.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
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

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const call = isSignup ? api.signup : api.login;
      await call(email.trim(), password);
      await refresh();
      navigate(-1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="step" aria-labelledby="auth-title">
      <button className="btn btn-quiet back-btn" onClick={() => navigate(-1)}>
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
      <form onSubmit={onSubmit} noValidate>
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
```

The form keeps the `#auth-form` styling by way of its `.field` and `.btn` children; if the form-width rule `#auth-form { max-width: 22rem }` is lost, add `id="auth-form"` to the `<form>` element. Check this visually in Step 3.

- [ ] **Step 2: Wire into App.tsx**

Add `import Auth from "./routes/Auth";` and set:
```tsx
<Route path="/login" element={<Auth mode="login" />} />
<Route path="/signup" element={<Auth mode="signup" />} />
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: PASS.

In the browser: `/signup` shows the intro paragraph and a 22rem-wide form. Confirm the form is not full width; if it is, add `id="auth-form"` as noted. Sign up with a new email, confirm the navbar switches to your email plus `Log out`. Submit a bad password (under 8 characters via devtools) and confirm the friendly error appears in the banner.

- [ ] **Step 4: Commit**

```bash
git add frontend/src
git commit -m "Port the sign up and log in routes

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Reciters and passage routes

**Files:**
- Create: `frontend/src/routes/Reciters.tsx`, `frontend/src/routes/Passage.tsx`, `frontend/src/components/ReferencePlayer.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api`, `Reciter`, `Passage` types, `ErrorBanner`.
- Produces: `<Reciters />` at `/reciters`; `<PassageRoute />` at `/verses?reciter=<id>`; `<ReferencePlayer passage={Passage} startVerse={number} endVerse={number} />`.

- [ ] **Step 1: Write the Reciters route**

Create `frontend/src/routes/Reciters.tsx`:

```tsx
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
```

- [ ] **Step 2: Write the ReferencePlayer**

Create `frontend/src/components/ReferencePlayer.tsx`. This ports the play/pause toggle, the speaking-verse highlight, and the auto-stop past the range end:

```tsx
import { useEffect, useRef, useState } from "react";
import type { Passage } from "../api/types";

interface Props {
  passage: Passage;
  startVerse: number;
  endVerse: number;
  onSpeakingVerseChange: (verse: number | null) => void;
}

export default function ReferencePlayer({
  passage,
  startVerse,
  endVerse,
  onSpeakingVerseChange,
}: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);

  const inRange = passage.verses.filter(
    (v) => v.verse_number >= startVerse && v.verse_number <= endVerse,
  );

  // Seek to the range start whenever the selection changes, so "Listen" plays
  // the chosen verses rather than always starting from verse 1.
  useEffect(() => {
    const audio = audioRef.current;
    const first = inRange[0];
    if (audio && first) audio.currentTime = first.start_ms / 1000;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startVerse, endVerse]);

  // Stop playback and clear the highlight when the component unmounts.
  useEffect(() => {
    return () => onSpeakingVerseChange(null);
  }, [onSpeakingVerseChange]);

  function onTimeUpdate() {
    const audio = audioRef.current;
    if (!audio) return;
    const ms = audio.currentTime * 1000;
    let active: number | null = null;
    for (const v of inRange) {
      if (ms >= v.start_ms && ms <= v.end_ms) active = v.verse_number;
    }
    onSpeakingVerseChange(active);
    const last = inRange[inRange.length - 1];
    if (last && ms > last.end_ms + 400) audio.pause();
  }

  return (
    <div className="ref-player">
      <button
        className="btn btn-quiet"
        aria-pressed={playing}
        onClick={() => {
          const audio = audioRef.current;
          if (!audio) return;
          if (audio.paused) void audio.play();
          else audio.pause();
        }}
      >
        {playing ? "⏸ Pause" : "▶ Listen to the reciter"}
      </button>
      <audio
        ref={audioRef}
        preload="none"
        src={passage.reference_audio_url}
        onPlay={() => setPlaying(true)}
        onPause={() => {
          setPlaying(false);
          onSpeakingVerseChange(null);
        }}
        onEnded={() => onSpeakingVerseChange(null)}
        onTimeUpdate={onTimeUpdate}
      />
    </div>
  );
}
```

- [ ] **Step 3: Write the Passage route**

Create `frontend/src/routes/Passage.tsx`. This ports the two-tap range selection:

```tsx
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
```

- [ ] **Step 4: Wire into App.tsx**

Add the imports and set `/reciters` to `<Reciters />` and `/verses` to `<PassageRoute />`.

- [ ] **Step 5: Verify**

Run: `cd frontend && npm run build`
Expected: PASS.

In the browser: `/reciters` lists the reciter card. Clicking it goes to `/verses?reciter=1` with all 7 verses selected and the readout reading `Verses 1–7 selected`. Tap verse 2, then verse 5, and confirm the readout reads `Verses 2–5 selected` and the highlight matches. Press `▶ Listen to the reciter` and confirm playback starts at verse 2, highlights each verse as it speaks, and stops after verse 5. Refresh the page and confirm it still loads.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "Port the reciter and verse-range routes with the reference player

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: The recorder state machine

Pure logic, TDD. The DOM-touching wrapper comes in Task 8.

**Files:**
- Create: `frontend/src/hooks/useRecorder.ts`
- Test: `frontend/src/hooks/useRecorder.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `type RecorderStatus = "idle" | "recording" | "recorded" | "submitting"`
  - `interface RecorderState { status: RecorderStatus; elapsedSeconds: number; blob: Blob | null; objectUrl: string | null }`
  - `type RecorderAction = { type: "start" } | { type: "tick"; seconds: number } | { type: "stop"; blob: Blob; objectUrl: string } | { type: "reset" } | { type: "submit" } | { type: "submitFailed" }`
  - `const initialRecorderState: RecorderState`
  - `function recorderReducer(state: RecorderState, action: RecorderAction): RecorderState`
  - `const CAP_SECONDS = 180`
  - `function formatDuration(totalSeconds: number): string`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/hooks/useRecorder.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  CAP_SECONDS,
  formatDuration,
  initialRecorderState,
  recorderReducer,
} from "./useRecorder";

describe("formatDuration", () => {
  it("pads seconds", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(9)).toBe("0:09");
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(180)).toBe("3:00");
  });

  it("never goes negative", () => {
    expect(formatDuration(-5)).toBe("0:00");
  });
});

describe("recorderReducer", () => {
  it("starts from idle", () => {
    expect(initialRecorderState.status).toBe("idle");
    const s = recorderReducer(initialRecorderState, { type: "start" });
    expect(s.status).toBe("recording");
    expect(s.elapsedSeconds).toBe(0);
  });

  it("accumulates elapsed time while recording", () => {
    let s = recorderReducer(initialRecorderState, { type: "start" });
    s = recorderReducer(s, { type: "tick", seconds: 12.4 });
    expect(s.elapsedSeconds).toBeCloseTo(12.4);
  });

  it("ignores ticks when not recording", () => {
    const s = recorderReducer(initialRecorderState, { type: "tick", seconds: 5 });
    expect(s.elapsedSeconds).toBe(0);
  });

  it("moves to recorded and keeps the blob", () => {
    const blob = new Blob(["x"], { type: "audio/webm" });
    let s = recorderReducer(initialRecorderState, { type: "start" });
    s = recorderReducer(s, { type: "stop", blob, objectUrl: "blob:1" });
    expect(s.status).toBe("recorded");
    expect(s.blob).toBe(blob);
    expect(s.objectUrl).toBe("blob:1");
  });

  it("reset clears the take and returns to idle", () => {
    const blob = new Blob(["x"]);
    let s = recorderReducer(initialRecorderState, { type: "start" });
    s = recorderReducer(s, { type: "stop", blob, objectUrl: "blob:1" });
    s = recorderReducer(s, { type: "reset" });
    expect(s).toEqual(initialRecorderState);
  });

  it("submit keeps the take so a failure can recover it", () => {
    const blob = new Blob(["x"]);
    let s = recorderReducer(initialRecorderState, { type: "start" });
    s = recorderReducer(s, { type: "stop", blob, objectUrl: "blob:1" });
    s = recorderReducer(s, { type: "submit" });
    expect(s.status).toBe("submitting");
    expect(s.blob).toBe(blob);
    s = recorderReducer(s, { type: "submitFailed" });
    expect(s.status).toBe("recorded");
    expect(s.blob).toBe(blob);
  });

  it("caps at three minutes", () => {
    expect(CAP_SECONDS).toBe(180);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL, cannot resolve `./useRecorder`.

- [ ] **Step 3: Write the reducer and the hook**

Create `frontend/src/hooks/useRecorder.ts`:

```ts
/* Recording step (PRD §4 steps 5-6): mic capture with a live timer and a
   visible 3:00 cap, playback + re-record, then submit.

   The state machine is a pure reducer so it can be tested without a DOM or a
   MediaRecorder. useRecorder wires it to the real browser APIs and owns
   teardown of the stream, interval and object URL. */
import { useCallback, useEffect, useReducer, useRef } from "react";

export const CAP_SECONDS = 180; // PRD: hard 3:00 cap

export type RecorderStatus = "idle" | "recording" | "recorded" | "submitting";

export interface RecorderState {
  status: RecorderStatus;
  elapsedSeconds: number;
  blob: Blob | null;
  objectUrl: string | null;
}

export type RecorderAction =
  | { type: "start" }
  | { type: "tick"; seconds: number }
  | { type: "stop"; blob: Blob; objectUrl: string }
  | { type: "reset" }
  | { type: "submit" }
  | { type: "submitFailed" };

export const initialRecorderState: RecorderState = {
  status: "idle",
  elapsedSeconds: 0,
  blob: null,
  objectUrl: null,
};

export function recorderReducer(state: RecorderState, action: RecorderAction): RecorderState {
  switch (action.type) {
    case "start":
      return { ...initialRecorderState, status: "recording" };
    case "tick":
      return state.status === "recording"
        ? { ...state, elapsedSeconds: action.seconds }
        : state;
    case "stop":
      return {
        ...state,
        status: "recorded",
        blob: action.blob,
        objectUrl: action.objectUrl,
      };
    case "reset":
      return initialRecorderState;
    case "submit":
      return { ...state, status: "submitting" };
    case "submitFailed":
      return { ...state, status: "recorded" };
    default:
      return state;
  }
}

export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function useRecorder(onError: (message: string) => void) {
  const [state, dispatch] = useReducer(recorderReducer, initialRecorderState);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const intervalRef = useRef<number | null>(null);
  const startedAtRef = useRef(0);
  const objectUrlRef = useRef<string | null>(null);

  const releaseAll = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  // Release the mic, timer and object URL even if the user navigates away
  // mid-recording.
  useEffect(() => releaseAll, [releaseAll]);

  const stop = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const start = useCallback(async () => {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      onError("This browser can't record audio. Try a recent Chrome, Firefox, or Safari.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError("We need microphone access to record. Enable it in your browser settings and try again.");
      return;
    }
    streamRef.current = stream;
    chunksRef.current = [];
    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;

    recorder.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size) chunksRef.current.push(e.data);
    });
    recorder.addEventListener("stop", () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      const type = recorder.mimeType || "audio/webm";
      const blob = new Blob(chunksRef.current, { type });
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      dispatch({ type: "stop", blob, objectUrl: url });
    });

    recorder.start();
    startedAtRef.current = Date.now();
    dispatch({ type: "start" });
    intervalRef.current = window.setInterval(() => {
      const secs = (Date.now() - startedAtRef.current) / 1000;
      dispatch({ type: "tick", seconds: secs });
      if (secs >= CAP_SECONDS) stop();
    }, 200);
  }, [onError, stop]);

  const reset = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    chunksRef.current = [];
    dispatch({ type: "reset" });
  }, []);

  return {
    state,
    start,
    stop,
    reset,
    markSubmitting: () => dispatch({ type: "submit" }),
    markSubmitFailed: () => dispatch({ type: "submitFailed" }),
  };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test && npm run typecheck`
Expected: PASS, 13 tests total (5 from Task 2 plus 8 here).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks
git commit -m "Add the recorder state machine with a tested pure reducer

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Record route

**Files:**
- Create: `frontend/src/routes/Record.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `useRecorder`, `formatDuration`, `api.submitAttempt`, `ErrorBanner`.
- Produces: `<Record />` at `/record?reciter=<id>&start=<n>&end=<n>`. Navigates to `/results/:attemptId` on success.

- [ ] **Step 1: Write the Record route**

Create `frontend/src/routes/Record.tsx`:

```tsx
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
      // Stay here with the take intact (§5.10 friendly message).
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
```

The original intro named the reciter. That required carrying the reciter object through the flow; since the route is now URL-driven, the copy says "the reciter" instead. If you prefer the name, fetch `/api/reciters` here and look up `reciterId`.

- [ ] **Step 2: Wire into App.tsx**

Add `import Record from "./routes/Record";` and set `/record` to `<Record />`.

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: PASS.

In the browser, go through `/reciters` to `/verses` to `/record`. Grant mic access, record a few seconds, stop, confirm the preview plays and the timer froze at the elapsed time. Press `Re-record` and confirm the timer resets to `0:00`. Record again and press `Submit for analysis`; confirm the spinner appears and you land on `/results/<id>`.

Then verify teardown: start a recording and press `Back` mid-recording. Confirm the browser's microphone indicator turns off (this is the leak the old code did not handle).

- [ ] **Step 4: Commit**

```bash
git add frontend/src
git commit -m "Port the recording route with mic teardown on unmount

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: Results route and its presentational parts

**Files:**
- Create: `frontend/src/routes/Results.tsx`, `frontend/src/components/OverallScore.tsx`, `frontend/src/components/SubScoreGrid.tsx`, `frontend/src/components/VerseChips.tsx`, `frontend/src/components/TipsList.tsx`, `frontend/src/components/resultsHelpers.ts`
- Test: `frontend/src/components/resultsHelpers.test.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api`, `Attempt`, `Passage`, `Tip`, `PerVerse`.
- Produces:
  - `groupByVerse(tips: Tip[]): { verse: number; tips: Tip[] }[]`, `clampPercent(n: number): number`
  - `<OverallScore attempt={Attempt} />`, `<SubScoreGrid attempt={Attempt} />`, `<VerseChips perVerse={PerVerse[]} focused={number | null} onPick={(v: number) => void} />`, `<TipsList tips={Tip[]} focusedVerse={number | null} />`
  - `<Results />` at `/results/:attemptId`
- Task 10 adds `<PitchChart />` into `Results.tsx`.

- [ ] **Step 1: Write the failing helper test**

Create `frontend/src/components/resultsHelpers.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { clampPercent, groupByVerse } from "./resultsHelpers";
import type { Tip } from "../api/types";

function tip(verse: number, text: string): Tip {
  return { verse, word_index: null, type: "melody", text };
}

describe("groupByVerse", () => {
  it("groups tips and orders verses numerically", () => {
    const groups = groupByVerse([tip(3, "c"), tip(1, "a"), tip(3, "d"), tip(2, "b")]);
    expect(groups.map((g) => g.verse)).toEqual([1, 2, 3]);
    expect(groups[2].tips.map((t) => t.text)).toEqual(["c", "d"]);
  });

  it("returns nothing for no tips", () => {
    expect(groupByVerse([])).toEqual([]);
  });

  it("orders 2 before 10 rather than lexically", () => {
    expect(groupByVerse([tip(10, "x"), tip(2, "y")]).map((g) => g.verse)).toEqual([2, 10]);
  });
});

describe("clampPercent", () => {
  it("clamps to 0..100", () => {
    expect(clampPercent(-5)).toBe(0);
    expect(clampPercent(42)).toBe(42);
    expect(clampPercent(140)).toBe(100);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL, cannot resolve `./resultsHelpers`.

- [ ] **Step 3: Write the helpers**

Create `frontend/src/components/resultsHelpers.ts`:

```ts
import type { Tip } from "../api/types";

export interface VerseGroup {
  verse: number;
  tips: Tip[];
}

export function groupByVerse(tips: Tip[]): VerseGroup[] {
  const byVerse = new Map<number, Tip[]>();
  for (const t of tips) {
    const existing = byVerse.get(t.verse);
    if (existing) existing.push(t);
    else byVerse.set(t.verse, [t]);
  }
  return [...byVerse.keys()]
    .sort((a, b) => a - b)
    .map((verse) => ({ verse, tips: byVerse.get(verse) as Tip[] }));
}

export function clampPercent(n: number): number {
  return Math.max(0, Math.min(100, n));
}
```

- [ ] **Step 4: Run to verify the helper tests pass**

Run: `cd frontend && npm test`
Expected: PASS, 17 tests total.

- [ ] **Step 5: Write the presentational components**

Create `frontend/src/components/OverallScore.tsx`:

```tsx
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
```

Create `frontend/src/components/SubScoreGrid.tsx`:

```tsx
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
```

Create `frontend/src/components/VerseChips.tsx`:

```tsx
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
```

Create `frontend/src/components/TipsList.tsx`:

```tsx
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
```

- [ ] **Step 6: Write the Results route**

Create `frontend/src/routes/Results.tsx`. It rehydrates from the attempt id alone, which is what makes the results URL shareable:

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Attempt, Passage } from "../api/types";
import ErrorBanner from "../components/ErrorBanner";
import OverallScore from "../components/OverallScore";
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
      {/* Task 10 inserts <PitchChart /> here, above the tips. */}
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
```

`passage` is unused until Task 10 adds the chart. If `noUnusedLocals` rejects it, keep the state and reference it in a `void passage;` statement with a comment, or add the chart in the same session.

- [ ] **Step 7: Wire into App.tsx and verify**

Add `import Results from "./routes/Results";` and set `/results/:attemptId` to `<Results />`.

Run: `cd frontend && npm test && npm run build`
Expected: PASS.

In the browser, complete a recording and confirm: the score, label and verse range render; four sub-score cards with filled meters; verse chips that toggle focus and filter the tips; `Try again` returns to `/record` with the same verses. Copy the `/results/<id>` URL into a new tab and confirm it loads standalone.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "Port the results route with tested grouping helpers

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: Pitch chart

**Files:**
- Create: `frontend/src/components/PitchChart.tsx`
- Modify: `frontend/src/routes/Results.tsx`

**Interfaces:**
- Consumes: `Attempt`, `Passage`.
- Produces: `<PitchChart attempt={Attempt} passage={Passage | null} focusedVerse={number | null} reciterName={string} />`

- [ ] **Step 1: Write the component**

Create `frontend/src/components/PitchChart.tsx`. The drawing code is ported verbatim from `frontend/js/results.js`; only the lifecycle changes:

```tsx
import { useEffect, useRef } from "react";
import type { Attempt, Passage } from "../api/types";

interface Props {
  attempt: Attempt;
  passage: Passage | null;
  focusedVerse: number | null;
  reciterName: string;
}

interface Boundary {
  verse: number;
  t: number;
  label: string;
}

function verseBoundaries(attempt: Attempt, passage: Passage | null): Boundary[] {
  if (!passage) return [];
  const inRange = passage.verses.filter(
    (v) => v.verse_number >= attempt.start_verse && v.verse_number <= attempt.end_verse,
  );
  if (!inRange.length) return [];
  const startMs = inRange[0].start_ms;
  const endMs = inRange[inRange.length - 1].end_ms;
  const span = endMs - startMs || 1;
  return inRange.map((v) => ({
    verse: v.verse_number,
    t: Math.max(0, Math.min(1, (v.start_ms - startMs) / span)),
    label: `V${v.verse_number}`,
  }));
}

function drawLine(
  ctx: CanvasRenderingContext2D,
  xs: number[],
  ys: number[],
  x: (t: number) => number,
  y: (s: number) => number,
  color: string,
  width: number,
) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineJoin = "round";
  ctx.beginPath();
  let started = false;
  for (let i = 0; i < xs.length; i++) {
    if (!isFinite(ys[i])) {
      started = false;
      continue;
    }
    const px = x(xs[i]);
    const py = y(ys[i]);
    if (!started) {
      ctx.moveTo(px, py);
      started = true;
    } else {
      ctx.lineTo(px, py);
    }
  }
  ctx.stroke();
}

export default function PitchChart({ attempt, passage, focusedVerse, reciterName }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function draw() {
      const c = canvasRef.current;
      if (!c) return;
      const ctx = c.getContext("2d");
      if (!ctx) return;
      const overlay = attempt.pitch_overlay;
      const cssW = c.clientWidth || 600;
      const cssH = 260;
      const dpr = window.devicePixelRatio || 1;
      c.width = cssW * dpr;
      c.height = cssH * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, cssW, cssH);

      const pad = { l: 14, r: 14, t: 14, b: 22 };
      const plotW = cssW - pad.l - pad.r;
      const plotH = cssH - pad.t - pad.b;

      const all = overlay.reference_semitones
        .concat(overlay.user_semitones_aligned)
        .filter((v) => isFinite(v));
      let lo = Math.min(...all);
      let hi = Math.max(...all);
      if (!isFinite(lo) || lo === hi) {
        lo = -6;
        hi = 6;
      }
      const range = hi - lo || 1;
      lo -= range * 0.12;
      hi += range * 0.12;

      const x = (t: number) => pad.l + t * plotW;
      const y = (semi: number) => pad.t + (1 - (semi - lo) / (hi - lo)) * plotH;

      const bounds = verseBoundaries(attempt, passage);
      ctx.strokeStyle = "#e7e1d8";
      ctx.fillStyle = "#9a9186";
      ctx.font = "11px Inter, sans-serif";
      ctx.lineWidth = 1;
      for (const b of bounds) {
        ctx.beginPath();
        ctx.moveTo(x(b.t), pad.t);
        ctx.lineTo(x(b.t), pad.t + plotH);
        ctx.stroke();
        if (b.label) ctx.fillText(b.label, x(b.t) + 3, pad.t + 11);
      }

      if (focusedVerse) {
        const seg = bounds.find((b) => b.verse === focusedVerse);
        const next = bounds.find((b) => b.verse === focusedVerse + 1);
        const x0 = seg ? x(seg.t) : pad.l;
        const x1 = next ? x(next.t) : pad.l + plotW;
        ctx.fillStyle = "rgba(63,111,94,0.08)";
        ctx.fillRect(x0, pad.t, x1 - x0, plotH);
      }

      drawLine(ctx, overlay.time_axis, overlay.reference_semitones, x, y, "#3f6f5e", 2);
      drawLine(ctx, overlay.time_axis, overlay.user_semitones_aligned, x, y, "#c1873b", 2);
    }

    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [attempt, passage, focusedVerse]);

  return (
    <figure className="chart-wrap">
      <canvas
        ref={canvasRef}
        className="pitch-chart"
        role="img"
        aria-label={`Pitch contour: your recitation compared to ${reciterName}'s, on a shared time axis.`}
      />
      <figcaption className="muted">
        <span className="key key-ref" /> {reciterName} &nbsp; <span className="key key-you" /> You
      </figcaption>
    </figure>
  );
}
```

- [ ] **Step 2: Insert it into Results.tsx**

Add `import PitchChart from "../components/PitchChart";` and replace the placeholder comment between `<VerseChips />` and `<TipsList />` with:

```tsx
<PitchChart
  attempt={attempt}
  passage={passage}
  focusedVerse={focused}
  reciterName={reciterName}
/>
```

This also resolves the unused-`passage` note from Task 9.

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: PASS.

In the browser, open a results page. Confirm: two contour lines (green for the reciter, amber for you), grey verse boundary lines labelled `V1`, `V2` and so on, the caption key, and that clicking a verse chip shades that verse's band on the chart. Resize the window and confirm the chart redraws crisply rather than stretching.

- [ ] **Step 4: Commit**

```bash
git add frontend/src
git commit -m "Port the canvas pitch chart with a ResizeObserver redraw

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 11: Remove the vanilla app, document, ship the build

**Files:**
- Delete: `frontend/js/api.js`, `frontend/js/app.js`, `frontend/js/record.js`, `frontend/js/results.js`, and the now-empty `frontend/js/` and `frontend/css/`
- Create: `docs/adr/0003-react-frontend.md`
- Modify: `README.md`
- Build: `frontend/dist/` (committed)

**Interfaces:**
- Consumes: everything above.
- Produces: a clean tree and a committed production build.

- [ ] **Step 1: Delete the vanilla frontend**

```bash
git rm -r frontend/js frontend/css
```

Confirm nothing references them: `grep -rn "js/app.js\|css/styles.css\|SadaApi\|SadaRecord\|SadaResults\|SadaFlow" --include="*.py" --include="*.md" --include="*.html" --include="*.ts" --include="*.tsx" .` should return only ADR/README prose you are about to update.

- [ ] **Step 2: Write ADR-0003**

Create `docs/adr/0003-react-frontend.md`, matching the house style of ADR-0001 and ADR-0002 (a `# ADR-NNNN: title`, `**Status:**`, `**Date:**`, then Context / Decision / Consequences). It must record:

- That this supersedes ADR-0002's "vanilla JS, no frameworks" point, and only that point. Auth stays a same-origin HttpOnly cookie.
- Why React + Vite: the vanilla flow controller had grown to 416 lines with hand-rolled navigation, and step state was diverging from the URL.
- Why `frontend/dist/` is committed: Render's service is `runtime: python`, whose build image does not preload Node or npm, so building at deploy time would force either Docker or a second service. Committing the build keeps `render.yaml`, `nixpacks.toml` and `Procfile` untouched and preserves the "no Docker needed" property.
- The cost of that choice: `dist/` can go stale relative to `src/`, so it must be rebuilt and committed before every deploy.
- That frontend testing is limited to Vitest over pure logic; component and end-to-end tests remain unwritten.

- [ ] **Step 3: Update the README**

In `README.md`, change the `frontend/` line in Project layout from "vanilla HTML/CSS/JS single-page flow, served by `app`" to a React + Vite description, and add a section after `## Run`:

````markdown
## Frontend

The frontend is a React + TypeScript SPA built by Vite. The built output in
`frontend/dist/` is **committed to git** (see [ADR-0003](./docs/adr/0003-react-frontend.md)),
so `uvicorn` alone serves the whole app with no Node required.

```bash
cd frontend
npm install
npm run dev       # :5173 with hot reload, proxying /api to :8000
npm test          # Vitest over the pure logic
npm run build     # writes frontend/dist
```

For hot reload, run `uvicorn app.main:app --reload` and `npm run dev` side by
side and use <http://localhost:5173>.

**Before deploying, rebuild and commit the bundle**, or the deploy ships a
stale UI:

```bash
cd frontend && npm run build && cd ..
git add frontend/dist && git commit -m "Rebuild frontend"
```
````

- [ ] **Step 4: Build and commit the bundle**

```bash
cd frontend && npm run build && cd ..
git add -f frontend/dist
git status --short   # confirm dist/ is staged, node_modules/ is not
```

- [ ] **Step 5: Run every check**

```bash
cd frontend && npm test && npm run typecheck && cd ..
./.venv/Scripts/python.exe -m pytest -q
```
Expected: Vitest 17 passing, pytest 150 passing.

- [ ] **Step 6: Full manual click-through**

Install a browser if needed: `npx playwright install chromium`.

Start `./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000` and walk the whole flow, confirming each: welcome renders; `Start practicing` goes to `/reciters`; choosing a reciter goes to `/verses?reciter=N`; two-tap range selection updates the readout; `▶ Listen to the reciter` plays the selected range with verse highlighting; `Continue to recording` goes to `/record`; recording, stopping, previewing and re-recording all work; submitting shows the spinner then `/results/<id>`; the chart, chips and tips render and chip focus filters both; `Try again` returns to `/record`; sign up switches the navbar to your email; `Log out` reverts it; the browser back button walks back through the steps; `/results/<id>` loads in a fresh tab; and pressing `Back` mid-recording releases the microphone.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Remove the vanilla frontend, add ADR-0003, ship the built bundle

Deletes frontend/js and frontend/css now that every screen is ported,
documents the framework change and the committed-dist tradeoff in
ADR-0003, adds a frontend section to the README, and commits the
production build that FastAPI serves.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Self-Review Notes

Checked against the spec on 2026-09-06:

- **Spec coverage.** Project layout: Task 1. Dependency versions: Task 1. Routes: Task 3 (table) with each route filled in by Tasks 4, 5, 6, 8, 9. State/SessionContext: Task 3. Component map: Tasks 3, 4, 6, 8, 9, 10. API layer: Task 2. `useRecorder`: Task 7. `PitchChart`: Task 10. Backend changes: Task 1. Build/deploy and README: Task 11. Testing amendment (Vitest over pure logic): Tasks 2, 7, 9. ADR-0003: Task 11.
- **Known gap, deliberately accepted.** The spec's "no visual redesign" is verified only by human comparison in Task 11 Step 6, since there is no screenshot baseline. Anyone wanting stronger assurance should capture screenshots of the current UI before starting Task 1.
- **Naming consistency.** `recorderReducer`, `initialRecorderState`, `formatDuration`, `CAP_SECONDS`, `groupByVerse`, `clampPercent`, `messageFromBody`, `ApiError`, `api.*`, `useSession`, `SessionProvider` are each defined once and referenced with the same names throughout. The `Passage` type and the `PassageRoute` component are deliberately distinct names to avoid a collision in `App.tsx`.
