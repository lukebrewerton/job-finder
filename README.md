# Job Finder

A self-hostable job aggregator and CV-matching tool. It pulls roles from multiple
sources (aggregators, remote boards, company ATS endpoints, bespoke career pages),
normalises them into a common shape, scores each against your CV, and serves a
filterable web UI. Single user to start, multi-tenant by design.

> Built as a portfolio piece demonstrating adapter-driven ingestion, a clean
> ingestion/serving seam at the database, deterministic-first design with the LLM
> fenced into three well-defined roles, and a local-dev → GitOps deployment story.

## Architecture

```
Celery Beat ─▶ fetch tasks ─▶ SourceAdapter.fetch ─▶ normalise ─▶ dedup ─▶ Postgres
                                                                              │
                                                              LLM scoring (cached)
                                                                              ▼
FastAPI ──reads──▶ Postgres ◀──reads── React SPA (browse / filter / triage)
```

- **Backend** — FastAPI, SQLAlchemy 2 (sync), Alembic, Celery + Beat.
- **Data** — PostgreSQL (single source of truth and the seam between ingestion and UI).
- **Frontend** — React + Vite + TypeScript, TanStack Query/Table, Tailwind.
- **Sources** — pluggable adapters behind one interface; adding one is a new file plus
  a registry entry.

See [`docs/SPEC.md`](docs/SPEC.md) for the full design and the phased build plan, and
[`CLAUDE.md`](CLAUDE.md) for the working conventions.

## Prerequisites

- Docker and Docker Compose v2
- An **OIDC provider** — Google, Authentik, Keycloak, or any other provider that supports OIDC Discovery. See [`docs/auth.md`](docs/auth.md).
- An **LLM API key** — Anthropic or OpenAI — for CV parsing and job scoring. The app runs without one but scoring won't work.
- API keys for any job sources that need them (Adzuna, Reed). Several sources need no credentials. See [`docs/sources.md`](docs/sources.md).

## Quickstart (local development)

```bash
cp .env.example .env      # adjust as needed
make lock                 # generate uv.lock (first run only)
make up                   # build and run the dev stack with hot reload
```

Then:

- Web UI — http://localhost:5173
- API health — http://localhost:8000/api/health
- API readiness (DB + Redis) — http://localhost:8000/api/ready

Common tasks:

```bash
make test     # pytest
make lint     # ruff + black --check + mypy
make format   # ruff --fix + black
make migrate  # alembic upgrade head
```

## Getting started

Once the stack is running (dev or prod), the setup order matters:

1. **Profile** — create a search profile with your canonical role (e.g. "Platform Engineer") and seniority. The LLM generates title variation keywords automatically; you can edit them afterwards.
2. **CVs** — upload your CV. It is parsed immediately; scoring runs in the background once jobs are loaded.
3. **Sources** — add at least one source and hit **Run now** to fetch immediately, or wait for the scheduled cadence.
4. **Jobs** — roles appear in the Active tab. Scores arrive shortly after via the worker. Click any row for the detail panel: fit score, role summary, matched skills, gaps, and triage controls.

The Active tab hides anything you have rejected or ignored. Shortlisted and Applied have their own tabs.

## Deployment

Production runs from [`docker-compose.prod.yml`](docker-compose.prod.yml). All secrets
are injected as environment variables — nothing sensitive lives in the repo. Migrations
run as a one-shot `migrate` service before the API starts; a missing required variable
causes an immediate, loud failure rather than silent misconfiguration.

See [`docs/deployment.md`](docs/deployment.md) for the full guide, including a
worked example with Portainer GitOps + Traefik and a Terraform snippet for automated
deployments.

## Repository & CI

- **Canonical: GitLab** (`brewerton/workloads/job-finder`, private). The source of
  truth; development and deployment happen here.
- **Mirror: GitHub** (public, portfolio). A one-way **push mirror** from GitLab
  (GitLab → Settings → Repository → *Mirroring repositories*). You push to GitLab;
  GitHub follows. Never develop on the mirror.

CI runs on GitLab only (`.gitlab-ci.yml`) — lint, type-check, and test. GitHub is a
mirror and carries no CI; GitHub Actions are not used.

## Tooling

Three tools, three jobs: **black** formats, **ruff** lints, **mypy** type-checks.
Managed with **uv**. mypy is configured pragmatically and tightened over time.

## Documentation

| Doc | Contents |
|---|---|
| [`docs/sources.md`](docs/sources.md) | Every source adapter — credentials, config, and how to add a new one |
| [`docs/auth.md`](docs/auth.md) | OIDC setup for Google, Authentik, and other providers |
| [`docs/deployment.md`](docs/deployment.md) | Production deployment guide with Portainer + Traefik example |
| [`docs/SPEC.md`](docs/SPEC.md) | Architecture and phased build plan |

## Status

Phases 1–7 complete (ingestion, dedup, LLM scoring, multi-tenant auth, triage UI,
targeted ATS sources, and QoL improvements). See the phase plan in
[`docs/SPEC.md`](docs/SPEC.md) for what's next.
