"""FastAPI web layer for Sada.

Wraps the pure-Python analysis pipeline (`analysis/`) in the HTTP API from
INITIAL_PROJECT_PLAN.md §6, with SQLite persistence (§7) and self-built
user accounts (docs/adr/0002-user-accounts.md). No analysis logic lives
here -- this package only does HTTP, persistence, and auth.
"""
