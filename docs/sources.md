# Source Adapters

Job Finder pulls roles from two categories of source:

- **Breadth sources** — aggregators and public boards that cover many companies at once. Most need no credentials. You configure search titles in your profile and the adapter runs queries against them.
- **Targeted sources** — company ATS endpoints (Greenhouse, Lever, Ashby) and structured careers pages (JSON-LD). These fetch everything from one company's board and let the dedup layer reconcile overlaps with aggregators. They require a per-source `board_token` or `url` set in the source config.

Sources are managed through the web UI (Sources tab) or seeded via `make seed`. A source has a name, a type (the adapter key), an enabled flag, and a fetch cadence in minutes. Targeted sources also carry a `config` object with type-specific values.

**Sources are global, but the job pool covers all users' roles.** When a fetch runs, it collects the title variations from every active profile across all users, deduplicates them, and uses the combined set as search queries. So if one user is a Platform Engineer and another is a Software Engineer, a single Adzuna fetch will query for both — neither user's roles are missed.

Per-user isolation is at the scoring and triage layer: each user has their own CV, fit scores, and triage state. The fit score surfaces relevant roles to the top for each user individually, regardless of how many other roles are in the shared pool. The only case where separate instances are warranted is if users need completely isolated job pools with no crossover at all.

---

## Breadth sources

### `adzuna`

UK-focused aggregator with a wide breadth of roles. Searches by job title keyword — the adapter runs one query per title variation in your active profile.

**Credentials required:** yes — Adzuna Developer API.

Register at [developer.adzuna.com](https://developer.adzuna.com). The free tier gives 250 API calls/day which is sufficient for personal use.

**Env vars:**

```
ADZUNA_APP_ID=your-app-id
ADZUNA_APP_KEY=your-app-key
```

**Source config:** none.

---

### `reed`

Reed.co.uk — UK job board. Searches by keyword, 100 results per query.

**Credentials required:** yes — Reed API.

Apply at [reed.co.uk/developers/jobseeker](https://www.reed.co.uk/developers/jobseeker). The key is issued instantly.

**Env vars:**

```
REED_API_KEY=your-api-key
```

**Source config:** none.

---

### `remotive`

[Remotive.com](https://remotive.com) — remote-only job board. No credentials needed. All jobs are remote by definition.

**Env vars:** none.

**Source config:** none.

---

### `remoteok`

[RemoteOK.com](https://remoteok.com) — remote-only job board. No credentials needed. Fetches the full public feed (all roles); the profile's title filter is applied after fetch.

**Env vars:** none.

**Source config:** none.

---

### `himalayas`

[Himalayas.app](https://himalayas.app) — remote-only job board with salary data. No credentials needed.

**Env vars:** none.

**Source config:** none.

---

### `hn_whoishiring`

Hacker News monthly "Who is hiring?" thread, fetched via the Algolia HN API. Each top-level comment is a freeform job posting; an LLM call normalises it into a structured job record.

**LLM credits required.** Each matching comment costs one LLM call. A keyword pre-filter limits calls to comments that mention at least one of your profile's title variations. A hard cap of 50 comments per run prevents runaway cost.

**Env vars:** none beyond the LLM provider vars (`LLM_PROVIDER`, `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`).

**Source config:** none.

---

## Targeted sources

Targeted sources fetch an entire company job board. They are deduplicated against breadth sources automatically — if the same role appears in Adzuna and a Greenhouse board, the Greenhouse record wins (it carries ATS authority and links directly to the application form).

### `greenhouse`

Fetches a company's public Greenhouse job board via the Greenhouse Boards API. No authentication needed — all public boards are openly accessible.

To find a company's board token, look at their careers page URL:
`https://boards.greenhouse.io/<board_token>/jobs`

**Source config (set in the UI):**

```json
{ "board_token": "acmecorp" }
```

**Env vars:** none.

---

### `lever`

Fetches a company's public Lever job board via the Lever Postings API. No authentication needed.

To find the token, look at a company's Lever board URL:
`https://jobs.lever.co/<board_token>`

**Source config:**

```json
{ "board_token": "acmecorp" }
```

**Env vars:** none.

---

### `ashby`

Fetches a company's public Ashby HQ job board. No authentication needed.

The token is typically the company's slug visible in their careers page URL or embedded in the Ashby widget.

**Source config:**

```json
{ "board_token": "acmecorp" }
```

**Env vars:** none.

---

### `jsonld`

Fetches any careers page that embeds `schema.org/JobPosting` structured data as JSON-LD in `<script type="application/ld+json">` tags. This covers a wide range of company sites without ATS-specific code.

No credentials needed. The adapter fetches the page and extracts all `JobPosting` objects. If a page doesn't embed JSON-LD it will return zero results (silently).

**Source config:**

```json
{ "url": "https://acme.com/careers", "company": "Acme Corp" }
```

`company` is used as a fallback when the JSON-LD doesn't include the organisation name.

---

## Adding a new adapter

Every adapter lives in `app/core/sources/` as a single file. The contract is:

```python
from app.core.sources.base import FetchContext, RawJob, register

@register
class MyAdapter:
    key = "mysource"          # unique string; used in the DB and make fetch SOURCE=
    requires_config = False   # True if source config (board_token, url, etc.) is needed

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        ...
```

`FetchContext` carries the active profile's `titles`, `locations`, `remote_modes`, and any per-source `config` dict. Return `RawJob` instances; the pipeline handles dedup, normalisation, and scoring. No other registration is needed — the `@register` decorator adds the class to the registry automatically.

Write a unit test against a recorded fixture in `tests/fixtures/<key>/` rather than hitting the live API in CI.
