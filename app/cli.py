# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Operational CLI.

Usage:
    python -m app.cli fetch --source adzuna [--query "cloud engineer" "platform engineer"]
    python -m app.cli seed
"""

import argparse
import sys


def cmd_fetch(args: argparse.Namespace) -> int:
    import logging

    from sqlalchemy import select

    from app.core.pipeline import run_fetch
    from app.db import SessionLocal
    from app.models.profile import SearchProfile

    logging.basicConfig(level="INFO")

    with SessionLocal() as session:
        if args.query:
            titles: list[str] = args.query
        else:
            # Use title variations from all active profiles (Phase 2+).
            profiles = session.scalars(
                select(SearchProfile).where(SearchProfile.active.is_(True))
            ).all()
            seen: set[str] = set()
            titles = []
            for p in profiles:
                for t in p.title_variations or []:
                    if t not in seen:
                        seen.add(t)
                        titles.append(t)

        results = run_fetch(args.source, titles, session)

    for counts in results:
        print(
            f"[fetch] source={counts['source']!r} name={counts['source_name']!r} "
            f"fetched={counts['fetched']} new={counts['new']} "
            f"updated={counts['updated']} skipped={counts['skipped']}"
        )
    return 0


def cmd_seed(args: argparse.Namespace) -> int:  # noqa: ARG001
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db import SessionLocal
    from app.models.source import Source
    from app.models.user import User

    # Aggregator sources (authority=0): one row per adapter, upserted by type+name.
    aggregator_sources = [
        {
            "type": "adzuna",
            "name": "Adzuna UK",
            "config": {},
            "enabled": True,
            "cadence_minutes": 60,
            "authority": 0,
        },
        {
            "type": "reed",
            "name": "Reed UK",
            "config": {},
            "enabled": True,
            "cadence_minutes": 120,
            "authority": 0,
        },
        {
            "type": "himalayas",
            "name": "Himalayas",
            "config": {},
            "enabled": True,
            "cadence_minutes": 120,
            "authority": 0,
        },
        {
            "type": "remotive",
            "name": "Remotive",
            "config": {},
            "enabled": True,
            "cadence_minutes": 120,
            "authority": 0,
        },
        {
            "type": "remoteok",
            "name": "Remote OK",
            "config": {},
            "enabled": True,
            "cadence_minutes": 120,
            "authority": 0,
        },
        {
            "type": "hn_whoishiring",
            "name": "HN Who Is Hiring",
            "config": {},
            "enabled": True,
            "cadence_minutes": 1440,
            "authority": 0,
        },
    ]

    users = [
        {"email": "luke@brewerton.me", "name": "Luke"},
    ]

    with SessionLocal() as session:
        for s in aggregator_sources:
            existing = session.scalars(
                select(Source).where(Source.type == s["type"], Source.name == s["name"])
            ).first()
            if existing is None:
                session.add(Source(**s))

        for u in users:
            stmt = pg_insert(User).values(**u).on_conflict_do_nothing(index_elements=["email"])
            session.execute(stmt)

        session.commit()

    print(f"[seed] seeded {len(aggregator_sources)} aggregator source(s), {len(users)} user(s).")
    print("[seed] Add ATS sources (greenhouse/lever/ashby/jsonld) via the admin UI.")
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
        help="Override title queries. Omit to use active profile title variations.",
    )

    sub.add_parser("seed", help="Seed sources and default user for local dev")

    args = parser.parse_args(argv)

    if args.command == "fetch":
        return cmd_fetch(args)
    if args.command == "seed":
        return cmd_seed(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
