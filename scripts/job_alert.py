from __future__ import annotations

import argparse
import json
import os
import smtplib
from dataclasses import dataclass, asdict
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROFILE_PATH = DATA_DIR / "profile.json"
JOBS_PATH = DATA_DIR / "jobs.json"
STATE_PATH = DATA_DIR / "state.json"

DEFAULT_PROFILE = {
    "target_roles": [
        "Python AI Engineer",
        "Agentic AI Engineer",
        "Software Engineer",
        "SDET / Automation Engineer",
    ],
    "preferred_locations": ["Pune", "Mumbai", "Remote"],
    "keywords": ["Python", "AI", "LLM", "Agents", "APIs", "Automation", "QA"],
}


@dataclass
class Job:
    company: str
    role: str
    location: str = ""
    source: str = ""
    apply_link: str = ""
    description: str = ""


@dataclass
class MatchResult:
    job: Job
    score: int
    reasons: list[str]
    missing: list[str]


def read_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def extract_profile_from_resume(resume_text: str) -> dict:
    lowered = resume_text.lower()
    skills = []
    for skill in ["python", "ai", "llm", "agents", "api", "automation", "qa", "pytest", "selenium", "playwright", "sql"]:
        if skill in lowered:
            skills.append(skill)

    summary = resume_text[:1200].strip()
    profile = dict(DEFAULT_PROFILE)
    profile.update(
        {
            "resume_summary": summary,
            "detected_skills": skills,
            "resume_length": len(resume_text),
        }
    )
    return profile


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_jobs(path: Path) -> list[Job]:
    raw_jobs = load_json(path, [])
    jobs: list[Job] = []
    for item in raw_jobs:
        jobs.append(Job(**item))
    return jobs


def score_job(job: Job, profile: dict) -> MatchResult:
    text = f"{job.company} {job.role} {job.location} {job.description}".lower()
    score = 0
    reasons: list[str] = []
    missing: list[str] = []

    target_roles = [role.lower() for role in profile.get("target_roles", [])]
    preferred_locations = [loc.lower() for loc in profile.get("preferred_locations", [])]
    keywords = [kw.lower() for kw in profile.get("keywords", [])]
    detected_skills = [skill.lower() for skill in profile.get("detected_skills", [])]

    if any(role in text for role in target_roles):
        score += 35
        reasons.append("Role matches a target title")

    if any(loc in text for loc in preferred_locations):
        score += 20
        reasons.append("Location matches preference")

    matched_keywords = [kw for kw in keywords if kw in text or kw in detected_skills]
    if matched_keywords:
        score += min(35, len(matched_keywords) * 7)
        reasons.append(f"Matches keywords: {', '.join(matched_keywords[:5])}")

    if "qa" in text or "automation" in text or "selenium" in text or "playwright" in text:
        score += 10
        reasons.append("Contains QA/automation signals")
    if "ai" in text or "llm" in text or "agent" in text:
        score += 10
        reasons.append("Contains AI/agent signals")

    if "cloud" not in text and "aws" not in text and "azure" not in text:
        missing.append("cloud deployment experience")
    if "testing" not in text and "qa" not in text:
        missing.append("testing emphasis")

    score = max(0, min(100, score))
    return MatchResult(job=job, score=score, reasons=reasons[:4], missing=missing[:3])


def filter_jobs(jobs: Iterable[Job], profile: dict, threshold: int = 70) -> list[MatchResult]:
    results = [score_job(job, profile) for job in jobs]
    return sorted((result for result in results if result.score >= threshold), key=lambda item: item.score, reverse=True)


def format_email(results: list[MatchResult]) -> str:
    if not results:
        return "No strong matches found today."

    lines = [f"Top AI/QA jobs for you: {len(results)} matches", ""]
    for index, result in enumerate(results[:10], start=1):
        job = result.job
        lines.append(f"{index}. {job.company} - {job.role}")
        lines.append(f"   Location: {job.location or 'N/A'}")
        lines.append(f"   Match: {result.score}%")
        if result.reasons:
            lines.append(f"   Why: {', '.join(result.reasons)}")
        if result.missing:
            lines.append(f"   Missing: {', '.join(result.missing)}")
        if job.apply_link:
            lines.append(f"   Apply: {job.apply_link}")
        lines.append("")
    return "\n".join(lines).rstrip()


def send_email(subject: str, body: str, to_email: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    from_email = os.environ.get("FROM_EMAIL", smtp_user)

    if not smtp_host or not smtp_user or not smtp_password or not from_email:
        raise RuntimeError("Missing SMTP configuration. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, and FROM_EMAIL.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)


def build_profile(resume_path: Path) -> None:
    resume_text = read_pdf_text(resume_path)
    profile = extract_profile_from_resume(resume_text)
    save_json(PROFILE_PATH, profile)
    print(f"Saved profile to {PROFILE_PATH}")


def run_report(to_email: str) -> None:
    profile = load_json(PROFILE_PATH, DEFAULT_PROFILE)
    jobs = load_jobs(JOBS_PATH)
    matches = filter_jobs(jobs, profile)
    body = format_email(matches)
    send_email("Top AI and QA Jobs for You", body, to_email)
    print(f"Sent report to {to_email}")


def init_sample_jobs() -> None:
    sample_jobs = [
        {
            "company": "Example AI Labs",
            "role": "Python AI Engineer - LLM Agents",
            "location": "Remote",
            "source": "Sample",
            "apply_link": "https://example.com/apply",
            "description": "Build AI agents, APIs, and automation workflows using Python and LLMs.",
        },
        {
            "company": "QA Systems",
            "role": "SDET Automation Engineer",
            "location": "Pune",
            "source": "Sample",
            "apply_link": "https://example.com/apply2",
            "description": "Automate regression testing with Playwright, Python, and CI/CD.",
        },
    ]
    save_json(JOBS_PATH, sample_jobs)
    print(f"Saved sample jobs to {JOBS_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Personal job search assistant")
    parser.add_argument("command", choices=["build-profile", "sample-jobs", "report"])
    parser.add_argument("--resume", type=Path, default=BASE_DIR / "Chemuru_Leelamohan_Resume.pdf")
    parser.add_argument("--to", default="mohan.leelachemuru@gmail.com")
    args = parser.parse_args()

    if args.command == "build-profile":
        build_profile(args.resume)
    elif args.command == "sample-jobs":
        init_sample_jobs()
    elif args.command == "report":
        run_report(args.to)


if __name__ == "__main__":
    main()
