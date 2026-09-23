"""One-shot audit: imports, config, scoring, data validity. Delete after use."""
import json, sys
from pathlib import Path

results = []

def ok(label, detail=""):
    results.append(("OK  ", label, detail))
    print(f"OK   {label:<35} {detail}")

def fail(label, detail=""):
    results.append(("FAIL", label, detail))
    print(f"FAIL {label:<35} {detail}")

print("=== 1. Imports ===")
try:
    from models import Job, MatchResult, load_json, BASE_DIR, JOBS_PATH, PROFILE_PATH, STATE_PATH, COMPANIES_PATH, SOURCES_PATH
    ok("models.py")
except Exception as e:
    fail("models.py", str(e)); sys.exit(1)

try:
    from sources import ATS_PARSERS, fetch_board, board_url, collect_all
    ok("sources.py", "parsers: " + ", ".join(sorted(ATS_PARSERS.keys())))
except Exception as e:
    fail("sources.py", str(e)); sys.exit(1)

try:
    from matching import load_preferences, rank_jobs, score_job, SKILL_VOCAB, ROLE_FAMILIES
    ok("matching.py", f"vocab={len(SKILL_VOCAB)} skills, {len(ROLE_FAMILIES)} role families")
except Exception as e:
    fail("matching.py", str(e)); sys.exit(1)

try:
    from drafts import load_answer_bank, cover_note, EVIDENCE
    ok("drafts.py", "angles: " + ", ".join(sorted(EVIDENCE.keys())))
except Exception as e:
    fail("drafts.py", str(e)); sys.exit(1)

try:
    from fetch_jobs import load_boards, migrate_state, prune_emailed
    boards = load_boards()
    ats_counts = {}
    for b in boards:
        ats_counts[b["ats"]] = ats_counts.get(b["ats"], 0) + 1
    ok("fetch_jobs.py", f"{len(boards)} boards: {ats_counts}")
except Exception as e:
    fail("fetch_jobs.py", str(e)); sys.exit(1)

try:
    from gap_analysis import GAP_REPORT_PATH, detect, SKILLS
    ok("gap_analysis.py", f"{len(SKILLS)} skills tracked")
except Exception as e:
    fail("gap_analysis.py", str(e)); sys.exit(1)

try:
    from build_dashboard import build_payload, TEMPLATE
    ok("build_dashboard.py")
except Exception as e:
    fail("build_dashboard.py", str(e)); sys.exit(1)

try:
    from job_alert import build_profile, format_email_html, format_email_text
    ok("job_alert.py")
except Exception as e:
    fail("job_alert.py", str(e)); sys.exit(1)

print()
print("=== 2. Profile from job-search-profile.md ===")
prefs = load_preferences()
ok("target_roles", f"{len(prefs['target_roles'])} roles: {prefs['target_roles'][:3]}")
ok("preferred_locations", str(prefs["preferred_locations"]))
ok("skills", f"{len(prefs['skills'])} skills")

print()
print("=== 3. Answer bank ===")
bank = load_answer_bank()
keys = sorted(bank.keys())
ok("answer_bank keys", str(keys))
is_placeholder = bank.get("full_name", "") in ("Your Name", "")
ok("placeholder mode (no PII in repo)", str(is_placeholder))

print()
print("=== 4. companies.json ===")
raw = Path("../data/companies.json").read_text(encoding="utf-8")
data = json.loads(raw)
boards = data["boards"]
india = [b for b in boards if b["tier"] == "india"]
glob  = [b for b in boards if b["tier"] == "global"]
ats_set = set(b["ats"] for b in boards)
missing_parsers = ats_set - set(ATS_PARSERS.keys())
slugkeys = [(b["ats"], b["slug"]) for b in boards]
dupes = set(k for k in slugkeys if slugkeys.count(k) > 1)
ok("total boards", f"{len(boards)} (india={len(india)}, global={len(glob)})")
ok("ATS types", str(sorted(ats_set)))
if missing_parsers:
    fail("missing parsers", str(missing_parsers))
else:
    ok("all ATS parsers present")
if dupes:
    fail("duplicate slugs", str(dupes))
else:
    ok("no duplicate slugs")

print()
print("=== 5. Scoring smoke test ===")
test_jobs = [
    Job(company="Sarvam AI",   role="AI Engineer",              location="Bangalore",      description="python llm agent fastapi", tier="india"),
    Job(company="Swiggy",      role="Software Engineer",         location="Pune, MH, India",description="python rest api mysql backend", tier="india"),
    Job(company="Anthropic",   role="Senior ML Engineer",        location="Remote",         description="machine learning llm pytorch", tier="global"),
    Job(company="Google",      role="Director of Engineering",   location="San Francisco",  description="leadership strategy", tier="global"),
    Job(company="OpenAI",      role="QA Automation Engineer",    location="Remote",         description="selenium pytest api testing", tier="global"),
    Job(company="Accenture",   role="Sales Manager",             location="Mumbai",         description="sales crm", tier="india"),
    Job(company="Porter",      role="Backend Engineer",          location="Bengaluru, India",description="python rest api mysql docker", tier="india"),
    Job(company="Freshworks",  role="Software Engineer",         location="Chennai, India", description="python java backend api", tier="india"),
]
profile = dict(prefs)
profile["detected_skills"] = ["python","java","mysql","rest api","aws","docker","selenium","appium","langchain","yolo"]

print(f"  {'SCORE':<7} {'COMPANY':<20} {'ROLE':<38} TOP REASON")
print(f"  {'-'*5:<7} {'-'*18:<20} {'-'*36:<38} {'-'*25}")
for j in test_jobs:
    r = score_job(j, profile)
    top = r.reasons[0] if r.reasons else (r.missing[0] if r.missing else "-")
    print(f"  [{r.score:3d}]  {j.company:<20} {j.role:<38} {top}")

expected_top = [j for j in test_jobs if j.company in ("Sarvam AI", "Swiggy", "Porter", "Freshworks")]
top_results = sorted([score_job(j, profile) for j in test_jobs], key=lambda x: -x.score)
if top_results[0].job.company in ("Sarvam AI", "Freshworks", "Swiggy", "Porter"):
    ok("India tech jobs rank highest")
else:
    fail("unexpected top rank", top_results[0].job.company)
if score_job(Job(company="X", role="Sales Manager", location="Mumbai", description="sales", tier="india"), profile).score == 0:
    ok("non-technical role correctly filtered to 0")
else:
    fail("non-technical filter broken")

print()
print("=== 6. Workflow CI steps check ===")
import subprocess
# Verify the workflow file references the right scripts
wf = Path("../.github/workflows/daily-job-alert.yml").read_text(encoding="utf-8")
checks = [
    ("fetch_jobs.py in workflow",      "fetch_jobs.py" in wf),
    ("job_alert build-profile",        "build-profile" in wf),
    ("job_alert report",               "job_alert.py report" in wf),
    ("gap_analysis.py in workflow",    "gap_analysis.py" in wf),
    ("build_dashboard.py in workflow", "build_dashboard.py" in wf),
    ("RESUME_TEXT secret used",        "RESUME_TEXT" in wf),
    ("ANSWER_BANK_JSON secret used",   "ANSWER_BANK_JSON" in wf),
    ("state.json committed",           "state.json" in wf),
]
for label, passed in checks:
    ok(label) if passed else fail(label)

print()
failures = [r for r in results if r[0] == "FAIL"]
if failures:
    print(f"RESULT: {len(failures)} FAILURES — fix before pushing")
    sys.exit(1)
else:
    print(f"RESULT: ALL {len(results)} CHECKS PASSED — safe to push")
