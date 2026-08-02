#!/usr/bin/env python3
"""Self-contained HTML overview of the submission pipeline.

Written to disk and opened locally — the data (unpublished manuscripts,
journal IDs, reviewer letters) never leaves the machine.
"""

import html
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sm_lib as L  # noqa: E402

# Pipeline columns, left to right.
LANES = [
    ("drafting", "Írás alatt", ["drafting"]),
    ("ready", "Kész, nincs beküldve", ["ready"]),
    ("submitted", "Beküldve / bírálat alatt", ["submitted", "under_review"]),
    ("revision", "Javítás kért", ["major_revision", "minor_revision", "revision_sent"]),
    ("done", "Lezárva", ["accepted", "rejected", "withdrawn"]),
]

LANE_OF = {s: key for key, _, states in LANES for s in states}

CSS = """
*, *::before, *::after { box-sizing: border-box; }
:root {
  --bg: #f7f7f5; --panel: #fff; --ink: #1b1a17; --muted: #6b6862;
  --line: #e2e0da; --accent: #7a5cff; --ok: #1f8a54; --warn: #b8791a;
  --bad: #c0392b; --chip: #f0eeea;
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#16151a; --panel:#1e1d24; --ink:#eceaf2; --muted:#9d99a8;
          --line:#302e38; --accent:#a892ff; --ok:#4fd18b; --warn:#e0a94a;
          --bad:#f0776a; --chip:#2a2833; }
}
:root[data-theme="light"] {
  --bg:#f7f7f5; --panel:#fff; --ink:#1b1a17; --muted:#6b6862;
  --line:#e2e0da; --accent:#7a5cff; --ok:#1f8a54; --warn:#b8791a;
  --bad:#c0392b; --chip:#f0eeea;
}
:root[data-theme="dark"] {
  --bg:#16151a; --panel:#1e1d24; --ink:#eceaf2; --muted:#9d99a8;
  --line:#302e38; --accent:#a892ff; --ok:#4fd18b; --warn:#e0a94a;
  --bad:#f0776a; --chip:#2a2833;
}
body { margin:0; background:var(--bg); color:var(--ink); font: 15px/1.5
  ui-sans-serif, -apple-system, "Segoe UI", system-ui, sans-serif; }
.wrap { max-width: 1180px; margin: 0 auto; padding: 32px 20px 72px; }
h1 { font-size: 1.5rem; margin: 0 0 4px; letter-spacing: -0.01em; }
.sub { color: var(--muted); font-size: .85rem; margin-bottom: 28px; }
.counts { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:28px; }
.count { background:var(--panel); border:1px solid var(--line); border-radius:10px;
  padding:10px 14px; min-width:120px; }
.count b { display:block; font-size:1.5rem; line-height:1.2; }
.count span { color:var(--muted); font-size:.75rem; text-transform:uppercase;
  letter-spacing:.06em; }
.alerts { border:1px solid var(--bad); border-radius:10px; padding:12px 16px;
  margin-bottom:28px; background:var(--panel); }
.alerts h2 { font-size:.8rem; text-transform:uppercase; letter-spacing:.08em;
  margin:0 0 8px; color:var(--bad); }
.alerts ul { margin:0; padding-left:18px; }
.lanes { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
  gap:14px; margin-bottom:32px; }
.lane { background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:12px; min-width:0; }
.lane h3 { margin:0 0 10px; font-size:.72rem; text-transform:uppercase;
  letter-spacing:.08em; color:var(--muted); }
.card { border:1px solid var(--line); border-radius:9px; padding:9px 10px;
  margin-bottom:8px; background:var(--bg); }
.card .t { font-weight:600; font-size:.85rem; line-height:1.35; }
.card .j { color:var(--muted); font-size:.75rem; margin-top:3px; }
.chips { display:flex; flex-wrap:wrap; gap:4px; margin-top:6px; }
.chip { font-size:.68rem; padding:2px 7px; border-radius:999px;
  background:var(--chip); color:var(--muted); white-space:nowrap; }
.chip.ok { color:var(--ok); } .chip.warn { color:var(--warn); }
.chip.bad { color:var(--bad); } .chip.acc { color:var(--accent); }
.tablewrap { overflow-x:auto; background:var(--panel); border:1px solid var(--line);
  border-radius:12px; }
table { border-collapse:collapse; width:100%; min-width:820px; font-size:.85rem; }
th, td { text-align:left; padding:9px 12px; border-bottom:1px solid var(--line);
  vertical-align:top; }
th { font-size:.7rem; text-transform:uppercase; letter-spacing:.06em;
  color:var(--muted); font-weight:600; }
tr:last-child td { border-bottom:none; }
td.n { white-space:nowrap; }
.bar { display:inline-block; width:74px; height:6px; border-radius:3px;
  background:var(--chip); overflow:hidden; vertical-align:middle; }
.bar i { display:block; height:100%; background:var(--accent); }
h2.sec { font-size:.8rem; text-transform:uppercase; letter-spacing:.08em;
  color:var(--muted); margin:32px 0 10px; }
code { background:var(--chip); padding:1px 5px; border-radius:4px; font-size:.8em; }
footer { margin-top:36px; color:var(--muted); font-size:.75rem; }
"""


def esc(x):
    return html.escape(str(x or ""))


def chip(text, cls=""):
    return f'<span class="chip {cls}">{esc(text)}</span>'


def cover_chip(sub):
    state = sub["cover_letter_state"]
    label = {"missing": "cover: nincs", "draft": "cover: piszkozat",
             "ready": "cover: kész"}[state]
    return chip(label, {"missing": "bad", "draft": "warn", "ready": "ok"}[state])


def sent_chip(sub):
    if sub["submitted"]:
        return chip(f"beküldve {sub['submitted_at'] or '?'}", "ok")
    return chip("NINCS beküldve", "bad")


def due_chip(date_str):
    d = L.days_until(date_str)
    if d is None:
        return ""
    if d < 0:
        return chip(f"lejárt {abs(d)} napja", "bad")
    if d <= 7:
        return chip(f"{d} nap", "bad")
    if d <= 21:
        return chip(f"{d} nap", "warn")
    return chip(f"{d} nap")


def render(conn, out_path):
    projects = conn.execute(
        "SELECT * FROM projects WHERE archived = 0 ORDER BY id").fetchall()

    rows, alerts = [], []
    lane_cards = {key: [] for key, _, _ in LANES}

    for p in projects:
        sub = L.current_submission(conn, p["id"])
        reviews = L.open_reviews(conn, sub["id"]) if sub else []
        status = sub["status"] if sub else "drafting"
        lane = LANE_OF.get(status, "drafting")

        rev_done = rev_total = 0
        for rv in reviews:
            d, t = L.point_progress(conn, rv["id"])
            rev_done += d
            rev_total += t

        chips = []
        if sub:
            chips += [cover_chip(sub), sent_chip(sub)]
            if sub["due_at"]:
                chips.append(due_chip(sub["due_at"]))
        else:
            chips.append(chip("nincs beadás"))

        lane_cards[lane].append(
            f'<div class="card"><div class="t">{esc(p["title"][:90])}</div>'
            f'<div class="j">{esc(sub["journal"]) if sub else "—"}</div>'
            f'<div class="chips">{"".join(chips)}</div></div>')

        # Alert conditions, in the order they matter.
        for rv in reviews:
            d = L.days_until(rv["due_at"])
            done, total = L.point_progress(conn, rv["id"])
            if total == 0:
                alerts.append(f"<b>{esc(p['slug'])}</b> — bírálat #{rv['id']} betöltve, "
                              f"de nincs pontokra bontva")
            elif d is not None and d <= 14:
                alerts.append(f"<b>{esc(p['slug'])}</b> — {total - done} nyitott bírálói pont, "
                              f"határidő {esc(rv['due_at'])} ({d} nap)")
        if sub and status in L.NEEDS_ACTION and not reviews:
            alerts.append(f"<b>{esc(p['slug'])}</b> — {L.STATUS_LABEL[status]} döntés, "
                          f"de nincs rögzítve bírálói levél")
        if sub and status == "ready" and not sub["submitted"]:
            alerts.append(f"<b>{esc(p['slug'])}</b> — kész a {esc(sub['journal'])} "
                          f"beadásra, de nincs beküldve "
                          f"({L.COVER_LABEL[sub['cover_letter_state']]} cover letter)")

        pct = int(100 * rev_done / rev_total) if rev_total else 0
        prog = (f'<span class="bar"><i style="width:{pct}%"></i></span> '
                f'{rev_done}/{rev_total}') if rev_total else "—"
        rows.append(
            "<tr>"
            f'<td><b>{esc(p["title"][:70])}</b><br><code>{esc(p["slug"])}</code></td>'
            f'<td>{esc(sub["journal"]) if sub else "—"}'
            + (f'<br><span class="chip">#{esc(sub["journal_ms_id"])}</span>'
               if sub and sub["journal_ms_id"] else "")
            + "</td>"
            f'<td class="n">{esc(L.STATUS_LABEL.get(status, status))}</td>'
            f'<td class="n">{cover_chip(sub) if sub else "—"}</td>'
            f'<td class="n">{sent_chip(sub) if sub else chip("nincs beadás")}</td>'
            f'<td class="n">{prog}</td>'
            f'<td class="n">{esc(sub["due_at"]) if sub and sub["due_at"] else "—"} '
            f'{due_chip(sub["due_at"]) if sub else ""}</td>'
            "</tr>")

    n_sub = sum(1 for p in projects
                if (s := L.current_submission(conn, p["id"])) and s["submitted"])
    n_open_rev = len(L.open_reviews(conn))
    n_unsent = sum(1 for p in projects
                   if (s := L.current_submission(conn, p["id"])) and not s["submitted"])

    lanes_html = "".join(
        f'<div class="lane"><h3>{esc(label)} ({len(lane_cards[key])})</h3>'
        + ("".join(lane_cards[key]) or '<div class="j">—</div>')
        + "</div>"
        for key, label, _ in LANES)

    alerts_html = ""
    if alerts:
        items = "".join(f"<li>{a}</li>" for a in dict.fromkeys(alerts))
        alerts_html = f'<div class="alerts"><h2>Figyelmet igényel</h2><ul>{items}</ul></div>'

    doc = f"""<!doctype html>
<html lang="hu"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Science Monitor</title><style>{CSS}</style></head><body>
<div class="wrap">
  <h1>Science Monitor</h1>
  <div class="sub">{len(projects)} aktív kézirat · generálva
    {datetime.now().strftime('%Y-%m-%d %H:%M')} · adatforrás <code>{esc(L.DB_PATH)}</code></div>
  <div class="counts">
    <div class="count"><b>{len(projects)}</b><span>kézirat</span></div>
    <div class="count"><b>{n_sub}</b><span>beküldve</span></div>
    <div class="count"><b>{n_unsent}</b><span>beadásra vár</span></div>
    <div class="count"><b>{n_open_rev}</b><span>nyitott bírálat</span></div>
  </div>
  {alerts_html}
  <div class="lanes">{lanes_html}</div>
  <h2 class="sec">Minden kézirat</h2>
  <div class="tablewrap"><table>
    <thead><tr><th>Kézirat</th><th>Folyóirat</th><th>Státusz</th><th>Cover letter</th>
    <th>Beküldve?</th><th>Bírálati pontok</th><th>Határidő</th></tr></thead>
    <tbody>{"".join(rows) or '<tr><td colspan="7">Nincs felvett kézirat.</td></tr>'}</tbody>
  </table></div>
  <footer>Frissítés: <code>sm.py dashboard --open</code> · a fájl lokális, nincs feltöltve sehova.</footer>
</div></body></html>"""

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return os.path.abspath(out_path)


if __name__ == "__main__":
    conn = L.connect()
    print(render(conn, sys.argv[1] if len(sys.argv) > 1 else L.DASHBOARD_PATH))
