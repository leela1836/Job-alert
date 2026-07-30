"""Personal job search assistant: build a profile, score jobs, email the matches."""

from __future__ import annotations

import argparse
import datetime
import os
import smtplib
from email.message import EmailMessage
from html import escape
from pathlib import Path

from drafts import cover_note, load_answer_bank, screening_answers
from matching import SKILL_VOCAB, count_terms, load_preferences, rank_jobs
from models import (
    BASE_DIR,
    JOBS_PATH,
    PROFILE_PATH,
    STATE_PATH,
    Job,
    MatchResult,
    load_json,
    save_json,
)

DEFAULT_RESUME = BASE_DIR / "Leelamohan_resume.pdf"
DASHBOARD_URL = "https://leela1836.github.io/Job-alert/"


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------

def read_pdf_text(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def resolve_resume_text(resume_path: Path) -> tuple[str, str]:
    """Return (text, where it came from).

    RESUME_TEXT is preferred in CI. The base64 of the PDF is ~117 KB, which
    exceeds GitHub's 48 KB limit for a single secret, and only the extracted
    text is ever used for skill detection anyway.
    """
    from_env = os.environ.get("RESUME_TEXT", "").strip()
    if from_env:
        return from_env, "RESUME_TEXT secret"
    if resume_path.exists():
        return read_pdf_text(resume_path), str(resume_path.name)
    return "", "nothing found"


def build_profile(resume_path: Path) -> dict:
    preferences = load_preferences()
    resume_text, origin = resolve_resume_text(resume_path)
    lowered = resume_text.lower()

    # Word-boundary matched against a known vocabulary, so "ai" no longer
    # matches "email" the way the old substring check did.
    detected = count_terms(lowered, SKILL_VOCAB)
    profile = dict(preferences)
    profile.update(
        {
            "detected_skills": sorted(set(detected + preferences.get("skills", []))),
            "resume_found": bool(resume_text),
            "resume_length": len(resume_text),
            "generated_at": datetime.date.today().isoformat(),
        }
    )
    save_json(PROFILE_PATH, profile)
    print(
        f"Profile saved to {PROFILE_PATH.name}: "
        f"{len(profile['target_roles'])} target roles, "
        f"{len(profile['preferred_locations'])} locations, "
        f"{len(detected)} skills detected (resume source: {origin})"
    )
    if not resume_text:
        print("WARNING: no resume text available - scoring falls back to job-search-profile.md only")
    return profile


# --------------------------------------------------------------------------
# Email rendering
# --------------------------------------------------------------------------

BG = "#0f172a"
CARD = "#ffffff"
BORDER = "#e2e8f0"
INK = "#0f172a"
MUTED = "#64748b"
ACCENT = "#4f46e5"


def score_colour(score: int) -> str:
    if score >= 85:
        return "#059669"
    if score >= 70:
        return "#0284c7"
    return "#d97706"


def format_email_text(results: list[MatchResult], total_jobs: int) -> str:
    if not results:
        return (
            "AI Job Assistant - Daily Matches\n\n"
            f"No new matches today. {total_jobs} postings were scanned; everything "
            "scoring well has already been sent to you previously.\n\n"
            f"Dashboard: {DASHBOARD_URL}\n"
        )

    lines = [
        "AI JOB ASSISTANT - DAILY MATCHES",
        f"{len(results)} new matches out of {total_jobs} postings scanned.",
        f"Dashboard: {DASHBOARD_URL}",
        "=" * 52,
        "",
    ]
    for index, result in enumerate(results, start=1):
        job = result.job
        lines.append(f"{index}. [{result.score}%] {job.role}")
        lines.append(f"   {job.company} | {job.location or 'Location not stated'}")
        for reason in result.reasons:
            lines.append(f"   + {reason}")
        for gap in result.missing:
            lines.append(f"   - {gap}")
        if job.contact_email:
            lines.append(f"   Contact: {job.contact_email}")
        if job.apply_link:
            lines.append(f"   Apply: {job.apply_link}")
        lines.append("")
    return "\n".join(lines)


def _chip(text: str, colour: str, background: str) -> str:
    return (
        f'<span style="display:inline-block;padding:3px 9px;border-radius:99px;'
        f'font-size:11px;font-weight:700;color:{colour};background:{background};'
        f'letter-spacing:.02em;">{escape(text)}</span>'
    )


def _job_card(index: int, result: MatchResult) -> str:
    job = result.job
    colour = score_colour(result.score)
    chips = []
    if job.location:
        chips.append(_chip(job.location[:38], "#334155", "#f1f5f9"))
    if job.tier == "india":
        chips.append(_chip("India board", "#166534", "#dcfce7"))
    if job.remote:
        chips.append(_chip("Remote", "#3730a3", "#e0e7ff"))
    if job.posted_at:
        chips.append(_chip(job.posted_at, "#475569", "#f1f5f9"))

    reasons = "".join(
        f'<div style="font-size:13px;color:#166534;margin:3px 0;">&#10003; {escape(r)}</div>'
        for r in result.reasons
    )
    gaps = "".join(
        f'<div style="font-size:13px;color:#9a3412;margin:3px 0;">&#8722; {escape(g)}</div>'
        for g in result.missing
    )
    contact = ""
    if job.contact_email:
        contact = (
            f'<div style="font-size:13px;margin-top:8px;color:{MUTED};">Published contact: '
            f'<a href="mailto:{escape(job.contact_email)}" style="color:{ACCENT};">'
            f"{escape(job.contact_email)}</a></div>"
        )
    button = ""
    if job.apply_link:
        button = (
            f'<a href="{escape(job.apply_link)}" style="display:inline-block;margin-top:12px;'
            f'padding:9px 18px;background:{ACCENT};color:#ffffff;text-decoration:none;'
            f'border-radius:8px;font-size:13px;font-weight:700;">Apply &rarr;</a>'
        )

    return f"""
    <tr><td style="padding:0 0 14px 0;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="background:{CARD};border:1px solid {BORDER};border-radius:14px;">
        <tr>
          <td style="padding:18px 20px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="vertical-align:top;">
                  <div style="font-size:12px;color:{MUTED};font-weight:700;">#{index} &middot; {escape(job.company)}</div>
                  <div style="font-size:17px;font-weight:800;color:{INK};margin:4px 0 10px 0;line-height:1.35;">
                    {escape(job.role)}
                  </div>
                  <div>{" ".join(chips)}</div>
                </td>
                <td width="64" style="vertical-align:top;text-align:right;">
                  <div style="display:inline-block;min-width:52px;padding:8px 6px;border-radius:12px;
                              background:{colour};color:#ffffff;text-align:center;">
                    <div style="font-size:19px;font-weight:800;line-height:1;">{result.score}</div>
                    <div style="font-size:9px;letter-spacing:.08em;opacity:.85;">MATCH</div>
                  </div>
                </td>
              </tr>
            </table>
            <div style="margin-top:12px;">{reasons}{gaps}</div>
            {contact}
            {button}
          </td>
        </tr>
      </table>
    </td></tr>
    """


def format_email_html(results: list[MatchResult], total_jobs: int, bank: dict) -> str:
    today = datetime.date.today().strftime("%d %b %Y")

    if not results:
        body = (
            f'<tr><td style="background:{CARD};border:1px solid {BORDER};border-radius:14px;'
            f'padding:28px;text-align:center;color:{MUTED};font-size:14px;">'
            f"No new matches today.<br>{total_jobs} postings scanned - everything strong has "
            "already been sent to you.</td></tr>"
        )
        extras = ""
    else:
        body = "".join(_job_card(i, r) for i, r in enumerate(results, start=1))

        notes = ""
        for result in results[:3]:
            notes += (
                f'<div style="margin-bottom:14px;">'
                f'<div style="font-size:13px;font-weight:700;color:{INK};margin-bottom:6px;">'
                f"{escape(result.job.role)} &middot; {escape(result.job.company)}</div>"
                f'<pre style="margin:0;padding:12px;background:#f8fafc;border:1px solid {BORDER};'
                f"border-radius:10px;white-space:pre-wrap;word-wrap:break-word;font-family:ui-monospace,"
                f'Consolas,monospace;font-size:12px;line-height:1.55;color:#334155;">'
                f"{escape(cover_note(result, bank))}</pre></div>"
            )
        answers = "".join(
            f'<tr><td style="padding:5px 10px 5px 0;font-size:12px;color:{MUTED};white-space:nowrap;">'
            f'{escape(q)}</td><td style="padding:5px 0;font-size:12px;color:{INK};font-weight:600;">'
            f"{escape(str(a))}</td></tr>"
            for q, a in screening_answers(bank)
            if a
        )
        extras = f"""
        <tr><td style="padding:20px 0 8px 0;">
          <div style="font-size:13px;font-weight:800;color:#ffffff;letter-spacing:.06em;">READY-TO-SEND COVER NOTES</div>
          <div style="font-size:12px;color:#94a3b8;margin-top:3px;">Top 3 matches. Edit before sending.</div>
        </td></tr>
        <tr><td style="background:{CARD};border:1px solid {BORDER};border-radius:14px;padding:18px;">
          {notes}
        </td></tr>
        <tr><td style="padding:20px 0 8px 0;">
          <div style="font-size:13px;font-weight:800;color:#ffffff;letter-spacing:.06em;">SCREENING ANSWERS</div>
        </td></tr>
        <tr><td style="background:{CARD};border:1px solid {BORDER};border-radius:14px;padding:18px;">
          <table role="presentation" cellpadding="0" cellspacing="0">{answers}</table>
        </td></tr>
        """

    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:{BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};padding:24px 12px;">
<tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;">

    <tr><td style="padding-bottom:20px;">
      <div style="font-size:24px;font-weight:800;color:#ffffff;letter-spacing:-.02em;">
        AI Job Assistant
      </div>
      <div style="font-size:13px;color:#94a3b8;margin-top:5px;">
        {today} &middot; {len(results)} new match{"" if len(results) == 1 else "es"} from {total_jobs} postings scanned
      </div>
      <a href="{DASHBOARD_URL}" style="display:inline-block;margin-top:12px;padding:8px 16px;
         background:rgba(255,255,255,.1);color:#e2e8f0;text-decoration:none;border-radius:8px;
         font-size:12px;font-weight:600;border:1px solid rgba(255,255,255,.15);">Open dashboard &rarr;</a>
    </td></tr>

    {body}
    {extras}

    <tr><td style="padding-top:22px;text-align:center;color:#64748b;font-size:11px;line-height:1.6;">
      Generated by your personal job agent &middot; Python + GitHub Actions<br>
      Jobs already sent to you are never repeated.
    </td></tr>

  </table>
</td></tr>
</table>
</body></html>"""


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------

def send_email(subject: str, text_body: str, html_body: str, to_email: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587") or 587)
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    from_email = os.environ.get("FROM_EMAIL", smtp_user)

    missing = [
        name
        for name, value in [
            ("SMTP_HOST", smtp_host),
            ("SMTP_USER", smtp_user),
            ("SMTP_PASSWORD", smtp_password),
            ("FROM_EMAIL", from_email),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError("Missing SMTP configuration: " + ", ".join(missing))

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(smtp_host, smtp_port, timeout=45) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def load_ranked(only_new: bool, limit: int) -> tuple[list[MatchResult], int, dict]:
    profile = load_json(PROFILE_PATH, None) or load_preferences()
    raw_jobs = load_json(JOBS_PATH, [])
    jobs = [Job(**item) for item in raw_jobs] if isinstance(raw_jobs, list) else []

    state = load_json(STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}
    emailed = state.get("emailed", {})
    if not emailed and isinstance(state.get("seen"), dict):
        # Pre-migration state file; fetch_jobs.py rewrites it on the next run.
        emailed = {
            job_id: entry.get("last_seen", "")
            for job_id, entry in state["seen"].items()
            if isinstance(entry, dict) and entry.get("emailed")
        }

    ranked = rank_jobs(jobs, profile, limit=limit * 3)
    for result in ranked:
        result.first_seen = emailed.get(result.job.job_id, "")
        result.is_new = result.job.job_id not in emailed

    if only_new:
        ranked = [r for r in ranked if r.is_new]
    return ranked[:limit], len(jobs), state


def run_report(to_email: str, only_new: bool, limit: int, dry_run: bool) -> None:
    results, total_jobs, state = load_ranked(only_new, limit)
    bank = load_answer_bank()

    text_body = format_email_text(results, total_jobs)
    html_body = format_email_html(results, total_jobs, bank)
    subject = (
        f"{len(results)} new job match{'' if len(results) == 1 else 'es'} - "
        f"{datetime.date.today().strftime('%d %b')}"
        if results
        else f"No new job matches - {datetime.date.today().strftime('%d %b')}"
    )

    if dry_run:
        preview = BASE_DIR / "data" / "email_preview.html"
        save_json(BASE_DIR / "data" / "email_preview.json", {"subject": subject})
        preview.write_text(html_body, encoding="utf-8")
        print(text_body)
        print(f"\n[dry run] no email sent. HTML preview written to {preview}")
        return

    send_email(subject, text_body, html_body, to_email)
    print(f"Sent {len(results)} matches to {to_email}")

    today = datetime.date.today().isoformat()
    sent = state.setdefault("emailed", {})
    for result in results:
        sent[result.job.job_id] = today
    save_json(STATE_PATH, state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Personal job search assistant")
    parser.add_argument("command", choices=["build-profile", "report"])
    parser.add_argument("--resume", type=Path, default=DEFAULT_RESUME)
    parser.add_argument("--to", default=os.environ.get("TO_EMAIL", ""))
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--all", action="store_true", help="include jobs already emailed")
    parser.add_argument("--dry-run", action="store_true", help="render the email without sending")
    args = parser.parse_args()

    if args.command == "build-profile":
        build_profile(args.resume)
    else:
        if not args.to and not args.dry_run:
            raise SystemExit("No recipient. Pass --to or set TO_EMAIL.")
        run_report(args.to, only_new=not args.all, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
