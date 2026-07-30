"""Preference loading and job scoring.

`job-search-profile.md` is the single source of truth for targeting. The old
code kept a hardcoded DEFAULT_PROFILE that disagreed with that file, so edits to
the markdown had no effect on what actually got emailed.
"""

from __future__ import annotations

import datetime
import re

from models import Job, MatchResult, PREFERENCES_PATH

# Word-boundary matching. The previous implementation used `term in text`, so
# "ai" matched "email" and "maintained", inflating every score.
def has_term(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9+#]){re.escape(term.lower())}(?![a-z0-9+#])", text) is not None


def count_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if has_term(text, term)]


# --------------------------------------------------------------------------
# Preferences
# --------------------------------------------------------------------------

def extract_section_bullets(markdown: str, heading: str) -> list[str]:
    """Collect '- ' bullets under a heading, including any sub-headings."""
    lines = markdown.splitlines()
    target = heading.strip().lower()
    bullets: list[str] = []
    depth = None
    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match:
            level, title = len(match.group(1)), match.group(2).strip().lower()
            if depth is None:
                if title == target:
                    depth = level
            elif level <= depth:
                break
            continue
        if depth is not None:
            bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
            if bullet:
                value = bullet.group(1).strip()
                if value:
                    bullets.append(value)
    return bullets


def load_preferences() -> dict:
    markdown = PREFERENCES_PATH.read_text(encoding="utf-8") if PREFERENCES_PATH.exists() else ""
    roles = extract_section_bullets(markdown, "Target Roles")
    locations = extract_section_bullets(markdown, "Preferred Locations")
    skills = extract_section_bullets(markdown, "Core Skills")
    return {
        "target_roles": roles or ["AI Engineer", "Software Engineer", "SDET"],
        "preferred_locations": locations or ["Bangalore", "Hyderabad", "Pune", "Remote"],
        "skills": [s.lower() for s in skills],
    }


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

ROLE_FAMILIES: list[tuple[int, str, list[str]]] = [
    (40, "AI/ML engineering", [
        "ai engineer", "ml engineer", "machine learning engineer", "llm engineer",
        "agentic", "generative ai", "genai", "nlp engineer", "applied scientist",
        "ai/ml", "deep learning", "research engineer", "ai developer",
    ]),
    (36, "QA automation / SDET", [
        "sdet", "automation engineer", "test engineer", "qa engineer",
        "quality engineer", "automation tester", "test automation", "qa automation",
    ]),
    (32, "Software / backend", [
        "software engineer", "software developer", "backend engineer", "backend developer",
        "python developer", "full stack", "fullstack", "sde", "application engineer",
        "platform engineer", "api engineer",
    ]),
    (24, "Cloud / DevOps", [
        "cloud engineer", "devops", "site reliability", "sre", "infrastructure engineer",
    ]),
]

INDIA_CITIES = [
    "bangalore", "bengaluru", "hyderabad", "chennai", "pune", "mumbai",
    "gurgaon", "gurugram", "noida", "delhi", "india",
]

SKILL_VOCAB = [
    "python", "java", "typescript", "javascript", "react", "node.js", "node", "express",
    "sql", "mongodb", "rest api", "api", "git", "github actions", "postman",
    "appium", "selenium", "testng", "cucumber", "rest assured", "webdriver", "playwright",
    "pytest", "junit", "bdd", "ci/cd", "agile", "oop", "data structures",
    "machine learning", "deep learning", "llm", "langchain", "pandas", "scikit-learn",
    "numpy", "pytorch", "tensorflow", "yolo", "docker", "kubernetes", "aws", "azure", "gcp",
]

SENIOR_MARKERS = ["staff", "principal", "lead ", "head of", "director", "vp ", "manager", "architect", "distinguished"]
# Tracked separately: "senior" is a soft no for a 0-2 year candidate, while
# staff/principal/director are effectively unreachable.
MID_SENIOR_MARKERS = ["senior", "sr.", "sr ", "ii", "iii", "specialist"]

# Anywhere that is not India and not open-remote. A posting in Krakow or New
# York is not actionable, so it is pushed below everything reachable.
FOREIGN_MARKERS = [
    "united states", "usa", "u.s.", "new york", "san francisco", "seattle", "austin",
    "boston", "chicago", "denver", "atlanta", "los angeles", "palo alto", "mountain view",
    "canada", "toronto", "vancouver", "united kingdom", "london", "manchester",
    "ireland", "dublin", "germany", "berlin", "munich", "france", "paris",
    "netherlands", "amsterdam", "spain", "madrid", "barcelona", "portugal", "lisbon",
    "poland", "krakow", "kraków", "warsaw", "romania", "bucharest", "sweden", "stockholm",
    "switzerland", "zurich", "italy", "milan", "australia", "sydney", "melbourne",
    "singapore", "japan", "tokyo", "korea", "seoul", "china", "shanghai", "hong kong",
    "brazil", "sao paulo", "mexico", "argentina", "latam", "israel", "tel aviv",
    "dubai", "uae", "abu dhabi", "europe", "emea", "north america", "nyc",
]

# Remote, but fenced to a region we cannot work from.
REMOTE_RESTRICTIONS = [
    "us only", "usa only", "united states only", "us-based", "must be located in the us",
    "eu only", "uk only", "eligible to work in the united states", "pst", "est", "cst",
    "authorized to work in the us", "work authorization in the us", "us citizens",
]
JUNIOR_MARKERS = [
    "junior", "associate", "entry level", "entry-level", "graduate", "trainee",
    "fresher", "campus", "sde i", "sde-i", "sde 1", "sde-1", "engineer i", "engineer - i",
    "engineer 1", "new grad", "early career", "apprentice",
]
NON_TECHNICAL = [
    "sales", "marketing", "recruiter", "recruiting", "talent acquisition", "human resources",
    "accountant", "finance manager", "legal counsel", "paralegal", "customer success",
    "account executive", "business development", "copywriter", "content writer",
    "graphic designer", "social media", "hr business partner",
]
YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:-\s*\d+\s*)?year")
REMOTE_WORDS_RE = re.compile(
    r"\b(remote|anywhere|worldwide|global|globally|flexible|hybrid|on-?site|in-?office|work from home|wfh|distributed)\b"
)


def _job_text(job: Job) -> str:
    return f"{job.role} {job.location} {job.description}".lower()


def classify_location(job: Job) -> str:
    """Bucket a posting into india / remote_open / remote_restricted / foreign.

    Order matters: an explicit India mention always wins, so "Remote - India"
    and "Bangalore, India" are treated as reachable even though the string also
    contains the word "remote".
    """
    location = job.location.lower()
    if any(has_term(location, city) for city in INDIA_CITIES):
        return "india"

    is_remote = job.remote or has_term(location, "remote") or has_term(location, "anywhere")
    if is_remote:
        window = f"{location} {job.description[:600].lower()}"
        if any(marker in window for marker in REMOTE_RESTRICTIONS):
            return "remote_restricted"
        # Whitelist rather than blacklist: strip the words that mean "remote"
        # and see whether a place name is left over. Feeds name regions in
        # their own language ("Polska") and often arrive mojibaked, so
        # enumerating foreign place names does not scale.
        residue = re.sub(r"[^a-z ]+", " ", REMOTE_WORDS_RE.sub(" ", location))
        if residue.split():
            return "remote_restricted"
        return "remote_open"

    if any(has_term(location, marker) for marker in FOREIGN_MARKERS):
        return "foreign"
    return "foreign" if location else "remote_open"


def score_job(job: Job, profile: dict) -> MatchResult:
    title = job.role.lower()
    text = _job_text(job)
    haystack = f"{title} {job.location.lower()}"

    score = 0
    reasons: list[str] = []
    missing: list[str] = []

    # --- Hard exclusions -------------------------------------------------
    for term in NON_TECHNICAL:
        if has_term(title, term):
            return MatchResult(job=job, score=0, reasons=["Non-technical role"], missing=[])

    # --- Role family -----------------------------------------------------
    best_points, best_label = 0, ""
    for points, label, terms in ROLE_FAMILIES:
        if any(term in title for term in terms):
            if points > best_points:
                best_points, best_label = points, label
    if best_points:
        score += best_points
        reasons.append(f"Role fits {best_label}")
    else:
        # Weaker signal: the target role list from the profile markdown.
        target_hits = [r for r in profile.get("target_roles", []) if r.lower() in title]
        if target_hits:
            score += 22
            reasons.append(f"Matches target role: {target_hits[0]}")
        else:
            missing.append("role title is outside your target families")

    # --- Location --------------------------------------------------------
    preferred = [loc.lower() for loc in profile.get("preferred_locations", [])]
    location_kind = classify_location(job)
    if location_kind == "india":
        city_hits = [c for c in INDIA_CITIES if has_term(haystack, c)]
        named = next((c for c in city_hits if c in preferred), city_hits[0] if city_hits else "India")
        score += 28
        reasons.append(f"Location matches: {named.title()}")
    elif location_kind == "remote_open":
        score += 15
        reasons.append("Open remote")
    elif location_kind == "remote_restricted":
        score -= 30
        missing.append("remote but fenced to a US/EU region")
    else:
        score -= 40
        missing.append(f"onsite outside India ({job.location or 'unspecified'})")

    # --- Seniority fit (0-2 years) --------------------------------------
    if any(marker in title for marker in SENIOR_MARKERS):
        score -= 30
        missing.append("role targets staff/lead seniority")
    elif any(has_term(title, marker.strip()) for marker in MID_SENIOR_MARKERS):
        score -= 20
        missing.append("role targets senior level")
    elif any(marker in title for marker in JUNIOR_MARKERS):
        score += 12
        reasons.append("Explicitly junior/associate level")
    if has_term(title, "intern") or has_term(title, "internship"):
        score -= 25
        missing.append("internship, not a full-time role")

    # Calibrated for ~8 months of professional experience: 3+ years is already
    # a stretch, 5+ is effectively a filter.
    years = [int(y) for y in YEARS_RE.findall(text)[:4]]
    if years:
        asked = min(years)
        if asked >= 5:
            score -= 25
            missing.append(f"asks for {asked}+ years experience")
        elif asked >= 3:
            score -= 12
            missing.append(f"asks for {asked}+ years (you have ~8 months)")
        else:
            score += 8
            reasons.append(f"Experience bar is low ({asked}+ years)")

    # --- Skill overlap ---------------------------------------------------
    resume_skills = profile.get("detected_skills") or SKILL_VOCAB
    matched = count_terms(text, [s for s in resume_skills if len(s) > 1])
    if matched:
        score += min(25, len(matched) * 4)
        reasons.append("Skill overlap: " + ", ".join(matched[:6]))
    if not matched:
        missing.append("no overlapping skills detected in the posting")

    # --- Bonuses ---------------------------------------------------------
    if any(has_term(text, t) for t in ["llm", "agent", "agentic", "rag", "genai", "generative ai"]):
        score += 10
        reasons.append("Involves LLM / agent work")

    if job.tier == "india":
        score += 5

    if job.posted_at:
        try:
            posted = datetime.date.fromisoformat(job.posted_at[:10])
            if (datetime.date.today() - posted).days <= 7:
                score += 5
                reasons.append("Posted within the last week")
        except ValueError:
            pass

    score = max(0, min(100, score))
    return MatchResult(job=job, score=score, reasons=reasons[:5], missing=missing[:3])


def rank_jobs(
    jobs: list[Job],
    profile: dict,
    threshold: int = 60,
    floor: int = 45,
    minimum_results: int = 5,
    limit: int = 25,
) -> list[MatchResult]:
    """Rank and cut.

    If too few jobs clear `threshold`, fall back toward `floor` so the daily
    email is never empty just because it was a quiet day.
    """
    results = sorted((score_job(job, profile) for job in jobs), key=lambda r: r.score, reverse=True)
    strong = [r for r in results if r.score >= threshold]
    if len(strong) < minimum_results:
        strong = [r for r in results if r.score >= floor][:minimum_results]
    return strong[:limit]
