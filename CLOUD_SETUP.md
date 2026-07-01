# Cloud Setup for Daily Job Alerts

This version runs in GitHub Actions, so it keeps working even when your PC is off.

## What runs in the cloud
- `scripts/refresh_jobs.py` pulls jobs from configured RSS/Atom sources into `data/jobs.json`
- `scripts/job_alert.py build-profile` reads `Chemuru_Leelamohan_Resume.pdf`
- `scripts/job_alert.py report` scores jobs and emails the results
- `.github/workflows/daily-job-alert.yml` runs every day at 12:30 UTC, which is 6:00 PM IST

## Required GitHub Secrets
Add these in your repository settings:
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `FROM_EMAIL`
- `TO_EMAIL`

## Recommended values
If you use Gmail:
- `SMTP_HOST = smtp.gmail.com`
- `SMTP_PORT = 587`
- `SMTP_USER = your Gmail address`
- `SMTP_PASSWORD = your Gmail app password`
- `FROM_EMAIL = your Gmail address`
- `TO_EMAIL = mohan.leelachemuru@gmail.com`

## How to enable
1. Push this folder to a GitHub repository.
2. Add the secrets above.
3. Make sure `Chemuru_Leelamohan_Resume.pdf` is committed to the repo.
4. Enable GitHub Actions.
5. Wait for the scheduled run or trigger it manually from the Actions tab.

## Time zone note
GitHub Actions cron uses UTC, not IST.
- `30 12 * * *` = 12:30 UTC = 6:00 PM IST

## Limitation
This cloud version depends on RSS/Atom feeds listed in `data/job_sources.json`.
If you want new sources later, add feeds that are safe to fetch from GitHub Actions.
