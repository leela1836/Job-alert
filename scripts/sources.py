"""Job source adapters.

Every adapter normalises a provider's payload into a list of `Job`. Failures are
collected and reported rather than swallowed: a source that breaks should look
different from a source that legitimately has no jobs.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from models import Job, extract_contact_email, strip_html

USER_AGENT = "Mozilla/5.0 (compatible; personal-job-alert/1.0; +https://github.com/leela1836/Job-alert)"
TIMEOUT = 25
ATOM = "{http://www.w3.org/2005/Atom}"


@dataclass
class FetchReport:
    name: str
    ok: bool
    count: int = 0
    error: str = ""

    def line(self) -> str:
        status = "OK  " if self.ok else "FAIL"
        detail = f"{self.count} jobs" if self.ok else self.error
        return f"[{status}] {self.name:<28} {detail}"


def fetch_raw(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", errors="ignore")


def fetch_json(url: str) -> object:
    return json.loads(fetch_raw(url))


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


# --------------------------------------------------------------------------
# Applicant tracking systems (per-company boards)
# --------------------------------------------------------------------------

def board_url(ats: str, slug: str) -> str:
    return {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        "lever": f"https://api.lever.co/v0/postings/{slug}?mode=json",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
    }[ats]


def parse_greenhouse(payload: object, company: str, tier: str, slug: str = "") -> list[Job]:
    jobs = []
    for item in (payload or {}).get("jobs", []) if isinstance(payload, dict) else []:
        title = _text(item.get("title"))
        if not title:
            continue
        location = _text((item.get("location") or {}).get("name"))
        job_ref = item.get("id")
        jobs.append(
            Job(
                company=company,
                role=title,
                location=location,
                source=f"{company} (Greenhouse)",
                apply_link=_text(item.get("absolute_url")),
                description="",
                posted_at=_text(item.get("updated_at"))[:10],
                ats="greenhouse",
                tier=tier,
                remote="remote" in location.lower(),
                # The list endpoint omits descriptions; this is where the full
                # posting lives if we later decide we need it.
                detail_url=(
                    f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_ref}"
                    if slug and job_ref
                    else ""
                ),
            )
        )
    return jobs


def parse_lever(payload: object, company: str, tier: str, slug: str = "") -> list[Job]:
    jobs = []
    for item in payload if isinstance(payload, list) else []:
        title = _text(item.get("text"))
        if not title:
            continue
        categories = item.get("categories") or {}
        location = _text(categories.get("location"))
        # Lever ships the full description inline, so no detail fetch is needed.
        description = _text(item.get("descriptionPlain")) or strip_html(_text(item.get("description")))
        posted = item.get("createdAt")
        posted_at = ""
        if isinstance(posted, (int, float)):
            import datetime

            posted_at = datetime.datetime.utcfromtimestamp(posted / 1000).strftime("%Y-%m-%d")
        jobs.append(
            Job(
                company=company,
                role=title,
                location=location,
                source=f"{company} (Lever)",
                apply_link=_text(item.get("hostedUrl")) or _text(item.get("applyUrl")),
                description=description,
                posted_at=posted_at,
                ats="lever",
                tier=tier,
                remote="remote" in f"{location} {categories.get('commitment', '')}".lower(),
            )
        )
    return jobs


def parse_ashby(payload: object, company: str, tier: str, slug: str = "") -> list[Job]:
    jobs = []
    for item in (payload or {}).get("jobs", []) if isinstance(payload, dict) else []:
        title = _text(item.get("title"))
        if not title:
            continue
        location = _text(item.get("location"))
        description = _text(item.get("descriptionPlain")) or strip_html(_text(item.get("descriptionHtml")))
        jobs.append(
            Job(
                company=company,
                role=title,
                location=location,
                source=f"{company} (Ashby)",
                apply_link=_text(item.get("jobUrl")) or _text(item.get("applyUrl")),
                description=description,
                posted_at=_text(item.get("publishedAt"))[:10],
                ats="ashby",
                tier=tier,
                remote=bool(item.get("isRemote")) or "remote" in location.lower(),
            )
        )
    return jobs


ATS_PARSERS = {"greenhouse": parse_greenhouse, "lever": parse_lever, "ashby": parse_ashby}


def fetch_board(board: dict) -> tuple[list[Job], FetchReport]:
    ats = board.get("ats", "")
    slug = board.get("slug", "")
    name = board.get("name", slug)
    tier = board.get("tier", "global")
    if ats not in ATS_PARSERS:
        return [], FetchReport(name, False, error=f"unknown ats '{ats}'")
    try:
        payload = fetch_json(board_url(ats, slug))
        jobs = ATS_PARSERS[ats](payload, name, tier, slug)
        return jobs, FetchReport(name, True, len(jobs))
    except urllib.error.HTTPError as exc:
        return [], FetchReport(name, False, error=f"HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001 - report, never hide
        return [], FetchReport(name, False, error=f"{type(exc).__name__}: {str(exc)[:60]}")


def fetch_greenhouse_description(job: Job) -> str:
    """Greenhouse omits descriptions from the list endpoint.

    Only called for shortlisted jobs so we do not pull megabytes of HTML for
    hundreds of postings we are going to discard anyway.
    """
    if not job.detail_url:
        return ""
    try:
        payload = fetch_json(job.detail_url)
        return strip_html(_text((payload or {}).get("content")))
    except Exception:  # noqa: BLE001
        return ""


# --------------------------------------------------------------------------
# Aggregator APIs
# --------------------------------------------------------------------------

def parse_remoteok(payload: object, name: str) -> list[Job]:
    jobs = []
    for item in payload if isinstance(payload, list) else []:
        # The first element is a legal disclaimer, not a job.
        if not isinstance(item, dict) or not item.get("position"):
            continue
        jobs.append(
            Job(
                company=_text(item.get("company")) or name,
                role=_text(item.get("position")),
                location=_text(item.get("location")) or "Remote",
                source=name,
                apply_link=_text(item.get("apply_url")) or _text(item.get("url")),
                description=strip_html(_text(item.get("description")))
                or " ".join(item.get("tags") or []),
                posted_at=_text(item.get("date"))[:10],
                remote=True,
            )
        )
    return jobs


def parse_arbeitnow(payload: object, name: str) -> list[Job]:
    jobs = []
    for item in (payload or {}).get("data", []) if isinstance(payload, dict) else []:
        title = _text(item.get("title"))
        if not title:
            continue
        jobs.append(
            Job(
                company=_text(item.get("company_name")) or name,
                role=title,
                location=_text(item.get("location")),
                source=name,
                apply_link=_text(item.get("url")),
                description=strip_html(_text(item.get("description"))),
                remote=bool(item.get("remote")),
            )
        )
    return jobs


def parse_remotive(payload: object, name: str) -> list[Job]:
    jobs = []
    for item in (payload or {}).get("jobs", []) if isinstance(payload, dict) else []:
        title = _text(item.get("title"))
        if not title:
            continue
        jobs.append(
            Job(
                company=_text(item.get("company_name")) or name,
                role=title,
                location=_text(item.get("candidate_required_location")) or "Remote",
                source=name,
                apply_link=_text(item.get("url")),
                description=strip_html(_text(item.get("description"))),
                posted_at=_text(item.get("publication_date"))[:10],
                remote=True,
            )
        )
    return jobs


def parse_himalayas(payload: object, name: str) -> list[Job]:
    jobs = []
    for item in (payload or {}).get("jobs", []) if isinstance(payload, dict) else []:
        title = _text(item.get("title"))
        if not title:
            continue
        restrictions = item.get("locationRestrictions") or []
        location = ", ".join(str(r) for r in restrictions) if restrictions else "Remote"
        jobs.append(
            Job(
                company=_text(item.get("companyName")) or name,
                role=title,
                location=location,
                source=name,
                apply_link=_text(item.get("applicationLink")) or _text(item.get("guid")),
                description=strip_html(_text(item.get("description")) or _text(item.get("excerpt"))),
                remote=True,
            )
        )
    return jobs


def parse_jobicy(payload: object, name: str) -> list[Job]:
    jobs = []
    for item in (payload or {}).get("jobs", []) if isinstance(payload, dict) else []:
        title = _text(item.get("jobTitle"))
        if not title:
            continue
        jobs.append(
            Job(
                company=_text(item.get("companyName")) or name,
                role=title,
                location=_text(item.get("jobGeo")) or "Remote",
                source=name,
                apply_link=_text(item.get("url")),
                description=strip_html(_text(item.get("jobDescription")) or _text(item.get("jobExcerpt"))),
                posted_at=_text(item.get("pubDate"))[:10],
                remote=True,
            )
        )
    return jobs


def parse_rss(payload: str, name: str, source_url: str) -> list[Job]:
    root = ET.fromstring(payload)
    jobs = []
    entries = [(item, "") for item in root.findall(".//item")]
    entries += [(entry, ATOM) for entry in root.findall(f".//{ATOM}entry")]
    for node, ns in entries:
        title = _text(node.findtext(f"{ns}title"))
        if not title:
            continue
        if ns:
            link_node = node.find(f"{ns}link")
            link = link_node.attrib.get("href", source_url) if link_node is not None else source_url
            body = _text(node.findtext(f"{ns}summary"))
        else:
            link = _text(node.findtext("link")) or source_url
            body = _text(node.findtext("description"))
        company = title.split(" - ")[0].strip() if " - " in title else name
        jobs.append(
            Job(
                company=company or name,
                role=title,
                source=name,
                apply_link=link,
                description=strip_html(body),
            )
        )
    return jobs


API_PARSERS = {
    "remoteok": parse_remoteok,
    "arbeitnow": parse_arbeitnow,
    "remotive": parse_remotive,
    "himalayas": parse_himalayas,
    "jobicy": parse_jobicy,
}


def fetch_source(source: dict) -> tuple[list[Job], FetchReport]:
    name = source.get("name", "?")
    url = source.get("url", "")
    kind = source.get("type", "rss")
    try:
        if kind in API_PARSERS:
            jobs = API_PARSERS[kind](fetch_json(url), name)
        elif kind in {"rss", "atom", "xml"}:
            jobs = parse_rss(fetch_raw(url), name, url)
        else:
            return [], FetchReport(name, False, error=f"unknown type '{kind}'")
        return jobs, FetchReport(name, True, len(jobs))
    except urllib.error.HTTPError as exc:
        return [], FetchReport(name, False, error=f"HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        return [], FetchReport(name, False, error=f"{type(exc).__name__}: {str(exc)[:60]}")


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def collect_all(boards: list[dict], sources: list[dict], workers: int = 12) -> tuple[list[Job], list[FetchReport]]:
    tasks: list = [("board", board) for board in boards] + [("source", source) for source in sources]

    def run(task):
        kind, payload = task
        return fetch_board(payload) if kind == "board" else fetch_source(payload)

    jobs: list[Job] = []
    reports: list[FetchReport] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for found, report in executor.map(run, tasks):
            jobs.extend(found)
            reports.append(report)

    # Collapse duplicates that appear on several boards at once.
    unique: dict[str, Job] = {}
    for job in jobs:
        existing = unique.get(job.job_id)
        if existing is None or (not existing.description and job.description):
            unique[job.job_id] = job

    for job in unique.values():
        if not job.contact_email:
            job.contact_email = extract_contact_email(job.description)
    return list(unique.values()), reports
