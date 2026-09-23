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
        "I built A-MATS, an autonomous AI-powered trading platform in Python that analyses NSE stocks, "
        "generates trade decisions, executes paper trades and tracks portfolio performance - orchestrated "
        "on GitHub Actions with a live self-updating dashboard. I also built an image classification "
        "solution using YOLO + MySQL for automated defect detection, and a recommendation engine with "
        "Pandas, NumPy and Scikit-learn."
    ),
    "qa": (
        "During my internship at Mphasis I implemented automated API validation frameworks using Java, "
        "Rest Assured and Cucumber BDD, and validated REST APIs, JSON payloads and SQL queries against "
        "backend services following Page Object Model principles."
    ),
    "backend": (
        "At Mphasis I engineer Python-based backend components for financial transaction processing, "
        "validation and workflow orchestration, design REST APIs for service-to-service communication, "
        "and use MySQL for data validation and query optimisation - all in Linux/Agile environments."
    ),
    "cloud": (
        "I use AWS (EC2, S3, IAM, CloudWatch), Docker and GitHub Actions in my own projects - including "
        "A-MATS, which runs scheduled cloud workflows multiple times daily and deploys a live dashboard. "
        "CI/CD and cloud automation are things I actively build with, not just study."
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
