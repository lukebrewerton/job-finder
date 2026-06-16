"""Operational CLI.

Usage:
    python -m app.cli fetch --source adzuna [--query "cloud engineer" "platform engineer"]
    python -m app.cli seed
"""

import argparse
import sys


def cmd_fetch(args: argparse.Namespace) -> int:
    import logging

    from app.core.pipeline import run_fetch
    from app.db import SessionLocal

    logging.basicConfig(level="INFO")
    titles: list[str] = args.query or []

    with SessionLocal() as session:
        counts = run_fetch(args.source, titles, session)

    print(
        f"[fetch] source={counts['source']!r} "
        f"fetched={counts['fetched']} new={counts['new']} "
        f"updated={counts['updated']} skipped={counts['skipped']}"
    )
    return 0


def cmd_seed(args: argparse.Namespace) -> int:  # noqa: ARG001
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db import SessionLocal
    from app.models.source import Source

    sources = [
        {
            "type": "adzuna",
            "name": "Adzuna UK",
            "config": {},
            "enabled": True,
            "cadence_minutes": 60,
        },
    ]

    with SessionLocal() as session:
        for s in sources:
            stmt = pg_insert(Source).values(**s).on_conflict_do_nothing(index_elements=["type"])
            session.execute(stmt)
        session.commit()

    print(f"[seed] inserted/skipped {len(sources)} source(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="job-finder")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_p = sub.add_parser("fetch", help="Run a single source adapter on demand")
    fetch_p.add_argument("--source", required=True, help="Adapter key, e.g. adzuna")
    fetch_p.add_argument(
        "--query",
        nargs="+",
        metavar="TITLE",
        help="Title queries (Phase 1: no profiles yet). Omit to search without keyword.",
    )

    sub.add_parser("seed", help="Seed sources for local dev")

    args = parser.parse_args(argv)

    if args.command == "fetch":
        return cmd_fetch(args)
    if args.command == "seed":
        return cmd_seed(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
