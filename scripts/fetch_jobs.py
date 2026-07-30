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
    seen = state.setdefault("seen", {})

    new_count = 0
    for job in jobs:
        entry = seen.get(job.job_id)
        if entry is None:
            seen[job.job_id] = {"first_seen": today, "last_seen": today, "emailed": False}
            new_count += 1
        else:
            entry["last_seen"] = today

    state["last_run"] = today
    save_json(STATE_PATH, state)
    save_json(JOBS_PATH, [job.to_dict() for job in jobs])

    print(f"{new_count} never-seen-before jobs | saved to {JOBS_PATH.name} and {STATE_PATH.name}")

    # A total wipeout means something structural broke; fail loudly in CI.
    if not jobs:
        print("ERROR: every source returned zero jobs", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
