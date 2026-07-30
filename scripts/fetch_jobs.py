"""Fetch jobs from every configured source and record which ones are new."""

from __future__ import annotations

import argparse
import datetime
import sys

from models import (
    COMPANIES_PATH,
    JOBS_PATH,
    SOURCES_PATH,
    STATE_PATH,
    load_json,
    save_json,
)
from sources import collect_all


def migrate_state(state: dict) -> tuple[dict, int]:
    """Convert the old `seen` map to the compact `emailed` map.

    The old schema recorded every job ever fetched. Dedup only ever reads the
    `emailed` flag, and `first_seen` was never rendered anywhere, so ~99% of
    those entries were dead weight - and because `last_seen` was refreshed on
    every run, each daily commit rewrote all of them.
    """
    if "seen" not in state:
        return state, 0
    legacy = state.pop("seen") or {}
    emailed = state.setdefault("emailed", {})
    carried = 0
    for job_id, entry in legacy.items():
        if isinstance(entry, dict) and entry.get("emailed"):
            emailed.setdefault(job_id, entry.get("last_seen") or entry.get("first_seen") or "")
            carried += 1
    return state, carried


def prune_emailed(emailed: dict, today: str, retention_days: int) -> int:
    """Forget jobs emailed long enough ago that resending one is harmless."""
    cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=retention_days)).isoformat()
    stale = [job_id for job_id, sent_on in emailed.items() if str(sent_on) and str(sent_on) < cutoff]
    for job_id in stale:
        del emailed[job_id]
    return len(stale)


def load_boards(india_only: bool = False) -> list[dict]:
    payload = load_json(COMPANIES_PATH, {})
    boards = payload.get("boards", []) if isinstance(payload, dict) else []
    if india_only:
        boards = [b for b in boards if b.get("tier") == "india"]
    return boards


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh job data from all configured sources")
    parser.add_argument("--india-only", action="store_true", help="skip the global/remote company boards")
    parser.add_argument("--quiet", action="store_true", help="only print the summary line")
    parser.add_argument(
        "--emailed-retention", type=int, default=365,
        help="days to remember an emailed job, so it is never resent (default: 365)",
    )
    args = parser.parse_args()

    boards = load_boards(args.india_only)
    sources = load_json(SOURCES_PATH, [])
    if not isinstance(sources, list):
        sources = []

    jobs, reports = collect_all(boards, sources)

    if not args.quiet:
        for report in sorted(reports, key=lambda r: (r.ok, -r.count)):
            print(report.line())

    failures = [r for r in reports if not r.ok]
    print(
        f"\n{len(jobs)} unique jobs from {len(reports) - len(failures)}/{len(reports)} sources"
        + (f" ({len(failures)} failing)" if failures else "")
    )

    today = datetime.date.today().isoformat()
    state = load_json(STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}

    state, carried = migrate_state(state)
    if carried:
        print(f"migrated state to the compact schema, carrying {carried} emailed job ids")

    emailed = state.setdefault("emailed", {})
    pruned = prune_emailed(emailed, today, args.emailed_retention)
    unsent = sum(1 for job in jobs if job.job_id not in emailed)

    state["last_run"] = today
    save_json(STATE_PATH, state)
    save_json(JOBS_PATH, [job.to_dict() for job in jobs])

    print(f"{unsent} jobs not yet emailed | saved to {JOBS_PATH.name} and {STATE_PATH.name}")
    if pruned:
        print(f"pruned {pruned} entries older than {args.emailed_retention} days")
    print(f"state: {len(emailed)} emailed job ids tracked")

    # A total wipeout means something structural broke; fail loudly in CI.
    if not jobs:
        print("ERROR: every source returned zero jobs", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
