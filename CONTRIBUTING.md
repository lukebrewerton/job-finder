# Contributing

Thanks for taking a look at Job Finder. This started as a solo portfolio project, but
genuine contributions are welcome.

## Before opening a PR

- Read `CLAUDE.md` for conventions (formatting, linting, testing, commit style) and
  `docs/SPEC.md` for the architecture and the source-adapter contract — most "how do I
  add X" questions are answered there, particularly §5 ("How to add a source").
- For anything non-trivial, open an issue first to discuss the approach before writing
  code. Saves both of us time if the direction needs adjusting.
- Small fixes (typos, obvious bugs) can just be a PR directly.

## Checks before submitting

- `make lint` (ruff + black --check + mypy) and `make test` must both pass locally —
  the same checks run in CI on your PR.
- If you touched the schema, include an Alembic migration.
- If you added an env var, add it to `.env.example` with a placeholder value.

## What won't be merged

- LinkedIn scraping or browser automation (see `docs/SPEC.md` §13/§15 for why)
- A fabricated "likelihood of success" score — fit score + flags only, deliberately
- Anything that adds an LLM call outside the three defined lanes (`docs/SPEC.md` §7)

If you disagree with one of these, open an issue and make the case — they're
documented decisions, not arbitrary ones, but they're not immovable either.
