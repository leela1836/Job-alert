# Cloud Setup for Daily Job Alerts

Runs entirely in GitHub Actions, so it keeps working when your PC is off.

## What runs each day

| Step | Script | What it does |
| --- | --- | --- |
| 1 | `scripts/fetch_jobs.py` | Pulls jobs from ~48 company ATS boards plus 6 aggregator APIs into `data/jobs.json` |
| 2 | `scripts/job_alert.py build-profile` | Reads the resume and detects skills into `data/profile.json` |
| 3 | `scripts/job_alert.py report` | Scores jobs, emails new matches, records what was sent |
| 4 | `scripts/build_dashboard.py` | Regenerates the public dashboard in `docs/` |

Schedule: `30 12 * * *` = 12:30 UTC = **6:00 PM IST**.

## Where the jobs come from

Everything is **free to apply to** — no premium walls.

- **Company ATS boards** (`data/companies.json`) — Greenhouse, Lever and Ashby expose each
  company's board as public JSON. Applying goes straight into the company's own hiring
  pipeline, with no aggregator in between. India-tier boards include Paytm, Sarvam AI,
  PhonePe, Meesho, HighRadius, Sigmoid, InMobi, Hevo, Netomi, Postman, Groww, CRED and more.
- **Aggregator APIs** (`data/job_sources.json`) — RemoteOK, Arbeitnow, Remotive, Himalayas,
  Jobicy and Hacker News jobs.

Dropped from the old config because they were dead or paywalled: aijobs.net (404),
RemoteOK `.rss` (410 — the JSON API replaced it), Indeed RSS (404, discontinued),
We Work Remotely (applying requires a paid plan), Y Combinator (JavaScript-rendered,
so the HTML scrape only ever returned navigation links).

### Adding a company board

Find the slug and confirm it returns JSON before adding it to `data/companies.json`:

```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/<slug>/jobs" | head -c 300
curl -s "https://api.lever.co/v0/postings/<slug>?mode=json"      | head -c 300
curl -s "https://api.ashbyhq.com/posting-api/job-board/<slug>"   | head -c 300
```

A wrong slug returns 404, and `fetch_jobs.py` will print it as `[FAIL]` rather than
hiding it.

## Required GitHub Secrets

| Secret | Purpose |
| --- | --- |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASSWORD` | Gmail **app password**, not your account password |
| `FROM_EMAIL` | Your Gmail address |
| `TO_EMAIL` | Where the alert is delivered |
| `RESUME_B64` | Base64 of your resume PDF (see below) |
| `ANSWER_BANK_JSON` | Contents of `data/answer_bank.json` |

### Why the resume is a secret

This repository is **public**. Committing the resume would publish your phone number
and personal email. `.gitignore` blocks `*.pdf` and `data/answer_bank.json`, and the
workflow restores both from secrets at runtime.

To produce the secret value:

```bash
base64 -w0 Leelamohan_resume.pdf          # Linux / macOS / Git Bash
```

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("Leelamohan_resume.pdf")) | Set-Clipboard
```

Paste the result as `RESUME_B64`.

## Enabling GitHub Pages

1. Repository **Settings → Pages → Source → GitHub Actions**.
2. Run the workflow once.
3. The dashboard appears at `https://leela1836.github.io/Job-alert/`.

The dashboard publishes job listings and match scores only. Your Interested / Applied /
Rejected marks live in your browser's `localStorage`, so your application history is
never committed or published.

## Tuning what you get

`job-search-profile.md` is the single source of truth for targeting — target roles,
preferred locations, skills, experience level and availability. Edit that file and the
next run picks it up. There is no separate hardcoded profile any more.

Scoring lives in `scripts/matching.py`:

- Role families (AI/ML, QA/SDET, backend, cloud) with per-family weights
- Location buckets: `india` / `remote_open` / `remote_restricted` / `foreign`
- Seniority calibrated to ~8 months of experience — staff/principal/senior titles are
  penalised, SDE-I / Associate / Junior titles are boosted
- Postings asking 3+ years lose points, 5+ years lose more

## Running it locally

```bash
pip install -r requirements.txt
python scripts/fetch_jobs.py                       # fetch everything
python scripts/fetch_jobs.py --india-only          # skip global boards
python scripts/job_alert.py build-profile
python scripts/job_alert.py report --dry-run       # render without sending
python scripts/build_dashboard.py                  # regenerate docs/index.html
```

`--dry-run` writes `data/email_preview.html`, which you can open in a browser to check
the email layout before sending anything.

## Notes and limits

- Jobs already emailed are never resent. That state lives in `data/state.json`, which the
  workflow commits back to the repo. Use **Run workflow → Include jobs already emailed**
  to override.
- Contact emails are extracted only when the posting itself publishes one (about 0.4% do,
  and they are usually generic `careers@` addresses). No address guessing and no
  third-party lookup databases.
- There is no auto-submit. The agent finds jobs, scores them, drafts a cover note and
  hands you the apply link — you decide what to send.
