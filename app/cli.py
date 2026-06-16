"""Operational CLI. Commands are fleshed out as phases land.

Usage:
    python -m app.cli fetch --source adzuna
    python -m app.cli seed
"""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="job-finder")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Run a single source adapter on demand")
    fetch.add_argument("--source", required=True, help="Adapter key, e.g. adzuna")

    sub.add_parser("seed", help="Load seed sources/profile for local dev")

    args = parser.parse_args(argv)

    if args.command == "fetch":
        print(f"[fetch] source={args.source!r} — implemented in Phase 1.")
        return 0
    if args.command == "seed":
        print("[seed] — implemented in Phase 2.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
