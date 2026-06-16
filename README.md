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

## Deployment (Portainer GitOps)

Production runs from [`docker-compose.prod.yml`](docker-compose.prod.yml) as a
**Portainer Git stack**: point a stack at this repo + that file, set the secrets as
stack environment variables (never in the repo), and enable auto-update. Pushing a
known-good state redeploys it. Migrations run as a one-shot `migrate` service before
the API starts. The same repo deploys identically wherever Portainer runs — local now,
the Proxmox lab later.

## Repository & CI

- **Canonical: GitLab** (`brewerton/workloads/job-finder`, private). The source of
  truth; development and deployment happen here.
- **Mirror: GitHub** (public, portfolio). A one-way **push mirror** from GitLab
  (GitLab → Settings → Repository → *Mirroring repositories*). You push to GitLab;
  GitHub follows. Never develop on the mirror.

Two CI definitions, by design — not duplication, different scope:

- **`.gitlab-ci.yml` (primary)** — lint, test, build, and trigger the Portainer
  GitOps deploy. Runs on GitLab only. Secrets come from GitLab CI/CD variables, never
  the file.
- **`.github/workflows/ci.yml` (mirror)** — lint + test only, no deploy. Provides the
  public "passing" badge on the portfolio repo. Runs on GitHub when the mirror updates.

The `.gitlab-ci.yml` is inert on GitHub (GitHub ignores it) — harmless, and useful as
evidence of the pipeline work.

## Tooling

Three tools, three jobs: **black** formats, **ruff** lints, **mypy** type-checks.
Managed with **uv**. mypy is configured pragmatically and tightened over time.

## Status

Phase 0 (scaffold) complete. See the phase plan in [`docs/SPEC.md`](docs/SPEC.md).
