# ADR-0002: User accounts, with guest sessions that upgrade on signup

**Status:** Accepted
**Date:** 2026-09-03

## Context

`INITIAL_PROJECT_PLAN.md` §2 and §8 fix v1's scope as accountless: "No user accounts... Attempts may be stored locally (SQLite) with an anonymous session ID for a simple 'recent attempts' list," and §8 explicitly says "Do not add... auth unless asked."

The developer has now asked for real accounts, so recitation history persists per-account rather than per-browser. This ADR records that decision and how it's implemented, superseding those two PRD lines (see the PRD diff below).

Two things drove the specific shape of the decision:

1. The project's whole stack is deliberately minimal and self-contained (Python/FastAPI, SQLite, vanilla JS, no frameworks, no Docker, single-service Render/Railway deployment). Anything added here should keep that property rather than trade it away.
2. The developer wants email+password now, with Google OAuth as an explicit later addition -- not a hypothetical one -- so the data model shouldn't assume password is the only credential a user will ever have.

## Decision

**Build the auth ourselves**, rather than adopt a hosted provider (Clerk/Auth0/Supabase Auth/Firebase Auth):

- A `users` table in the existing SQLite database: `id`, `email` (unique), `password_hash`, `created_at`. Password hashing via `bcrypt` (new dependency; small, no framework).
- Session state via Starlette's built-in `SessionMiddleware` (Starlette is what FastAPI is built on, so this adds only `itsdangerous`, not a new framework) -- a signed, `HttpOnly` cookie holding a small JSON payload. No server-side session table: the cookie itself is the session, which keeps the design stateless and revocation-free, an accepted v1 limitation (see Consequences).
- Every visitor, logged in or not, gets a `session_id` (UUID4) in that cookie the first time they're seen -- this is the PRD's existing "anonymous session ID" concept, just implemented now instead of only described. `attempts` rows (issue #7) always carry `session_id`, plus a nullable `user_id`.
- **Guest-to-account claim:** on successful signup or login, run
  `UPDATE attempts SET user_id = :user WHERE session_id = :current_session AND user_id IS NULL`
  once, then set `user_id` in the session cookie. This attaches every attempt the current browser made as a guest to the account being created/logged into, in one query -- no separate "migrate my history" flow needed. Logging out clears `user_id` from the cookie but keeps the same `session_id`, so a logged-out browser reverts to guest behavior on the same "recent attempts" identity it had before logging in.
- Future Google OAuth: add an `oauth_accounts` table (`user_id`, `provider`, `provider_user_id`) rather than overloading `users`. `password_hash` is already nullable-shaped for an eventual OAuth-only account, so this doesn't require a `users` schema change when it happens -- just a new table and a new login route.

**Rejected alternatives:**

- *Hosted auth provider.* Gets email verification/password reset for free and OAuth is trivial to add, but introduces a new external service, account, and (for most of them) a frontend JS SDK -- exactly the kind of dependency this project has avoided everywhere else, for a marginal benefit at this scale.
- *Stateless JWT (access+refresh tokens).* Solves multi-instance horizontal scaling, which a single free-tier Render/Railway service doesn't need. Would add real complexity (refresh rotation, XSS-safe storage) with no corresponding benefit here.

## Consequences

- **In scope for v1:** email+password signup/login/logout, the guest-claim behavior above, and per-account attempt history for issue #11's UI.
- **Explicitly out of scope for v1** (own limitations of a from-scratch, no-provider approach): email verification, password-reset flow, and session revocation (a stolen/leaked session cookie remains valid until it expires; there's no server-side session list to invalidate from). Worth a follow-up ADR/issue if this ships beyond a portfolio context.
- `SESSION_SECRET_KEY` becomes a new required `.env` value (see `.env.example`), used to sign the session cookie. Must never be committed, and must not rotate carelessly in production (rotating it invalidates every existing session).
- `requirements.txt` gains `bcrypt` and `itsdangerous`. No new frameworks, ORMs, or services -- SQLAlchemy and FastAPI/Starlette are already the fixed stack.
- Issue #7 (FastAPI endpoints + persistence) gains the `users` table, the `/auth/*` endpoints, and the guest-claim query as acceptance criteria.
- Issue #11 (polish/recent-attempts) changes from "an anonymous session's recent attempts" to "a signed-in user's attempt history," with guest "recent attempts" still working exactly as before for anyone who hasn't signed up.
- PRD §2 and §8 are updated to reflect this (see the corresponding PRD diff).
