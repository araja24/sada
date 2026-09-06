# ADR-0003: React + Vite frontend, with the build output committed to git

**Status:** Accepted
**Date:** 2026-09-06

## Context

ADR-0002 listed "vanilla JS, no frameworks" as one of the properties of the
stack it wanted to preserve. That was a reasonable call at the time, but the
vanilla frontend did not age well as the flow grew.

By the time every screen was built, `frontend/js/app.js` was a 416-line flow
controller with a hand-rolled `navStack` for back-button behavior. Wizard step
state lived in that controller rather than in the URL, so the two drifted apart:
a results page could not be refreshed without losing its data, and a results
URL could not be shared. Fixing that properly in the vanilla code meant
re-implementing routing, history integration and per-route data loading by
hand, which is most of what a small router library already does.

React with `react-router` gives real URL-owned route state, and Vite gives a
dev server with hot reload and a production bundler. Both are mainstream, both
are small, and neither pulls in a backend runtime.

The deployment target constrains how the bundle gets built. Render's service is
`runtime: python`. That build image does not preload Node or npm, so there is
no way to run `npm run build` at deploy time without either switching the
service to Docker or standing up a second Node service just to produce static
files. Both options give up the project's "no Docker needed" property.

## Decision

Replace the vanilla frontend with a React + TypeScript SPA built by Vite, and
commit the built bundle in `frontend/dist/` to git.

- `frontend/src/` is the live frontend. `react-router` owns route state, so
  every wizard step and every results page is a real URL that refreshes and
  shares correctly.
- `frontend/dist/` is committed. FastAPI serves it as static files, so
  `uvicorn` alone runs the whole app with no Node present. `render.yaml`,
  `nixpacks.toml` and `Procfile` stay exactly as they were.
- TypeScript is pinned at 5.9.3 (the plan named 7.0.2, which broke the build).
  React 19, `react-router` 7 and Vite 8 are pinned in `frontend/package.json`.
- This supersedes only ADR-0002's "vanilla JS, no frameworks" point. The auth
  decision from ADR-0002 is unchanged: the session is still a same-origin,
  signed, `HttpOnly` cookie, with no server-side session table.

## Consequences

- `uvicorn app.main:app` serves the full app with no Node, no Docker and no
  second service. The deploy configs are untouched.
- The committed `dist/` can go stale relative to `src/`. Nothing enforces that
  they match, so the bundle must be rebuilt and committed before every deploy,
  or the deploy ships an old UI against current API code. The README documents
  this and `.gitignore` deliberately does not ignore `frontend/dist/`.
- Frontend testing is limited to Vitest over pure logic: the API error mapping
  (`messageFromBody` / `ApiError`), the recorder reducer, and the results
  grouping helpers. There are no component tests and no end-to-end tests. UI
  regressions in rendering, audio playback or the microphone path are not
  caught by CI and are only found by manual click-through. This is a real gap,
  accepted for a project at this scale rather than papered over.
- `tests/test_api.py` now serves the SPA shell from `frontend/dist/index.html`
  and falls back to it for client-owned deep links such as `/results/:id`, so a
  missing or broken build fails the Python test suite, not just the frontend.
- The vanilla files (`frontend/js/`) and the standalone `frontend/css/`
  directory are deleted. `frontend/css/styles.css` moved to
  `frontend/src/styles.css` back when the Vite project was created.
