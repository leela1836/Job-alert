# Job Alert — Personal AI Job Search Agent

A fully automated, zero-cost job search pipeline that runs every day on GitHub Actions.
It scans **170+ sources** (company career pages + aggregator APIs), scores every posting
against your resume and preferences, emails you the best matches with ready-to-use cover
note drafts, and publishes a live searchable dashboard.

---

## Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│  GitHub Actions  ·  daily at 12:30 UTC (6 PM IST)                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
          │           fetch_jobs.py                 │
          │                                         │
          │  164 company ATS boards                 │
          │  ├─ Greenhouse  (93 boards)              │
          │  ├─ Lever       (12 boards)              │
          │  ├─ Ashby       (54 boards)              │
          │  ├─ SmartRecruiters (4 boards)           │
          │  └─ Workable    ( 1 board )              │
          │                                         │
          │  6 aggregator APIs                      │
          │  ├─ RemoteOK, Remotive, Himalayas        │
          │  ├─ Jobicy, Arbeitnow                    │
          │  └─ Hacker News Jobs (RSS)               │
          │                                         │
          │  → dedup by content hash                │
          │  → save  data/jobs.json                 │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
          │     job_alert.py  build-profile          │
          │                                         │
          │  Read RESUME_TEXT secret                 │
          │  Detect skills with word-boundary regex  │
          │  Merge with job-search-profile.md        │
          │  → save  data/profile.json               │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
          │       job_alert.py  report               │
          │                                         │
          │  Score every job (0–100)                 │
          │  ├─ Role family match                    │
          │  ├─ Location bucket                      │
          │  │    india / remote_open /              │
          │  │    remote_restricted / foreign        │
          │  ├─ Seniority fit                        │
          │  ├─ Skill overlap (resume ∩ posting)     │
          │  └─ Recency + LLM/agent bonus            │
          │                                         │
          │  Filter: score ≥ 60  (floor 45)         │
          │  Skip: already in  data/state.json       │
          │                                         │
          │  Generate HTML email                     │
          │  ├─ Job cards with score + reasons       │
          │  ├─ Cover note drafts (top 3)            │
          │  └─ Screening Q&A answers                │
          │                                         │
          │  Send via Gmail SMTP                     │
          │  Mark sent jobs in data/state.json       │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
          │         gap_analysis.py                  │
          │                                         │
          │  Analyse reachable postings (score ≥ 50) │
          │  Count skill mentions across postings    │
          │  Diff against detected_skills in profile │
          │  → save  data/gap_report.json            │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
          │        build_dashboard.py                │
          │                                         │
          │  Rank top 120 jobs                       │
          │  Embed jobs + gap report as JSON         │
          │  Generate self-contained HTML SPA        │
          │  → write  docs/index.html                │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
          │           git commit                     │
          │  data/state.json  (dedup, no PII)        │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
          │         GitHub Pages deploy              │
          │  docs/index.html → public dashboard      │
          └─────────────────────────────────────────┘
```

---

## Project structure

```
Job-alert/
├── scripts/
│   ├── models.py              Core data types: Job, MatchResult, JSON helpers
│   ├── sources.py             ATS adapters (Greenhouse, Lever, Ashby,
│   │                          SmartRecruiters, Workable) + aggregator parsers
│   ├── fetch_jobs.py          Orchestrates all fetches → data/jobs.json
│   ├── matching.py            Scoring: role families, location buckets,
│   │                          seniority calibration, skill overlap
│   ├── job_alert.py           Profile builder + HTML email renderer + SMTP
│   ├── drafts.py              Template cover notes + screening Q&A
│   ├── gap_analysis.py        Skill demand vs resume gap analysis
│   ├── build_dashboard.py     Generates docs/index.html (GitHub Pages SPA)
│   └── export_resume_text.py  Extracts PDF text for the RESUME_TEXT secret
├── data/
│   ├── companies.json         164 verified ATS boards (India + global)
│   ├── job_sources.json       6 aggregator API sources
│   ├── answer_bank.example.json  Template — copy to answer_bank.json
│   └── state.json             Dedup state (committed, no personal data)
├── docs/
│   └── index.html             Auto-generated dashboard (GitHub Pages)
├── .github/
│   ├── workflows/
│   │   └── daily-job-alert.yml
│   └── agents/
│       └── personal-job-search.agent.md
├── job-search-profile.md      ← Edit this to tune targeting
├── requirements.txt           pypdf only — no paid API keys needed
└── CLOUD_SETUP.md             Full setup guide
```

---

## Where the jobs come from

### Company ATS boards — 164 boards (`data/companies.json`)

Direct career pages via public JSON APIs. Applying goes straight into the company's hiring pipeline with no aggregator in between.

| ATS | API endpoint pattern | Example companies |
|---|---|---|
| **Greenhouse** | `boards-api.greenhouse.io/v1/boards/{slug}/jobs` | PhonePe, Groww, Postman, HackerRank, DevRev, Anthropic, Databricks, GitLab, Cloudflare, Stripe, Figma, Duolingo … |
| **Lever** | `api.lever.co/v0/postings/{slug}?mode=json` | Paytm, Meesho, CRED, Porter, FamPay, 100ms, Sysdig, JumpCloud … |
| **Ashby** | `api.ashbyhq.com/posting-api/job-board/{slug}` | Sarvam AI, Atlan, Composio, Bureau, OpenAI, Cohere, Perplexity AI, Cursor, LangChain, Supabase, Notion, Zapier, n8n … |
| **SmartRecruiters** | `api.smartrecruiters.com/v1/companies/{slug}/postings` | Swiggy (100+ jobs), Freshworks (100+ jobs), Unacademy, NoBroker |
| **Workable** | `apply.workable.com/api/v3/accounts/{slug}/jobs` | Apna |

**India-tier boards** get a +5 score bonus and are labelled in the dashboard and email.

> **Why not Zomato / Razorpay / Flipkart / TCS?**
> These companies use custom career pages, Workday, or Taleo — none expose a public JSON API.
> Adding them would require a browser scraper, which is a different architecture.

### Aggregator APIs — 6 sources (`data/job_sources.json`)

| Source | Focus |
|---|---|
| RemoteOK | Remote tech jobs worldwide |
| Remotive | Remote tech jobs worldwide |
| Himalayas | Remote jobs, location-filtered |
| Jobicy | Remote jobs |
| Arbeitnow | International remote + EU |
| Hacker News Jobs | HN hiring threads (RSS) |

---

## Scoring

Every job gets a score **0–100**. Daily email threshold: **≥ 60** (falls back to **≥ 45** if fewer than 5 jobs qualify).

| Signal | Points |
|---|---|
| Role matches AI/ML family | +40 |
| Role matches QA/SDET family | +36 |
| Role matches Software/Backend family | +32 |
| Cloud/DevOps family | +24 |
| India location | +28 |
| Open remote | +15 |
| Skill overlap with resume (capped) | up to +25 |
| LLM / agent / GenAI work | +10 |
| India-tier board | +5 |
| Posted within last 7 days | +5 |
| Explicitly junior / associate level | +12 |
| Experience bar ≤ 2 years | +8 |
| Staff / principal / lead / director title | −30 |
| "Senior" / Sr. in title | −20 |
| Internship role | −25 |
| Asks 5+ years experience | −25 |
| Asks 3+ years experience | −12 |
| Remote but US/EU region-fenced | −30 |
| Onsite outside India | −40 |
| Non-technical role (sales, HR, marketing…) | → 0 |

---

## Setup

See **[CLOUD_SETUP.md](CLOUD_SETUP.md)** for the full step-by-step guide. Quick summary:

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Fill in your details

```bash
cp data/answer_bank.example.json data/answer_bank.json
# Edit data/answer_bank.json — this file is gitignored
```

Edit [`job-search-profile.md`](job-search-profile.md) to set your target roles, locations, and skills.

### 3. Extract your resume text for the secret

```bash
python scripts/export_resume_text.py
# Writes resume_text.txt (gitignored) and copies to clipboard
# Paste the output as the RESUME_TEXT GitHub secret
```

### 4. Set GitHub Secrets

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | What to put |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASSWORD` | Gmail **App Password** — Google Account → Security → 2-Step Verification → App passwords |
| `FROM_EMAIL` | Your Gmail address |
| `TO_EMAIL` | Address to deliver the daily alert |
| `RESUME_TEXT` | Plain text from `export_resume_text.py` (~3 KB) |
| `ANSWER_BANK_JSON` | Full contents of `data/answer_bank.json` |

### 5. Enable GitHub Pages

**Settings → Pages → Source → GitHub Actions**, then trigger the workflow once manually.

---

## Running locally

```bash
# Fetch all jobs
python scripts/fetch_jobs.py

# India boards only (faster for testing)
python scripts/fetch_jobs.py --india-only

# Build profile from resume PDF (or RESUME_TEXT env var)
python scripts/job_alert.py build-profile

# Preview the email without sending
python scripts/job_alert.py report --dry-run
# → writes data/email_preview.html

# Send the email
python scripts/job_alert.py report --to you@example.com

# Analyse skill gaps
python scripts/gap_analysis.py

# Rebuild the dashboard
python scripts/build_dashboard.py
```

---

## Tuning

**Target roles / locations / skills** — edit [`job-search-profile.md`](job-search-profile.md). It is the single source of truth; the next run picks up all changes automatically.

**Add a company board** — find its ATS slug, verify it returns JSON, add to [`data/companies.json`](data/companies.json):

```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/<slug>/jobs"        | head -c 300
curl -s "https://api.lever.co/v0/postings/<slug>?mode=json"             | head -c 300
curl -s "https://api.ashbyhq.com/posting-api/job-board/<slug>"          | head -c 300
curl -s "https://api.smartrecruiters.com/v1/companies/<Name>/postings"  | head -c 300
```

**Score threshold** — edit `threshold` and `floor` in `rank_jobs()` in [`scripts/matching.py`](scripts/matching.py).

**Resend all jobs** — Actions → Daily Job Alert → Run workflow → check "Include jobs already emailed before".

---

## Dashboard

The public dashboard (`docs/index.html`, deployed to GitHub Pages) shows:

- All matched jobs with score, reasons, and skill gaps
- Filter by location (India / Remote), minimum score, application status
- Full-text search across role, company, location
- **Skill gap panel** — skills the market keeps asking for that aren't on your resume yet
- **Applied / Interested / Rejected** tracking — stored in `localStorage` only, never published

---

## What is and isn't committed

| Data | Location | In repo? |
|---|---|---|
| Job listings + match scores | `docs/index.html` | ✅ Public — no PII |
| Dedup state (job ID hashes only) | `data/state.json` | ✅ Committed — no PII |
| Resume PDF | Gitignored | ❌ Never |
| Resume plain text | `RESUME_TEXT` secret + `resume_text.txt` (gitignored) | ❌ Never |
| Personal details (phone, email, CTC…) | `ANSWER_BANK_JSON` secret + `data/answer_bank.json` (gitignored) | ❌ Never |
| Application status (Applied / Rejected…) | Browser `localStorage` | ❌ Never leaves your browser |
| Cover note drafts | Email only | ❌ Never |

---

## Secrets you need to update

After any resume change, regenerate and re-paste:

- **`RESUME_TEXT`** — run `python scripts/export_resume_text.py`, copy the output, update the secret
- **`ANSWER_BANK_JSON`** — update `data/answer_bank.json` locally, copy its full contents, update the secret

The other secrets (`SMTP_*`, `FROM_EMAIL`, `TO_EMAIL`) never change unless your email credentials change.

---

## Tech stack

- **Language:** Python 3.12
- **Dependencies:** `pypdf` only — no paid APIs, no OpenAI key, no LLM costs
- **CI/CD:** GitHub Actions (cron daily, manual dispatch)
- **Hosting:** GitHub Pages (free)
- **Email:** Gmail SMTP via App Password
- **Storage:** JSON files in the repo — no database
- **Cost:** ₹0 / $0
