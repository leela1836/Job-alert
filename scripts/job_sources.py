from __future__ import annotations

import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from job_alert import Job, save_json


@dataclass
class Source:
    name: str
    url: str
    type: str = "rss"
    category: list[str] | None = None
    locations: list[str] | None = None


class SimpleJobHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[tuple[str, str]] = []
        self._current_link = ""
        self._current_text: list[str] = []
        self._in_anchor = False

    def handle_starttag(self, tag: str, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            if href:
                self._in_anchor = True
                self._current_link = href
                self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._in_anchor:
            self._current_text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_anchor:
            title = " ".join(part for part in self._current_text if part).strip()
            if title:
                self.anchors.append((title, self._current_link))
            self._in_anchor = False
            self._current_link = ""
            self._current_text = []


JOB_URL_HINTS = (
    "job",
    "jobs",
    "career",
    "careers",
    "opening",
    "openings",
    "apply",
    "hiring",
    "position",
    "positions",
)


def load_sources(path: Path) -> list[Source]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources: list[Source] = []
    for item in payload:
        sources.append(
            Source(
                name=item.get("name", ""),
                url=item.get("url", ""),
                type=item.get("type", "rss"),
                category=item.get("category") or [],
                locations=item.get("locations") or [],
            )
        )
    return sources


def fetch_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def extract_jobs_from_rss(xml_text: str, source_name: str, source_url: str) -> list[Job]:
    root = ET.fromstring(xml_text)
    jobs: list[Job] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        description = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or source_url).strip()
        if not title:
            continue
        company = title.split("-")[0].strip() if "-" in title else source_name
        jobs.append(
            Job(
                company=company or source_name,
                role=title,
                source=source_name,
                apply_link=link,
                description=description,
            )
        )
    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        summary = (entry.findtext("{http://www.w3.org/2005/Atom}summary") or "").strip()
        link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
        link = link_elem.attrib.get("href", source_url) if link_elem is not None else source_url
        if not title:
            continue
        company = title.split("-")[0].strip() if "-" in title else source_name
        jobs.append(
            Job(
                company=company or source_name,
                role=title,
                source=source_name,
                apply_link=link,
                description=summary,
            )
        )
    return jobs


def extract_jobs_from_html(html_text: str, source: Source) -> list[Job]:
    parser = SimpleJobHtmlParser()
    parser.feed(html_text)
    source_name = source.name
    source_url = source.url
    keywords = [value.lower() for value in (source_name, *(source_name.split()))]
    category_terms = [term.lower() for term in source.category or []]
    locations = [term.lower() for term in source.locations or []]
    return_jobs: list[Job] = []
    for title, href in parser.anchors:
        title_text = title.lower()
        href_text = href.lower()
        if not any(hint in title_text or hint in href_text for hint in JOB_URL_HINTS):
            continue
        absolute_link = urljoin(source_url, href)
        if not absolute_link.startswith("http"):
            continue
        if not any(term in title_text or term in href_text for term in keywords + category_terms + locations):
            # Keep only obviously job-like links for generic web sources.
            if not any(hint in href_text for hint in JOB_URL_HINTS):
                continue
        return_jobs.append(
            Job(
                company=source_name,
                role=title,
                source=source_name,
                apply_link=absolute_link,
                description=title,
            )
        )
    return return_jobs


def collect_jobs(sources: Iterable[Source]) -> list[Job]:
    jobs: list[Job] = []
    ordered_sources = sorted(sources, key=lambda item: 0 if item.type.lower() in {"rss", "atom", "xml"} else 1)
    for source in ordered_sources:
        try:
            payload = fetch_url(source.url)
        except URLError:
            continue
        except Exception:
            continue

        if source.type.lower() in {"rss", "atom", "xml"}:
            jobs.extend(extract_jobs_from_rss(payload, source.name, source.url))
        else:
            jobs.extend(extract_jobs_from_html(payload, source))
    return jobs


def refresh_jobs(source_path: Path, jobs_path: Path) -> list[Job]:
    sources = load_sources(source_path)
    jobs = collect_jobs(sources)
    payload = [job.__dict__ for job in jobs]
    save_json(jobs_path, payload)
    return jobs
