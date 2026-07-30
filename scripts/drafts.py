"""Application drafts: a tailored cover note and answers to standard screening questions.

Deliberately template-based rather than LLM-backed, so the daily run needs no
API key and no budget. The output is a starting point you edit, not something
that gets submitted on your behalf.
"""

from __future__ import annotations

from models import DATA_DIR, MatchResult, load_json

ANSWER_BANK_PATH = DATA_DIR / "answer_bank.json"
ANSWER_BANK_EXAMPLE = DATA_DIR / "answer_bank.example.json"

# Evidence to reach for, picked by what the posting is actually about.
EVIDENCE = {
    "ai": (
        "I built A-MATS, an autonomous multi-agent system that screens NSE stocks, reasons about "
        "trade decisions, executes paper trades and learns from outcomes - scheduled in the cloud "
        "with GitHub Actions and fronted by a live self-updating dashboard, benchmarked against buy-and-hold."
    ),
    "qa": (
        "At Mphasis I design and maintain reusable Appium + TestNG + Java automation frameworks for "
        "Android and iOS, and previously built API test suites with Rest Assured and Cucumber (BDD)."
    ),
    "backend": (
        "I work in Python and Java day to day, have built REST APIs and data pipelines, and recently "
        "shipped an end-to-end automated pipeline for my A-MATS trading agent project."
    ),
    "cloud": (
        "I run my own projects on GitHub Actions - scheduled cloud jobs, automated data pipelines and "
        "a self-updating deployed dashboard - so CI/CD and cloud automation are things I use, not just study."
    ),
}


def load_answer_bank() -> dict:
    bank = load_json(ANSWER_BANK_PATH, None)
    if not isinstance(bank, dict):
        bank = load_json(ANSWER_BANK_EXAMPLE, {})
    return {k: v for k, v in bank.items() if not k.startswith("_")}


def pick_angle(result: MatchResult) -> str:
    text = f"{result.job.role} {result.job.description[:800]}".lower()
    if any(term in text for term in ("ai", "ml", "llm", "agent", "machine learning", "genai")):
        return "ai"
    if any(term in text for term in ("sdet", "qa", "test", "automation", "quality")):
        return "qa"
    if any(term in text for term in ("cloud", "devops", "infrastructure", "sre")):
        return "cloud"
    return "backend"


def cover_note(result: MatchResult, bank: dict) -> str:
    job = result.job
    angle = pick_angle(result)
    skills = ""
    for reason in result.reasons:
        if reason.startswith("Skill overlap: "):
            skills = reason.replace("Skill overlap: ", "")
            break

    lines = [
        f"Subject: Application for {job.role} - {bank.get('full_name', '')}",
        "",
        "Hello,",
        "",
        f"I'd like to apply for the {job.role} role at {job.company}"
        + (f" ({job.location})" if job.location else "")
        + ".",
        "",
        f"I'm currently an {bank.get('current_title', 'engineer')} at {bank.get('current_company', '')} "
        f"with {bank.get('total_experience', '')}, and I hold a B.Tech in AI & ML.",
        "",
        EVIDENCE[angle],
        "",
    ]
    if skills:
        lines += [f"Overlap with what you've listed: {skills}.", ""]
    lines += [
        f"I'm an {bank.get('notice_period', 'immediate joiner').lower()}, so I can start without a handover delay.",
        "",
        "I'd welcome the chance to talk it through.",
        "",
        "Best regards,",
        bank.get("full_name", ""),
        f"{bank.get('phone', '')} | {bank.get('email', '')}",
        bank.get("github", ""),
    ]
    return "\n".join(line for line in lines if line is not None)


def screening_answers(bank: dict) -> list[tuple[str, str]]:
    """Answers to the questions almost every Indian application form asks."""
    return [
        ("Notice period", bank.get("notice_period", "")),
        ("Total experience", bank.get("total_experience", "")),
        ("Current location", bank.get("current_location", "")),
        ("Willing to relocate", bank.get("willing_to_relocate", "")),
        ("Current CTC", bank.get("current_ctc", "")),
        ("Expected CTC", bank.get("expected_ctc", "")),
        ("Work authorisation", bank.get("work_authorization", "")),
        ("Highest qualification", bank.get("highest_qualification", "")),
    ]
