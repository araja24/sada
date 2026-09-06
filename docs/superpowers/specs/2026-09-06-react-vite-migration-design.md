# Design: migrate the Sada frontend from vanilla JS to React + Vite

**Date:** 2026-09-06
**Status:** Approved, ready for implementation planning

## Context

`frontend/` is currently four hand-written files served directly as static
assets by FastAPI:

- `index.html` holds every wizard step as a `<section class="step">`, toggled
  with the `hidden` attribute.
- `js/app.js` (416 lines) is the flow controller: navigation via a `navStack`
  array, reciter and passage selection, auth, recent attempts, error banner.
- `js/record.js` wraps `MediaRecorder` with a live timer and a 3:00 cap.
- `js/results.js` renders the score, sub-scores, per-verse chips, tips, and an
  imperative canvas pitch chart.
- `css/styles.css` is a single ~230-line stylesheet.

`app/main.py` mounts the directory with
`StaticFiles(directory=settings.FRONTEND_DIR, html=True)` at `/`, last, so it
never shadows `/api/*` or `/docs`.

This design replaces that with a React single-page app built by Vite, while
keeping the backend, the visual design, and both deployment targets intact.

### Relationship to ADR-0002

ADR-0002 records "vanilla JS, no frameworks" as a deliberate property of this
stack. This migration overturns that specific point (and only that point). It
does not change the auth decision itself: the session stays a same-origin,
signed, HttpOnly cookie. **ADR-0003 must be written as part of this work** to
record the framework change and the committed-`dist` tradeoff.

## Decisions taken

Four choices were settled before this design was written:

| Decision | Choice | Reason |
|---|---|---|
| Build and deploy | Commit `frontend/dist` to git | Render's service is `runtime: python`, whose build image does not preload Node or npm. Committing the build output leaves `render.yaml`, `nixpacks.toml` and `Procfile` untouched, keeps the README's "no Docker needed" property, and matches the existing precedent of committing the reference bundle for deploy. |
| Language | TypeScript | The main risk in this port is drift between the frontend's assumptions and `app/schemas.py`. Types catch that at compile time. |
| Routing | `react-router` with real URLs | The navbar links and the browser back button work natively, results become shareable and refreshable, and the hand-rolled `navStack` disappears. |
| Styling | Keep one global `styles.css` | Guarantees the port is visually identical, so any regression is obviously a markup bug rather than a style bug. |

## Architecture

### Project layout

`frontend/` becomes the Vite project root, since Vite requires `index.html` at
the root and that is where it already lives.

```
frontend/
  package.json          see "Dependency versions" below
  vite.config.ts        @vitejs/plugin-react; server.proxy '/api' -> :8000
  tsconfig.json
  index.html            Vite entry: <script type="module" src="/src/main.tsx">
  public/
    favicon.svg         moved from frontend/favicon.svg
  src/
    main.tsx            imports styles.css, mounts <BrowserRouter><App /></BrowserRouter>
    App.tsx             layout shell (Navbar, <Outlet/>, Footer) + <Routes>
    styles.css          moved unchanged from css/styles.css
    api/
      client.ts         port of js/api.js
      types.ts          hand-mirrored from app/schemas.py
    state/
      SessionContext.tsx
    hooks/
      useRecorder.ts
    components/
      Navbar.tsx  Footer.tsx  ErrorBanner.tsx  RecentAttempts.tsx
      ReferencePlayer.tsx  Recorder.tsx  PitchChart.tsx
      OverallScore.tsx  SubScoreGrid.tsx  VerseChips.tsx  TipsList.tsx
    routes/
      Welcome.tsx  Auth.tsx  Reciters.tsx  Passage.tsx  Record.tsx  Results.tsx
  dist/                 committed build output
```

Deleted: `frontend/js/`, `frontend/css/`, `frontend/favicon.svg` (moved).
Gitignored: `frontend/node_modules/`. Explicitly **not** ignored:
`frontend/dist/`.

### Dependency versions

Latest as published on npm at the time of writing (2026-09-06), which is what
`npm create vite@latest` will resolve to:

| Package | Version |
|---|---|
| `vite` | 8.2.2 |
| `react`, `react-dom` | 19.2.8 |
| `react-router-dom` | 7.18.3 |
| `@vitejs/plugin-react` | 6.1.1 |
| `typescript` | 7.0.2 |

TypeScript 7 is the native compiler rewrite. If it causes friction with the
Vite React template during implementation, pinning to the latest 5.x is an
acceptable fallback and does not change anything else in this design.

### Routes

Every route is self-sufficient on a cold load. Wizard selections live in the
URL rather than in memory, so a refresh or a shared link works.

| URL | Replaces | Cold-load behaviour |
|---|---|---|
| `/` | welcome step + recent attempts | Fetches `/api/attempts` |
| `/login`, `/signup` | the `authMode` toggle | Two routes sharing `Auth.tsx` |
| `/reciters` | reciter step | Fetches `/api/reciters` |
| `/verses?reciter=<id>` | passage step | Fetches the passage by id |
| `/record?reciter=<id>&start=<n>&end=<n>` | record step | Needs only the query params |
| `/results/:attemptId` | results step | Fetches the attempt, then the passage |

Notes:

- `Back` buttons become `navigate(-1)`. `navStack` and `back()` are deleted.
- The "analyzing" step is **not** a route, because it has no meaning on a
  refresh. It is a `submitting` state inside `Record.tsx` that navigates to
  `/results/:id` on success. On failure it stays put with the take intact,
  preserving the current `SadaRecord.recover()` behaviour.
- `/results/:attemptId` rehydrates from `AttemptOut.reciter_id`: fetch the
  attempt, fetch `/api/passages/fatiha?reciter_id=...`, and resolve the
  reciter's display name from `/api/reciters`. No backend schema change.
- A route with a missing or invalid query param (for example `/record` with no
  `reciter`) redirects to `/reciters` rather than rendering broken.

### State

The only genuinely global state is the signed-in user. `SessionContext`
exposes `{ user, loading, refresh(), logout() }` and replaces the `currentUser`
module global plus `refreshAccountNav()`. Everything else is route-local or
derived from the URL.

### Component map

| Current | Becomes |
|---|---|
| `js/app.js` navigation + steps | the six `routes/` components |
| `js/app.js` account nav | `SessionContext` + `Navbar` |
| `js/app.js` recent attempts | `RecentAttempts` |
| `js/app.js` ref player | `ReferencePlayer` |
| `js/app.js` error banner + `window.SadaFlow` | `ErrorBanner` (route-local error state) |
| `js/record.js` | `Recorder` + `useRecorder` |
| `js/results.js` | `OverallScore`, `SubScoreGrid`, `VerseChips`, `TipsList`, `PitchChart` |
| `js/api.js` | `api/client.ts` |

Markup and class names are preserved exactly so the untouched stylesheet keeps
matching. The recent navbar work (sticky `.navbar`, `Practice` / `My attempts`,
no arrow glyphs, no em dashes) carries across unchanged.

### API layer

`api/client.ts` keeps the existing single `request()` chokepoint and the
`messageFromBody()` friendly-error mapping verbatim, including the 413 and 5xx
special cases. `ApiError` becomes a real `class ApiError extends Error` with
`status` and `body`. All calls keep `credentials: "same-origin"`.

`api/types.ts` mirrors `app/schemas.py` by hand: `Reciter`, `Passage`,
`PassageVerse`, `Word`, `Attempt`, `AttemptSummary`, `PitchOverlay`, `Tip`,
`PerVerse`, `User`.

### The two imperative parts

These carry the most porting risk and get explicit treatment.

**`useRecorder`** owns the `MediaRecorder`, the chunk array, the timer
interval, the object URL, and the stream tracks. State machine:
`idle -> recording -> recorded -> submitting`. Every resource is released in a
`useEffect` cleanup, including on unmount mid-recording, which the current code
only handles on the happy path. The 180-second cap and the `0:00` / `of 3:00
max` display are preserved.

**`PitchChart`** keeps the existing canvas drawing code (device-pixel-ratio
scaling, verse boundary markers, focused-verse shading, the two contour lines
in `#3f6f5e` and `#c1873b`) verbatim inside a `useEffect` keyed on
`[attempt, passage, focusedVerse]`. A `ResizeObserver` on the canvas replaces
the debounced window `resize` listener.

### Backend changes

Two changes in Python, both small:

1. `settings.FRONTEND_DIR` default moves from `REPO_ROOT / "frontend"` to
   `REPO_ROOT / "frontend" / "dist"`. The `SADA_FRONTEND_DIR` override stays.
2. `_mount_frontend()` gains an SPA fallback, because `StaticFiles(html=True)`
   404s on `/results/abc123`. It becomes: mount the hashed assets directory,
   then register a catch-all `GET /{path:path}` **after** the API routers that
   returns `index.html`. The catch-all must not shadow `/api/*`, `/docs`,
   `/openapi.json`, or the favicon. The existing "return early if index.html is
   missing" guard is kept so the API still boots without a build.

No changes to routes, models, auth, or the analysis pipeline.

## Build and deployment

- `npm run build` writes `frontend/dist`, which is committed. Deploy configs
  are untouched.
- Local dev, two supported modes:
  - `uvicorn app.main:app --reload` alone, serving the committed build.
  - `npm run dev` on :5173 with `/api` proxied to :8000, for HMR. One proxy
    rule is enough because the reference audio is also under `/api`
    (`/api/reciters/{slug}/audio`).
- README gains a frontend section covering both modes and the requirement to
  rebuild and commit `dist` before deploying.

## Testing

There is **no automated frontend coverage before or after this change**. That
is a known gap and this migration does not close it. Correctness rests on:

1. `pytest -q` staying green. `test_static_frontend_is_served` is the one test
   that must change: it currently asserts `/js/app.js`, `/js/record.js`,
   `/js/results.js` and `/css/styles.css`, which stop existing once Vite emits
   hashed `/assets/*` filenames. It is rewritten to assert that `/` serves
   HTML, that a deep link such as `/results/x` falls back to HTML, that
   `/api/health` still returns JSON rather than the SPA shell, and that the
   favicon resolves. The other 146 tests are untouched.
2. `tsc --noEmit` and `vite build` succeeding.
3. A manual click-through of the full flow (welcome, sign up, reciter, verses,
   listen to reference, record, submit, results, verse focus, try again, log
   out, deep-link a result, browser back). This requires a browser:
   `npx playwright install chromium` must be run, since none is installed.

## Out of scope

- Any visual redesign. The port is pixel-identical by intent.
- Adding a frontend test framework (Vitest, Testing Library, Playwright specs).
  Worth doing, but it is its own piece of work.
- Changing auth, the API surface, or the analysis pipeline.
- Server-side rendering, or any framework above Vite.

## Risks

| Risk | Mitigation |
|---|---|
| `dist/` goes stale relative to `src/` | ADR-0003 records the tradeoff; README documents rebuilding before deploy. A pre-deploy check is a possible follow-up. |
| Recorder resource leaks under React's effect lifecycle | `useRecorder` releases tracks, interval and object URL in cleanup; verify by unmounting mid-recording. |
| Catch-all route shadowing the API | Registered after the routers, with explicit prefix exclusions, and covered by the rewritten test. |
| Visual drift | Stylesheet and class names unchanged; compare against the current UI during click-through. |
