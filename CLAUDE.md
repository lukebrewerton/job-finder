# CLAUDE.md — Job Finder

Operating context for Claude Code working in this repo. **Read this first, then `docs/SPEC.md`.**
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
- LLM behind a provider interface — **Anthropic or OpenAI**, selected by env (either/or)
- Frontend: React + Vite + TypeScript · TanStack Query + TanStack Table · Tailwind
- Docker Compose for local / homelab; one container per service
- Tooling: **uv** (env/deps) · **black** (format) · **ruff** (lint only) · **mypy** (types) · pytest

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

- **Canonical repo:** GitLab at `brewerton/workloads/job-finder` (private). This is the
  source of truth and the deployment source (Portainer Git stack pulls from here).
- **CI is GitLab CI only.** Create and maintain `.gitlab-ci.yml` (running the same
  `make lint` / `make test` steps). **Do not add GitHub Actions** workflows — GitHub is
  a mirror only, and CI lives on GitLab.
- **Public mirror:** GitHub is a public push-mirror, set up later (not initially). The
  whole repo and its **entire git history** must be treated as eventually public.
- **Secret hygiene (critical — the repo will be public):**
  - **Never commit secrets.** No real `.env`, API keys, tokens, passwords, or
    credentials in any commit. Secrets come from env vars only — a local `.env` for dev,
    Portainer stack environment variables in prod.
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

## Definition of done (every change)

1. Tests pass; `black --check`, `ruff`, and `mypy` all clean.
2. Alembic migration included if the schema changed.
3. Any new env var added to `.env.example` (placeholder only); no real secret staged.
4. The acceptance criteria for the relevant phase in `docs/SPEC.md` are met and the
   stack runs end to end.
