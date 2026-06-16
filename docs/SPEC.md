# Job Finder — Build Spec

This is the authoritative spec. Build it in the phases at the end, smallest runnable
slice first. Each phase has acceptance criteria that must pass before moving on.

---

## 1. Outcomes (what "done" means)

These are the exact, testable outcomes the system must deliver:

1. **Multi-source discovery without naming sources up front.** Roles are pulled from
   structured aggregators and remote boards out of the box, plus targeted company ATS
   endpoints and bespoke career pages — see §6. A user need not know which companies
   to target to get useful results.
2. **Remote / remote-first filtering.** Every job carries a `remote_mode`
   (`remote`, `remote_first`, `hybrid`, `onsite`, `unknown`); the UI can filter on it.
3. **Configurable title variations, not hardcoded.** A profile has a canonical role +
   seniority; the system expands these into title variations (§7.1) which the user can
   then edit. Different users search different titles with zero code change.
4. **Salary-shown filter.** Each job records `salary_disclosed` (true only when the
   source returned a real figure, not an estimate). The UI can show only jobs with
   disclosed salary, or only those without.
5. **CV-match scoring.** Each job is scored against a CV producing a `fit_score`
   (0–100), `matched_skills`, `gaps`, `flags`, and a short `rationale` (§7.3).
   **No fabricated "likelihood of success" probability** — confidence is expressed via
   the fit score and flags only.
6. **A web frontend** to browse, filter, sort and triage results, plus profile and CV
   management.
7. **Multi-tenant.** Users, profiles and CVs are first-class. Friends can sign up, add
   their own profiles/CVs, and see only their own results.
8. **Extensible.** A new source is one new adapter file + a registry entry (§5).

---

## 2. Architecture overview

```
                 ┌─────────────┐
   Celery Beat ─▶│ fetch tasks │── per (source × active profile)
                 └──────┬──────┘
                        ▼
   SourceAdapter.fetch(ctx) ─▶ RawJob[] ─▶ normalise ─▶ dedup ─▶ upsert `jobs`
                                                                      │
                                                                      ▼
                                                            enqueue score tasks
                                                                      │
                              LLM rubric (top candidates) ◀───────────┘
                                                                      ▼
                                                            upsert `job_scores`

   FastAPI  ──reads──▶ Postgres ◀──reads── React SPA (browse / filter / triage)
```

- **API** (FastAPI): serves the SPA and the JSON API. No heavy work in request path.
- **Worker** (Celery): runs fetch + scoring tasks.
- **Beat** (Celery Beat): schedules fetches per source on a configurable cadence.
- **Postgres**: single source of truth and the seam between ingestion and frontend.
- **Redis**: Celery broker/result backend.

Keep the LLM out of the hot path: title expansion runs on profile save; scoring runs
async in the worker and is cached.

---

## 3. Directory structure

```
.
├── CLAUDE.md
├── docs/
│   └── SPEC.md
├── docker-compose.yml
├── Makefile
├── .env.example
├── pyproject.toml
├── alembic/                      # migrations
├── app/
│   ├── main.py                   # FastAPI app factory
│   ├── config.py                 # pydantic-settings, env only
│   ├── db.py                     # engine/session
│   ├── models/                   # SQLAlchemy models
│   ├── schemas/                  # Pydantic DTOs
│   ├── api/                      # routers: profiles, cvs, jobs, sources, admin
│   ├── core/
│   │   ├── sources/
│   │   │   ├── base.py           # RawJob, FetchContext, SourceAdapter, registry
│   │   │   ├── adzuna.py
│   │   │   ├── reed.py
│   │   │   ├── himalayas.py
│   │   │   ├── remotive.py
│   │   │   ├── remoteok.py
│   │   │   ├── hn_whoishiring.py
│   │   │   ├── greenhouse.py     # ATS (per-company config)
│   │   │   ├── lever.py          # ATS
│   │   │   ├── ashby.py          # ATS
│   │   │   └── jsonld.py         # schema.org/JobPosting extractor
│   │   ├── llm/
│   │   │   ├── provider.py       # LLMProvider interface + Anthropic & OpenAI impls
│   │   │   ├── titles.py         # title expansion
│   │   │   ├── normalise.py      # unstructured → structured (used sparingly)
│   │   │   └── scoring.py        # rubric scoring
│   │   ├── pipeline.py           # fetch → normalise → dedup → upsert → enqueue
│   │   └── dedup.py
│   ├── tasks/                    # celery tasks + beat schedule
│   └── workers.py                # celery app
├── web/                          # React + Vite + TS frontend
└── tests/
    ├── fixtures/<source-key>/    # recorded payloads, one per adapter
    └── ...
```

---

## 4. Data model

All tables have `id` (uuid pk), `created_at`, `updated_at` unless noted.

**users** — `email` (unique), `name`. (Auth added in Phase 6; until then a seeded user.)

**search_profiles** — `user_id` fk · `name` · `canonical_role` (e.g. "Cloud Platform
Engineer") · `seniority` (enum: junior/mid/senior/lead/staff/principal) ·
`title_variations` (jsonb array of strings, user-editable) · `remote_modes` (jsonb
array of RemoteMode) · `require_salary` (bool) · `min_salary` (int, nullable) ·
`currency` (default GBP) · `locations` (jsonb array, nullable) · `active` (bool).

**cvs** — `user_id` fk · `name` · `raw_text` · `parsed` (jsonb: skills[], roles[],
years_experience, summary) · `version` (int) · `is_default` (bool). Multiple CVs/
versions per user supported.

**sources** — `type` (adapter key, e.g. `adzuna`) · `name` · `config` (jsonb;
e.g. `{"board_token": "tailscale"}` for ATS adapters) · `enabled` (bool) ·
`cadence_minutes` (int) · `last_run_at` (nullable). Global, not per-user.

**jobs** — `source_id` fk · `external_id` (source's stable id) · `title` · `company` ·
`url` · `description` (text) · `remote_mode` · `location` (nullable) · `salary_min` ·
`salary_max` · `salary_currency` · `salary_period` · `salary_disclosed` (bool) ·
`posted_at` (nullable) · `fetched_at` · `content_hash` · `dedup_key`.
Unique on `(source_id, external_id)`. `dedup_key` used for cross-source dedup (§9).

**job_scores** — `job_id` fk · `cv_id` fk · `profile_id` fk · `fit_score` (int 0–100)
· `matched_skills` (jsonb) · `gaps` (jsonb) · `flags` (jsonb) · `rationale` (text) ·
`model` (text) · `scored_at`. Unique on `(job_id, cv_id)` — scoring is cached.

**job_states** — `user_id` fk · `job_id` fk · `status` (enum: new/shortlisted/
applied/rejected/ignored) · `notes` (text). Unique on `(user_id, job_id)`.

---

## 5. Source-adapter contract (the extensibility heart)

`app/core/sources/base.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Iterable, Protocol

class RemoteMode(StrEnum):
    REMOTE = "remote"
    REMOTE_FIRST = "remote_first"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"

@dataclass(slots=True)
class RawJob:
    external_id: str                       # stable id from the source
    title: str
    company: str
    url: str
    description: str
    remote_mode: RemoteMode = RemoteMode.UNKNOWN
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None       # year | month | day | hour
    salary_disclosed: bool = False         # True ONLY if the source gave a real figure
    posted_at: datetime | None = None
    raw: dict = field(default_factory=dict)  # full source payload, for audit/reprocessing

@dataclass(slots=True)
class FetchContext:
    titles: list[str]              # the profile's title variations to query
    locations: list[str] | None
    remote_modes: list[RemoteMode]
    config: dict                   # source-specific (e.g. ATS board token)
    since: datetime | None         # incremental watermark; adapter may ignore

class SourceAdapter(Protocol):
    key: str                       # unique, matches sources.type
    requires_config: bool          # ATS adapters need a board token, etc.
    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]: ...

_REGISTRY: dict[str, type] = {}

def register(cls):
    _REGISTRY[cls.key] = cls
    return cls

def get_adapter(key: str) -> SourceAdapter:
    return _REGISTRY[key]()
```

**Rules every adapter must follow**
- Map source fields into `RawJob`. Set `salary_disclosed=True` **only** when a genuine
  figure is present (e.g. Adzuna's `salary_is_predicted=0`; a non-null Reed
  `minimumSalary`). Estimates/predictions → `salary_disclosed=False`.
- Set `remote_mode` from the source where it's known (remote boards → `REMOTE`/
  `REMOTE_FIRST`); otherwise `UNKNOWN` and let normalisation infer it.
- Be pure and deterministic given a payload. No DB access inside `fetch`.
- Respect the source's rate limits and ToS. Use the official API/feed; never bypass
  bot-detection or auth walls.

### How to add a source

1. Create `app/core/sources/<key>.py`, implement `SourceAdapter`, decorate with
   `@register`.
2. Map fields into `RawJob` per the rules above.
3. Drop a recorded sample payload in `tests/fixtures/<key>/` and add a unit test
   asserting the mapping (skills, salary_disclosed, remote_mode). No live network.
4. Insert a `sources` row with `type=<key>` (+ `config` if `requires_config`).
5. Done — the pipeline discovers it via the registry. No other code changes.

---

## 6. Sources to ship (by tier)

All are free and structured. (LinkedIn and browser-automation are intentionally out of
scope — see §13 for the documented extension point.)

- **Tier 1 — aggregators (catch the long tail of company sites for free):**
  `adzuna` (UK, `/v1/api/jobs/gb/search`, has `salary_is_predicted`),
  `reed` (UK jobseeker API, returns `minimumSalary`/`maximumSalary` or null).
- **Tier 2 — company ATS (targeted; `requires_config`):**
  `greenhouse` (`boards-api.greenhouse.io/v1/boards/{token}/jobs`),
  `lever` (`api.lever.co/v0/postings/{token}`),
  `ashby` (public posting API). One `sources` row per target company.
- **Tier 3 — bespoke career pages:** `jsonld` — given a careers URL in `config`, fetch
  and extract `schema.org/JobPosting` JSON-LD blocks. Structured, low-fragility.
- **Tier 4 — remote / curated boards (roles that skip the big boards):**
  `himalayas` (free JSON, no auth; returns salary + location/timezone restrictions),
  `remotive`, `remoteok`, `hn_whoishiring` (Hacker News "Who is hiring" monthly
  threads via the HN Algolia API).

Cross-cutting (recommend, optional): document an **email-alert ingestion** path — the
user sets up alerts on any board, and a future adapter parses their forwarded inbox.
Leave a stub `email_alerts` adapter key reserved; do not build in v1.

---

## 7. The AI's three lanes

The only places an LLM is used. Everything else is deterministic.

### 7.1 Title expansion (on profile save, cached, user-editable)
Input: `canonical_role` + `seniority`. Output: a list of equivalent/adjacent titles
(e.g. Cloud Platform Engineer → Platform Engineer, Cloud Engineer, DevOps Engineer,
SRE, Infrastructure Engineer, + seniority permutations). Store in
`search_profiles.title_variations`. The user can edit the list in the UI. **Never call
per fetch.**

### 7.2 Normalisation (sparingly)
Only for unstructured sources (`jsonld`, `hn_whoishiring`) where `remote_mode`, salary
or skills aren't clean. Structured APIs map directly with no LLM. Output strictly the
`RawJob` fields it was asked to infer.

### 7.3 Scoring (async, cached)
For each (active profile's new jobs × default CV): the candidate set is already
relevant (jobs were queried by the profile's titles), so score that set directly. The
LLM receives the CV `parsed` summary + the job, and must return **only** this JSON:

```json
{
  "fit_score": 0,
  "matched_skills": ["..."],
  "gaps": ["..."],
  "flags": ["stretch_role", "missing_must_have", "below_salary_target",
            "seniority_mismatch", "remote_mismatch"],
  "rationale": "one or two sentences, British spelling"
}
```

- `fit_score` is capability fit, not a hiring-odds prediction. There is deliberately
  **no probability field**.
- Cache on `(job_id, cv_id)` in `job_scores`; never rescore unless the CV version
  changes.
- Cost control: only score jobs in `new` state for `active` profiles. If job volume
  grows large, add a pgvector cosine prefilter (CV vs job embedding) as an optimisation
  — not required for v1.

`LLMProvider` is a small interface — `generate_json(prompt, schema) -> dict` — with two
implementations, **Anthropic** and **OpenAI**, selected at runtime by `LLM_PROVIDER`
(either/or, never both). `LLM_MODEL` is the model id for the selected provider; the
matching key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) must be set, and the factory
**fails fast at startup** if the selected provider's key is missing. All three lanes
(title expansion, normalisation, scoring) go through this interface, so changing provider
is a config change with zero code edits. Both implementations must coerce output to the
same JSON shape — use Anthropic tool-use and OpenAI structured outputs / JSON mode as
appropriate. (Embeddings, if added later for the scoring prefilter, are provider-specific
and configured separately — out of scope for this switch.)

---

## 8. Scheduling & pipeline

- Celery Beat schedules a `fetch_source(source_id)` task per enabled source every
  `cadence_minutes`.
- `fetch_source` builds a `FetchContext` per active profile, calls
  `adapter.fetch(ctx)`, runs normalise → dedup → upsert, then enqueues
  `score_job(job_id, cv_id)` for genuinely new jobs.
- Everything idempotent: upsert on `(source_id, external_id)`; scoring upsert on
  `(job_id, cv_id)`.
- `make fetch SOURCE=<key>` runs a single source synchronously for debugging.

---

## 9. Dedup

A job often appears from several sources (e.g. Adzuna *and* the company's Greenhouse).
- `content_hash` = hash of normalised(title + company + location).
- `dedup_key` = `slug(company) + "::" + slug(title) + "::" + slug(location or "")`.
- On upsert, if a row with the same `dedup_key` exists from a different source, keep the
  most authoritative (ATS > aggregator) and record the others' URLs in `raw`. Surface
  one row to the UI. Keep this pragmatic; near-duplicates are acceptable.

---

## 10. API (FastAPI)

- `GET /api/jobs` — filters: `profile_id`, `remote_mode`, `salary_disclosed`,
  `min_fit`, `source`, `status`; sort by `fit`/`posted_at`; paginated.
- `GET /api/jobs/{id}` — job + its score for the current user's default CV.
- `PUT /api/jobs/{id}/state` — set status + notes.
- `GET/POST/PUT/DELETE /api/profiles` — POST/PUT triggers title expansion.
- `GET/POST /api/cvs` — upload (txt/pdf/docx → `raw_text` + parsed); set default.
- `GET/POST/PUT /api/sources` — manage sources (admin).
- `POST /api/admin/sources/{id}/run` — trigger a fetch now.

---

## 11. Frontend (React + Vite + TS)

- **Jobs view:** filterable, sortable table (TanStack Table + Query). Filters for
  salary-disclosed, remote mode, min fit score, source, profile, status. Row shows
  title, company, salary (or "not disclosed"), remote mode, fit score.
- **Job detail:** description, score rationale, matched skills, gaps, flags; triage
  buttons (shortlist / applied / rejected / ignore) → `PUT state`.
- **Profiles:** create/edit; the title-variations list is editable chips.
- **CVs:** upload, view parsed summary, set default.
- Styling: clean and flat; teal→blue accent; minimalist. Functional over flashy.

---

## 12. Multi-tenancy & auth

- All user data keyed by `user_id` from day one (seed one user for local dev).
- **Phase 6** adds real auth. Default to an OIDC provider via env config (works with
  the user's existing Entra / Cloudflare Access setup); fall back to simple sessions.
  Do not hardcode any provider — it's configured via env.
- Sources are global; results are partitioned per user by profile + CV.

---

## 13. Extension points (don't build, but don't preclude)

- **Browser-automation adapter** (`playwright` key): for a high-value bespoke source
  that defeats Tiers 1–4 and JSON-LD. Same `SourceAdapter` interface; runs in a
  separate worker queue because it's slow/fragile. Left unbuilt by request — the
  contract already accommodates it.
- **Email-alert ingestion** (`email_alerts` key): parse forwarded job-alert emails.
- **pgvector prefilter** for scoring at scale (§7.3).

---

## 14. Build phases (each must run end-to-end and pass its criteria)

**Phase 0 — Scaffold.** Compose (postgres, redis, api, worker, beat, web), config,
Alembic baseline, health endpoint, Makefile, CI lint/test.
*Accept:* `make up` brings the stack up; `/health` returns ok; `make test`/`make lint` pass.

**Phase 1 — Prove the loop (one source).** `jobs` table, `adzuna` adapter, pipeline
fetch→dedup→upsert, `GET /api/jobs`, minimal jobs table in the UI.
*Accept:* `make fetch SOURCE=adzuna` populates jobs; the UI lists them; re-running adds
no duplicates; `salary_disclosed` is correct against the Adzuna predicted flag.

**Phase 2 — Profiles & CVs.** `users`/`search_profiles`/`cvs`; CV upload + parse; title
expansion on profile save (editable); fetches are driven by the active profile's titles.
*Accept:* creating a profile yields editable title variations; uploading a CV produces a
parsed summary; fetch queries use the profile titles.

**Phase 3 — Scoring.** `job_scores`; rubric scoring async + cached; `min_fit` filter and
score/rationale in the UI.
*Accept:* new jobs get a `fit_score` + rationale + flags; rescoring doesn't happen unless
CV version changes; the UI filters by min fit; no probability field exists anywhere.

**Phase 4 — Breadth.** Add `reed`, `himalayas`, `remotive`, `remoteok`,
`hn_whoishiring`; cross-source dedup (§9); remote-mode + salary-disclosed filters.
*Accept:* jobs arrive from all sources; a job present on two sources shows once; remote
and salary filters work.

**Phase 5 — Targeted companies.** `greenhouse`, `lever`, `ashby` (config-driven) +
`jsonld` extractor; admin UI to add a target company / careers URL.
*Accept:* adding a company token fetches its roles; a careers page with JobPosting
JSON-LD is ingested; ATS rows win dedup over aggregators.

**Phase 6 — Triage & multi-user.** `job_states` + triage UI; OIDC auth; per-user
partitioning verified.
*Accept:* two users see only their own results; triage states persist; auth is
env-configured with no hardcoded provider.

---

## 15. Non-goals (v1)

- No LinkedIn scraping or LinkedIn data source.
- No browser automation / headless scraping in the shipped build.
- No bypassing of any site's bot detection, auth walls, or ToS.
- No fabricated success-probability metric.
