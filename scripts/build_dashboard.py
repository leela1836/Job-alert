"""Generate the public GitHub Pages dashboard.

Everything written here is public, so this module publishes job listings and
match scores only. Personal details and cover-letter drafts stay in the private
email path, and application status is kept in the browser's localStorage so it
is never committed to the repo.
"""

from __future__ import annotations

import argparse
import datetime
import json

from gap_analysis import GAP_REPORT_PATH
from matching import load_preferences, rank_jobs
from models import DOCS_DIR, JOBS_PATH, PROFILE_PATH, STATE_PATH, Job, load_json

PUBLIC_FIELDS = (
    "job_id", "company", "role", "location", "source", "apply_link",
    "posted_at", "tier", "remote", "contact_email",
)


def build_payload(limit: int) -> dict:
    profile = load_json(PROFILE_PATH, None) or load_preferences()
    raw = load_json(JOBS_PATH, [])
    jobs = [Job(**item) for item in raw] if isinstance(raw, list) else []
    state = load_json(STATE_PATH, {})
    emailed = state.get("emailed", {}) if isinstance(state, dict) else {}

    ranked = rank_jobs(jobs, profile, threshold=55, floor=40, limit=limit)
    items = []
    for result in ranked:
        entry = {field: getattr(result.job, field) for field in PUBLIC_FIELDS}
        entry["score"] = result.score
        entry["reasons"] = result.reasons
        entry["missing"] = result.missing
        entry["emailed_on"] = emailed.get(result.job.job_id, "")
        items.append(entry)

    gap_report = load_json(GAP_REPORT_PATH, {})
    if not isinstance(gap_report, dict):
        gap_report = {}

    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "total_scanned": len(jobs),
        "jobs": items,
        "gaps": gap_report.get("gaps", [])[:12],
        "strengths": gap_report.get("strengths", [])[:8],
        "gaps_analysed": gap_report.get("postings_analysed", 0),
    }


TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Job Match Dashboard</title>
<style>
*{box-sizing:border-box}
:root{
  --bg:#f6f7fb; --card:#fff; --ink:#0f172a; --muted:#64748b; --line:#e2e8f0;
  --accent:#4f46e5; --chip:#f1f5f9; --chip-ink:#334155;
}
@media (prefers-color-scheme:dark){
  :root{--bg:#0b1120;--card:#111a2e;--ink:#e6edf7;--muted:#8da2c0;--line:#1f2b45;
        --accent:#818cf8;--chip:#1a2540;--chip-ink:#b6c6e3}
}
:root[data-theme=dark]{--bg:#0b1120;--card:#111a2e;--ink:#e6edf7;--muted:#8da2c0;--line:#1f2b45;
        --accent:#818cf8;--chip:#1a2540;--chip-ink:#b6c6e3}
:root[data-theme=light]{--bg:#f6f7fb;--card:#fff;--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;
        --accent:#4f46e5;--chip:#f1f5f9;--chip-ink:#334155}
body{margin:0;background:var(--bg);color:var(--ink);
     font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 18px 60px}
header{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap}
h1{margin:0;font-size:25px;letter-spacing:-.02em}
.sub{color:var(--muted);font-size:13px;margin-top:5px}
button{font:inherit;cursor:pointer}
.ghost{background:var(--card);border:1px solid var(--line);color:var(--ink);
       padding:7px 13px;border-radius:9px;font-size:13px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:11px;margin:22px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:14px}
.stat b{display:block;font-size:24px;letter-spacing:-.02em}
.stat span{color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.06em}
.controls{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:18px}
input,select{font:inherit;background:var(--card);border:1px solid var(--line);color:var(--ink);
             padding:8px 11px;border-radius:9px}
input[type=search]{flex:1;min-width:210px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-bottom:12px}
.card.done{opacity:.5}
.top{display:flex;gap:14px;align-items:flex-start}
.grow{flex:1;min-width:0}
.co{font-size:12px;color:var(--muted);font-weight:700}
.role{font-size:16.5px;font-weight:750;margin:3px 0 9px;line-height:1.35}
.role a{color:inherit;text-decoration:none}
.role a:hover{color:var(--accent)}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{background:var(--chip);color:var(--chip-ink);border-radius:99px;padding:3px 9px;
      font-size:11px;font-weight:650}
.chip.in{background:#dcfce7;color:#166534}
.chip.rm{background:#e0e7ff;color:#3730a3}
.chip.sent{background:#fef3c7;color:#92400e}
@media (prefers-color-scheme:dark){.chip.in{background:#0d3b23;color:#7ee2ab}.chip.rm{background:#242a5c;color:#b3b9f5}
  .chip.sent{background:#3f2d10;color:#fcd34d}}
.score{min-width:56px;text-align:center;border-radius:12px;padding:9px 7px;color:#fff}
.score b{display:block;font-size:19px;line-height:1}
.score span{font-size:9px;letter-spacing:.08em;opacity:.85}
.why{margin-top:11px;font-size:13px}
.why div{margin:3px 0}
.ok{color:#059669}.gap{color:#d97706}
@media (prefers-color-scheme:dark){.ok{color:#4ade80}.gap{color:#fbbf24}}
.actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px;align-items:center}
.apply{background:var(--accent);color:#fff;text-decoration:none;padding:8px 15px;
       border-radius:9px;font-size:13px;font-weight:700}
.st{border:1px solid var(--line);background:transparent;color:var(--muted);
    padding:6px 11px;border-radius:9px;font-size:12px}
.st.on{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:700}
.empty{text-align:center;color:var(--muted);padding:50px 20px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:22px}
.panel h2{margin:0 0 3px;font-size:15px}
.panel .note{color:var(--muted);font-size:12px;margin-bottom:14px}
.gcols{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:22px}
.gcols h3{margin:0 0 9px;font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
.bar{display:grid;grid-template-columns:118px 1fr 38px;gap:9px;align-items:center;margin:6px 0;font-size:12.5px}
.bar .track{background:var(--chip);border-radius:99px;height:7px;overflow:hidden}
.bar .fill{height:100%;border-radius:99px;background:#d97706}
.bar.good .fill{background:#059669}
.bar .pct{text-align:right;color:var(--muted);font-size:11.5px}
.bar .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
footer{margin-top:26px;text-align:center;color:var(--muted);font-size:11.5px;line-height:1.7}
</style></head><body>
<div class="wrap">
  <header>
    <div>
      <h1>Job Match Dashboard</h1>
      <div class="sub">Updated __GENERATED__ &middot; __TOTAL__ postings scanned</div>
    </div>
    <button class="ghost" id="theme">Theme</button>
  </header>

  <div class="stats" id="stats"></div>

  <div class="panel" id="gapPanel" hidden>
    <h2>Skill demand vs your resume</h2>
    <div class="note" id="gapNote"></div>
    <div class="gcols">
      <div>
        <h3>Missing from your resume</h3>
        <div id="gapList"></div>
      </div>
      <div>
        <h3>Already covered</h3>
        <div id="strList"></div>
      </div>
    </div>
  </div>

  <div class="controls">
    <input type="search" id="q" placeholder="Search role, company, location...">
    <select id="loc">
      <option value="">All locations</option>
      <option value="india">India only</option>
      <option value="remote">Remote</option>
    </select>
    <select id="min">
      <option value="0">Any score</option>
      <option value="70">70+</option>
      <option value="80">80+</option>
      <option value="90">90+</option>
    </select>
    <select id="stf">
      <option value="">All statuses</option>
      <option value="new">Not actioned</option>
      <option value="interested">Interested</option>
      <option value="applied">Applied</option>
      <option value="rejected">Rejected</option>
    </select>
  </div>

  <div id="list"></div>

  <footer>
    Match scores are generated from <code>job-search-profile.md</code>.<br>
    Your Applied / Interested / Rejected marks are stored only in this browser and are never published.
  </footer>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const KEY = 'jobalert.status.v1';
const store = JSON.parse(localStorage.getItem(KEY) || '{}');
const save = () => localStorage.setItem(KEY, JSON.stringify(store));
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colour = s => s >= 85 ? '#059669' : s >= 70 ? '#0284c7' : '#d97706';
const STATUSES = ['interested','applied','rejected'];

const el = {
  list: document.getElementById('list'), stats: document.getElementById('stats'),
  q: document.getElementById('q'), loc: document.getElementById('loc'),
  min: document.getElementById('min'), stf: document.getElementById('stf'),
};

function visible(){
  const q = el.q.value.trim().toLowerCase();
  const loc = el.loc.value, min = +el.min.value, stf = el.stf.value;
  return DATA.jobs.filter(j => {
    if (min && j.score < min) return false;
    if (loc === 'india' && j.tier !== 'india' && !/india|bangalore|bengaluru|hyderabad|chennai|pune|mumbai|gurgaon|gurugram|noida|delhi/i.test(j.location||'')) return false;
    if (loc === 'remote' && !j.remote && !/remote/i.test(j.location||'')) return false;
    if (stf){
      const cur = store[j.job_id] || 'new';
      if (cur !== stf) return false;
    }
    if (q && !(`${j.role} ${j.company} ${j.location} ${j.source}`.toLowerCase().includes(q))) return false;
    return true;
  });
}

function renderStats(){
  const applied = Object.values(store).filter(v => v === 'applied').length;
  const interested = Object.values(store).filter(v => v === 'interested').length;
  const strong = DATA.jobs.filter(j => j.score >= 80).length;
  const india = DATA.jobs.filter(j => j.tier === 'india').length;
  el.stats.innerHTML = [
    [DATA.jobs.length, 'Matches'], [strong, 'Score 80+'], [india, 'India boards'],
    [interested, 'Interested'], [applied, 'Applied'],
  ].map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join('');
}

function render(){
  const rows = visible();
  el.list.innerHTML = rows.length ? rows.map(j => {
    const cur = store[j.job_id] || 'new';
    const chips = [
      j.location ? `<span class="chip">${esc(j.location)}</span>` : '',
      j.tier === 'india' ? '<span class="chip in">India board</span>' : '',
      j.remote ? '<span class="chip rm">Remote</span>' : '',
      j.posted_at ? `<span class="chip">${esc(j.posted_at)}</span>` : '',
      j.emailed_on ? `<span class="chip sent">Emailed ${esc(j.emailed_on)}</span>` : '',
      `<span class="chip">${esc(j.source)}</span>`,
    ].join('');
    const why = (j.reasons||[]).map(r => `<div class="ok">&#10003; ${esc(r)}</div>`).join('')
              + (j.missing||[]).map(m => `<div class="gap">&minus; ${esc(m)}</div>`).join('');
    const mail = j.contact_email
      ? `<a class="st" href="mailto:${esc(j.contact_email)}">${esc(j.contact_email)}</a>` : '';
    const buttons = STATUSES.map(s =>
      `<button class="st ${cur===s?'on':''}" data-id="${esc(j.job_id)}" data-st="${s}">${s[0].toUpperCase()+s.slice(1)}</button>`
    ).join('');
    return `<div class="card ${cur==='rejected'?'done':''}">
      <div class="top">
        <div class="grow">
          <div class="co">${esc(j.company)}</div>
          <div class="role">${j.apply_link?`<a href="${esc(j.apply_link)}" target="_blank" rel="noopener">${esc(j.role)}</a>`:esc(j.role)}</div>
          <div class="chips">${chips}</div>
        </div>
        <div class="score" style="background:${colour(j.score)}"><b>${j.score}</b><span>MATCH</span></div>
      </div>
      <div class="why">${why}</div>
      <div class="actions">
        ${j.apply_link?`<a class="apply" href="${esc(j.apply_link)}" target="_blank" rel="noopener">Apply &rarr;</a>`:''}
        ${buttons}${mail}
      </div>
    </div>`;
  }).join('') : '<div class="empty">No jobs match these filters.</div>';
  renderStats();
}

function renderGaps(){
  if (!DATA.gaps || !DATA.gaps.length) return;
  document.getElementById('gapPanel').hidden = false;
  document.getElementById('gapNote').textContent =
    `Based on ${DATA.gaps_analysed} reachable postings you scored 50+ on. `
    + `Percentages are the share of those postings that mention the skill.`;
  const top = Math.max(...DATA.gaps.map(g => g.share), 1);
  const bar = (name, share, title, good) =>
    `<div class="bar ${good?'good':''}" title="${esc(title)}">
       <span class="nm">${esc(name)}</span>
       <span class="track"><span class="fill" style="width:${Math.round(100*share/top)}%"></span></span>
       <span class="pct">${Math.round(share)}%</span>
     </div>`;
  document.getElementById('gapList').innerHTML =
    DATA.gaps.map(g => bar(g.skill, g.share, (g.companies||[]).join(', '), false)).join('');
  document.getElementById('strList').innerHTML =
    (DATA.strengths||[]).map(s => bar(s.skill, s.share, 'Already on your resume', true)).join('');
}

el.list.addEventListener('click', e => {
  const b = e.target.closest('button[data-st]');
  if (!b) return;
  const id = b.dataset.id, st = b.dataset.st;
  if (store[id] === st) delete store[id]; else store[id] = st;
  save(); render();
});
[el.q, el.loc, el.min, el.stf].forEach(node => node.addEventListener('input', render));

document.getElementById('theme').addEventListener('click', () => {
  const root = document.documentElement;
  const dark = root.dataset.theme === 'dark'
    || (!root.dataset.theme && matchMedia('(prefers-color-scheme:dark)').matches);
  root.dataset.theme = dark ? 'light' : 'dark';
  localStorage.setItem('jobalert.theme', root.dataset.theme);
});
const saved = localStorage.getItem('jobalert.theme');
if (saved) document.documentElement.dataset.theme = saved;

renderGaps();
render();
</script>
</body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the GitHub Pages dashboard")
    parser.add_argument("--limit", type=int, default=120)
    args = parser.parse_args()

    payload = build_payload(args.limit)
    html = (
        TEMPLATE.replace("__GENERATED__", payload["generated_at"])
        .replace("__TOTAL__", f"{payload['total_scanned']:,}")
        .replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
    )

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Dashboard written to {DOCS_DIR / 'index.html'} ({len(payload['jobs'])} jobs)")


if __name__ == "__main__":
    main()
