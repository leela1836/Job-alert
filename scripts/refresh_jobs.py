from __future__ import annotations

import argparse
from pathlib import Path

from job_alert import BASE_DIR, JOBS_PATH
from job_sources import refresh_jobs

SOURCE_PATH = BASE_DIR / "data" / "job_sources.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh cloud job data from configured sources")
    parser.parse_args()
    jobs = refresh_jobs(SOURCE_PATH, JOBS_PATH)
    print(f"Saved {len(jobs)} jobs to {JOBS_PATH}")


if __name__ == "__main__":
    main()
