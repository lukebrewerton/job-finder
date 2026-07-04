# CLAUDE.md — Job Finder

Operating context for Claude Code working in this repo. **Read this first, then `docs/SPEC.md`, then `docs/STATUS.md`.**
If `CLAUDE.local.md` exists alongside this file, read that too — it layers personal/environment notes on top of this file and is not committed.
Work in vertical slices, phase by phase, against the acceptance criteria in the spec. Do not jump ahead.

## What this is

A self-hostable job aggregator and CV-matching tool. It pulls roles from multiple
sources, normalises them into a common shape, scores each against a user's CV, and
serves a filterable web UI. Built for a single user initially but **multi-tenant by
design** — a second user signs up, creates a search profile, uploads a CV, and gets
their own results with no code changes.

## Principles (non-negotiable)

- **Modular, adapter-driven.** Every job source is a pluggable adapter behind one
  interface (`docs/SPEC.md` → "Source-adapter contract"). Adding a source is a new
  file plus a registry entry — nothing else.
- **Nothing user-specific is hardcoded.** Job titles, title variations, CV content,
  salary floors, remote preferences and locations are all *data* (rows in the DB),
  never constants in code.
- **Deterministic by default.** Only use an LLM where a deterministic mapping
  genuinely can't do the job. See `docs/SPEC.md` → "The AI's three lanes". Do not
  add an LLM call to a structured-API adapter that already returns clean fields.
- **Maintainability over cleverness.** Boring, typed, tested code wins.
- **British spelling** in all prose, comments, and UI copy.

## Stack

- Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.x · Alembic
- PostgreSQL 16 · Redis (Celery broker + result backend)
- Celery + Celery Beat (scheduling)
- LLM behind a provider interface — **Anthropic or OpenAI**, selected by env (either/or). See "LLM provider" below.
- Frontend: React 19 · Vite · TypeScript · TanStack Query + TanStack Table · Tailwind v4
- Docker Compose for local / homelab; one container per service
- Tooling: **uv** (env/deps) · **black** (format) · **ruff** (lint only) · **mypy** (types) · pytest

## LLM provider

Provider-switchable via env — either/or, never both at once:

```
LLM_PROVIDER=openai           # or: anthropic
LLM_MODEL=<model-id>          # the model id for whichever provider is selected
OPENAI_API_KEY=...            # used when LLM_PROVIDER=openai
ANTHROPIC_API_KEY=...         # used when LLM_PROVIDER=anthropic
```

Switching provider is a `.env` change only — no code edits, no rebuild. The provider
factory must fail fast at startup if the selected provider's key is missing. See
`docs/SPEC.md` §7 for the three lanes this interface serves (title expansion,
normalisation, scoring) — do not add LLM calls outside those three lanes.

Which provider is actually in use day to day is environment status, not project
convention — see `CLAUDE.local.md` if present.

## Conventions

- **Config via env vars only** (12-factor). No secrets in code or git. Every var is
  documented in `.env.example`.
- Type hints everywhere. **Three tools, three jobs:** `black` formats, `ruff` lints
  (lint only — do **not** enable `ruff format`), `mypy` type-checks. All must be clean.
  mypy is configured pragmatically (not `--strict`) and tightened over time. `pytest`
  for tests.
- **Dependencies via uv, always locked.** To add/remove a package use `uv add <pkg>`
  / `uv add --dev <pkg>` / `uv remove <pkg>` (never hand-edit `pyproject.toml` deps
  without re-locking). After any dependency change run `make lock` (i.e. `uv lock`) and
  **commit the updated `uv.lock`** in the same change — the Dockerfile builds with
  `uv sync --frozen`, so an out-of-date lockfile breaks the image. Don't pin exact
  versions in `pyproject.toml`; let the lockfile hold the resolved set.
- **All schema changes via Alembic migrations.** Never edit the DB by hand.
- **Adapters are pure and unit-tested against recorded fixtures.** No live network in
  the test suite — capture a sample payload per source under `tests/fixtures/<key>/`.
- Structured (JSON) logging. Emit one summary log line per fetch run with counts
  (fetched / new / updated / skipped).
- Idempotent pipeline: re-running a fetch must not create duplicates.

## Source control, remotes & secrets

- **Canonical repo:** GitHub, public. Development happens here, CI runs here, and
  issues/PRs are reviewed and merged directly — no second remote, no mirror.
- **CI is GitHub Actions** (`.github/workflows/ci.yml`), running the same
  `make lint` / `make test` steps as before.
- **Work-in-progress stays on unpushed feature branches**, not a second remote. Don't
  push a branch until it's ready to be seen. Even solo work goes through a PR against
  `main` — keeps `main` clean and gives CI a gate to run against.
- **History note:** this project was originally built on a private GitLab instance and
  migrated to GitHub once functionally complete (see `docs/STATUS.md`). Don't reference
  the old GitLab/Portainer-from-GitLab setup as current — GitHub is the only remote
  that matters now.
- **Secret hygiene (critical — this repo is public):**
  - **Never commit secrets.** No real `.env`, API keys, tokens, passwords, or
    credentials in any commit. Secrets come from env vars only — a local `.env` for dev,
    deployment-platform environment variables in prod (see `CLAUDE.local.md` for the
    current deployment setup).
  - `.env` is git-ignored; never `git add -f` it. The committed template is
    **`.env.example`** with placeholder values only (already present — keep it current).
  - **Every env var the code reads must be added to `.env.example`** with a non-secret
    placeholder, in the same change that introduces it.
  - History is forever: a secret committed once is compromised even if later removed.
    If it ever happens, **rotate the credential** — don't just delete the file.

## Common commands

- `make up` — run the full stack (postgres, redis, api, worker, beat, web)
- `make lock` — regenerate `uv.lock` after changing dependencies
- `make migrate` — apply Alembic migrations
- `make test` — pytest
- `make lint` — ruff + `black --check` + mypy
- `make format` — ruff `--fix` + black
- `make fetch SOURCE=<key>` — run one source adapter on demand (dev/debug)
- `make seed` — load seed sources/profile for local dev

## Key decisions already made (not up for re-discussion)

| Decision | Rationale |
|---|---|
| Sync SQLAlchemy throughout | FastAPI and Celery share models/sessions; no async/sync split to reason about |
| Adapter registry pattern | New source = one file, zero other changes |
| No ruff format | black owns formatting; enabling both is the one real overlap |
| mypy pragmatic not strict | Tighten per-package over time as code settles |
| uv not Poetry | Faster, standards-based (`[project]` PEP 621), covers Python version management |
| No Makefile replacement | Kept — useful for discoverability and Claude Code, wraps the long `docker compose run --rm api …` calls |
| No LinkedIn scraping | ToS, anti-bot friction, aggregators already cover most LinkedIn-sourced roles |
| No browser automation (v1) | Extension point exists in SPEC §13; not built initially |
| No fake success probability | Fit score + flags only; "likelihood of success" is false precision |

If you think one of these should change, say so and why — don't just silently work around it.

## Definition of done (every change)

1. Tests pass; `black --check`, `ruff`, and `mypy` all clean.
2. Alembic migration included if the schema changed.
3. Any new env var added to `.env.example` (placeholder only); no real secret staged.
4. The acceptance criteria for the relevant phase in `docs/SPEC.md` are met and the
   stack runs end to end.
5. Before ending the session, update `docs/STATUS.md` with what changed and what's
   next, and commit it alongside the code change. Keep it short — overwrite, don't
   append to a growing log.
