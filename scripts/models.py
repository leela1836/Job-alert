"""Shared data types and small helpers used across the job alert pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from html import unescape
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"

PROFILE_PATH = DATA_DIR / "profile.json"
JOBS_PATH = DATA_DIR / "jobs.json"
STATE_PATH = DATA_DIR / "state.json"
COMPANIES_PATH = DATA_DIR / "companies.json"
SOURCES_PATH = DATA_DIR / "job_sources.json"
PREFERENCES_PATH = BASE_DIR / "job-search-profile.md"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Turn an HTML job description into flat text suitable for scoring and email."""
    if not text:
        return ""
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6])\s*/?>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    text = unescape(text)
    lines = [_WS_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Addresses that show up in tracking pixels, asset URLs and boilerplate rather
# than as a real invitation to apply.
_EMAIL_NOISE = (
    "sentry.io", "example.com", "noreply", "no-reply", "donotreply", "wixpress",
    ".png", ".jpg", ".gif", "@2x", "your-email", "email@",
)


def extract_contact_email(text: str) -> str:
    """Return a contact address the posting itself published, if any.

    Deliberately limited to addresses printed in the job description - that is
    an explicit invitation to get in touch. We do not guess address patterns or
    look people up in third-party databases.
    """
    for candidate in _EMAIL_RE.findall(text or ""):
        lowered = candidate.lower()
        if not any(noise in lowered for noise in _EMAIL_NOISE):
            return candidate
    return ""


def make_job_id(company: str, role: str, location: str) -> str:
    """Stable identity for a posting.

    Hashed on content rather than URL: ATS links frequently change their
    tracking parameters, which would otherwise resurface the same job daily.
    """
    raw = f"{company.strip().lower()}|{role.strip().lower()}|{location.strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class Job:
    company: str
    role: str
    location: str = ""
    source: str = ""
    apply_link: str = ""
    description: str = ""
    posted_at: str = ""
    ats: str = ""
    tier: str = ""
    remote: bool = False
    contact_email: str = ""
    job_id: str = ""

    def __post_init__(self) -> None:
        if not self.job_id:
            self.job_id = make_job_id(self.company, self.role, self.location)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchResult:
    job: Job
    score: int
    reasons: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    is_new: bool = True
    first_seen: str = ""


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default
