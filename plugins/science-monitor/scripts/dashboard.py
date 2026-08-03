#!/usr/bin/env python3
"""The dashboard: pipeline overview, gap lists, submission checklists.

Two modes from one renderer.

* **static** — `sm.py dashboard` writes a file. Every action is a one-click
  copy button: it puts the exact command on the clipboard.
* **live** — `sm.py serve` hands `api_token` in, and the same controls become
  real checkboxes and buttons that write to the store on click.

Self-contained: no external CSS, fonts or scripts, and it never phones home.
"""

import html
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sm_lib as L  # noqa: E402

# The pipeline is organised by work state, not by submission status: a unit
# can be korrekció with no journal at all.
LANES = [(s, L.PROJECT_STATE_LABEL[s]) for s in L.PROJECT_STATES]
STATE_CLS = {"folyamatban": "", "hianypotlas": "warn", "korrekcio": "acc",
             "kesz": "ok", "elfogadva": "ok", "elutasitva": "bad"}

SEV_ICON = {"blocker": "✗", "warn": "!", "info": "·"}
SEV_LABEL = {"blocker": "blokkoló", "warn": "figyelmet kér", "info": "hiányzó adat"}

CSS = """
*, *::before, *::after { box-sizing: border-box; }
:root {
  --bg:#f7f7f5; --panel:#fff; --ink:#1b1a17; --muted:#6b6862; --line:#e2e0da;
  --accent:#7a5cff; --ok:#1f8a54; --warn:#b8791a; --bad:#c0392b; --chip:#f0eeea;
  --btn:#fff; --btnline:#cfccc4;
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#16151a; --panel:#1e1d24; --ink:#eceaf2; --muted:#9d99a8;
    --line:#302e38; --accent:#a892ff; --ok:#4fd18b; --warn:#e0a94a; --bad:#f0776a;
    --chip:#2a2833; --btn:#282630; --btnline:#403d4c; }
}
:root[data-theme="light"] { --bg:#f7f7f5; --panel:#fff; --ink:#1b1a17;
  --muted:#6b6862; --line:#e2e0da; --accent:#7a5cff; --ok:#1f8a54; --warn:#b8791a;
  --bad:#c0392b; --chip:#f0eeea; --btn:#fff; --btnline:#cfccc4; }
:root[data-theme="dark"] { --bg:#16151a; --panel:#1e1d24; --ink:#eceaf2;
  --muted:#9d99a8; --line:#302e38; --accent:#a892ff; --ok:#4fd18b; --warn:#e0a94a;
  --bad:#f0776a; --chip:#2a2833; --btn:#282630; --btnline:#403d4c; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5
  ui-sans-serif,-apple-system,"Segoe UI",system-ui,sans-serif; }
.wrap { max-width:1180px; margin:0 auto; padding:32px 20px 80px; }
h1 { font-size:1.5rem; margin:0 0 4px; letter-spacing:-.01em; }
.sub { color:var(--muted); font-size:.85rem; margin-bottom:12px; }
.mode { display:inline-block; font-size:.7rem; padding:3px 9px; border-radius:999px;
  margin-bottom:24px; }
.mode.live { background:var(--ok); color:#fff; }
.mode.static { background:var(--chip); color:var(--muted); }
.counts { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:28px; }
.count { background:var(--panel); border:1px solid var(--line); border-radius:10px;
  padding:10px 14px; min-width:118px; }
.count b { display:block; font-size:1.5rem; line-height:1.2; }
.count span { color:var(--muted); font-size:.72rem; text-transform:uppercase;
  letter-spacing:.06em; }
h2.sec { font-size:.8rem; text-transform:uppercase; letter-spacing:.08em;
  color:var(--muted); margin:34px 0 10px; }
.lanes { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
  gap:12px; }
.lane { background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:12px; min-width:0; }
.lane h3 { margin:0 0 9px; font-size:.7rem; text-transform:uppercase;
  letter-spacing:.08em; color:var(--muted); }
.lane a { display:block; font-size:.82rem; line-height:1.35; margin-bottom:7px;
  color:var(--ink); text-decoration:none; border-left:2px solid var(--line);
  padding-left:8px; }
.lane a:hover { border-left-color:var(--accent); }
.lane a small { color:var(--muted); display:block; font-size:.72rem; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:16px 18px; margin-bottom:14px; scroll-margin-top:16px; }
.card > h3 { margin:0 0 3px; font-size:1rem; line-height:1.35; }
.card .meta { color:var(--muted); font-size:.8rem; margin-bottom:10px; }
.chips { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-bottom:12px; }
.chip { font-size:.7rem; padding:3px 9px; border-radius:999px; background:var(--chip);
  color:var(--muted); white-space:nowrap; }
.chip.ok { color:var(--ok); } .chip.warn { color:var(--warn); }
.chip.bad { color:var(--bad); } .chip.acc { color:var(--accent); }
button.act { font:inherit; font-size:.72rem; padding:3px 10px; border-radius:999px;
  border:1px solid var(--btnline); background:var(--btn); color:var(--ink);
  cursor:pointer; white-space:nowrap; }
button.act:hover { border-color:var(--accent); color:var(--accent); }
button.act.done { border-color:var(--ok); color:var(--ok); }
button.act.primary { border-color:var(--accent); color:var(--accent); font-weight:600; }
.gaps { list-style:none; margin:0 0 12px; padding:0; }
.gaps li { display:flex; gap:9px; align-items:flex-start; padding:6px 0;
  border-top:1px solid var(--line); font-size:.85rem; }
.gaps li:first-child { border-top:none; }
.gaps .ic { width:1.1em; flex:none; font-weight:700; }
.gaps .blocker .ic { color:var(--bad); } .gaps .warn .ic { color:var(--warn); }
.gaps .info .ic { color:var(--muted); }
.gaps .txt { flex:1; min-width:0; }
.gaps code { display:block; color:var(--muted); font-size:.75em; margin-top:2px;
  word-break:break-all; }
details { border-top:1px solid var(--line); padding-top:9px; margin-top:4px; }
summary { cursor:pointer; font-size:.75rem; text-transform:uppercase;
  letter-spacing:.06em; color:var(--muted); list-style:none; }
summary::-webkit-details-marker { display:none; }
summary::before { content:"▸ "; }
details[open] summary::before { content:"▾ "; }
ul.check { list-style:none; margin:10px 0 0; padding:0; }
ul.check li { display:flex; gap:9px; align-items:flex-start; padding:4px 0;
  font-size:.85rem; }
ul.check input { margin-top:.35em; flex:none; accent-color:var(--accent); }
ul.check li.is-done > span { color:var(--muted); text-decoration:line-through; }
ul.check li.is-na > span { color:var(--muted); opacity:.6; font-style:italic; }
ul.check .na { margin-left:auto; font-size:.65rem; opacity:.55; }
ul.check .na:hover { opacity:1; }
.bar { display:inline-block; width:80px; height:6px; border-radius:3px;
  background:var(--chip); overflow:hidden; vertical-align:middle; }
.bar i { display:block; height:100%; background:var(--accent); }
.tablewrap { overflow-x:auto; background:var(--panel); border:1px solid var(--line);
  border-radius:12px; }
table { border-collapse:collapse; width:100%; min-width:760px; font-size:.83rem; }
th,td { text-align:left; padding:8px 12px; border-bottom:1px solid var(--line); }
th { font-size:.68rem; text-transform:uppercase; letter-spacing:.06em;
  color:var(--muted); font-weight:600; }
tr:last-child td { border-bottom:none; }
td.n { white-space:nowrap; }
code { background:var(--chip); padding:1px 5px; border-radius:4px; font-size:.8em; }
footer { margin-top:40px; color:var(--muted); font-size:.75rem; line-height:1.7; }
#toast { position:fixed; left:50%; bottom:24px; transform:translateX(-50%)
  translateY(80px); background:var(--ink); color:var(--bg); padding:9px 18px;
  border-radius:999px; font-size:.8rem; transition:transform .18s ease;
  pointer-events:none; z-index:9; }
#toast.show { transform:translateX(-50%) translateY(0); }
button.act.ghost { border-style:dashed; color:var(--muted); }
button.act.ghost:hover { color:var(--bad); border-color:var(--bad); }
.nextsteps { border:1px solid var(--bad); border-radius:10px; padding:11px 13px;
  margin:4px 0 12px; }
.nextsteps b { font-size:.75rem; text-transform:uppercase; letter-spacing:.07em;
  color:var(--bad); }
.nextsteps .meta { margin:4px 0 9px; }
.addbox { background:var(--panel); border:1px dashed var(--btnline);
  border-radius:12px; padding:14px 16px; margin-bottom:22px; }
.addbox form { display:flex; flex-wrap:wrap; gap:8px; align-items:center;
  margin-top:10px; }
.addbox input, .addbox select { font:inherit; font-size:.82rem; padding:5px 9px;
  border-radius:8px; border:1px solid var(--btnline); background:var(--bg);
  color:var(--ink); }
.addbox input[name=title] { flex:1; min-width:260px; }
.archived a { color:var(--muted); }
.track { border:1px solid var(--line); border-radius:10px; padding:10px 12px;
  margin-bottom:12px; }
.track.notstarted { display:flex; gap:10px; align-items:center; flex-wrap:wrap;
  border-style:dashed; }
.track.notstarted .meta { margin:0; }
.trackhead { font-size:.68rem; text-transform:uppercase; letter-spacing:.08em;
  color:var(--muted); margin-bottom:8px; }
.stages { display:flex; align-items:stretch; gap:0; flex-wrap:wrap; }
.stage { flex:1; min-width:104px; text-align:center; padding:6px 4px;
  border-top:3px solid var(--line); position:relative; }
.stage + .stage { margin-left:4px; }
.stage.past { border-top-color:var(--ok); }
.stage.past button.act { color:var(--ok); border-color:transparent;
  background:transparent; }
.stage.now { border-top-color:var(--accent); }
.stage.now button.act, .stage.now .lbl { color:var(--accent); font-weight:600;
  border-color:var(--accent); }
.stage.todo button.act, .stage.todo .lbl { color:var(--muted);
  border-color:transparent; background:transparent; }
.stage .lbl { display:block; font-size:.72rem; padding:3px 10px; }
.stage .sub { display:block; font-size:.65rem; color:var(--muted); margin-top:2px; }
"""

JS = """
const SM = window.SM || {live:false, token:null};

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 1900);
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); }
  catch (e) {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); ta.remove();
  }
  toast('Vágólapra másolva — illeszd be a Claude Code-ba');
}

async function api(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-SM-Token': SM.token},
    body: JSON.stringify(body)
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.error) { toast('Hiba: ' + (j.error || r.status)); return null; }
  return j;
}

document.addEventListener('click', async (e) => {
  const b = e.target.closest('button.act');
  if (!b) return;
  const apiSpec = b.dataset.api ? JSON.parse(b.dataset.api) : null;
  if (SM.live && apiSpec) {
    const res = await api(apiSpec.path, apiSpec.body);
    if (res && res.reload) location.reload();
    else if (res) toast('Mentve');
    return;
  }
  if (b.dataset.cmd) copy(b.dataset.cmd);
});

window.smAdd = async function (ev) {
  ev.preventDefault();
  const f = ev.target, body = {};
  for (const el of f.elements) if (el.name) body[el.name] = el.value.trim();
  if (!body.title) return false;
  const res = await api('/api/project/new', body);
  if (res && res.ok) location.reload();
  return false;
};

document.addEventListener('change', async (e) => {
  const cb = e.target;
  if (!cb.matches('input[type=checkbox][data-kind]')) return;
  const li = cb.closest('li');
  const path = cb.dataset.kind === 'check' ? '/api/checklist' : '/api/point';
  const res = await api(path, {id: Number(cb.dataset.id)});
  if (!res) { cb.checked = !cb.checked; return; }
  li.classList.toggle('is-done', !!(res.done || res.state === 'done'));
  const meter = document.getElementById(cb.dataset.meter);
  if (meter && res.progress) {
    const [d, t] = res.progress;
    meter.querySelector('i').style.width = (t ? 100 * d / t : 0) + '%';
    meter.nextElementSibling.textContent = ' ' + d + '/' + t;
  }
});
"""


def esc(x):
    return html.escape(str(x or ""))


def chip(text, cls=""):
    return f'<span class="chip {cls}">{esc(text)}</span>'


def button(label, cmd=None, api=None, cls=""):
    """One control. Live mode calls the API; static mode copies `cmd`."""
    attrs = f' data-cmd="{esc(cmd)}"' if cmd else ""
    if api:
        attrs += f" data-api='{esc(json.dumps(api, ensure_ascii=False))}'"
    return f'<button class="act {cls}"{attrs}>{esc(label)}</button>'


def bar_html(done, total, meter_id=None):
    pct = int(100 * done / total) if total else 0
    ident = f' id="{esc(meter_id)}"' if meter_id else ""
    return (f'<span class="bar"{ident}><i style="width:{pct}%"></i></span>'
            f'<span> {done}/{total}</span>')


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


def add_box(live):
    """Adding a manuscript is a first-class action, not a trip to the terminal."""
    kinds = ["article", "review", "systematic-review", "hypothesis", "position",
             "protocol", "thesis"]
    if not live:
        return ('<div class="addbox"><b>Új kézirat</b>'
                '<p class="meta">Statikus módban a gomb a parancsot másolja.</p>'
                + button('sm.py add --title "..." --path DIR',
                         cmd='sm.py add --title "..." --kind article --path DIR',
                         cls="primary") + "</div>")
    options = "".join(f'<option value="{k}">{k}</option>' for k in kinds)
    cats = "".join(f'<option value="{k}">{esc(v)}</option>'
                   for k, v in L.CATEGORIES.items())
    return (
        '<div class="addbox"><b>Új kézirat</b>'
        '<form id="addform" onsubmit="return smAdd(event)">'
        '<input name="title" placeholder="A kézirat címe" required>'
        f'<select name="kind">{options}</select>'
        f'<select name="category">{cats}</select>'
        '<input name="path" placeholder="mappa (nem kötelező)" size="22">'
        '<button class="act primary" type="submit">Hozzáadás</button>'
        "</form></div>")


def archived_section(conn, live):
    rows = conn.execute(
        "SELECT * FROM projects WHERE archived = 1 ORDER BY slug").fetchall()
    if not rows:
        return ""
    items = []
    for p in rows:
        items.append(
            f'<li><span class="txt">{esc(p["title"][:80])}'
            f'<code>{esc(p["slug"])}</code></span>'
            + button("Visszaállítás", cmd=f"sm.py set {p['slug']} --unarchive",
                     api={"path": "/api/project",
                          "body": {"id": p["id"], "field": "archived", "value": 0}})
            + "</li>")
    return (f'<details class="archived"><summary>Archivált ({len(rows)})</summary>'
            f'<ul class="gaps">{"".join(items)}</ul></details>')


def state_controls(p):
    """The work state as six one-click buttons; the current one is marked."""
    return "".join(
        button(L.PROJECT_STATE_LABEL[st],
               cmd=f"sm.py state {p['slug']} {st}",
               api={"path": "/api/project",
                    "body": {"id": p["id"], "field": "state", "value": st}},
               cls="done" if p["state"] == st else "")
        for st in L.PROJECT_STATES)


# The editor's verdict, as one click each. These are the transitions that
# actually happen to a submitted manuscript, in the order they happen.
VERDICT_BUTTONS = [
    ("submitted", "Beadva"),
    ("under_review", "Peer-review"),
    ("desk_rejection", "Desk rejection"),
    ("major_revision", "Major revision"),
    ("minor_revision", "Minor revision"),
    ("accepted", "Elfogadva"),
    ("rejected", "Elutasítva"),
]


def verdict_controls(p, sub):
    """What the journal said — one button per verdict, current one marked."""
    return "".join(
        button(label,
               cmd=f"sm.py submit {p['slug']} --status {status}",
               api={"path": "/api/submission",
                    "body": {"id": sub["id"], "field": "status", "value": status}},
               cls="done" if sub["status"] == status else "")
        for status, label in VERDICT_BUTTONS)


# Clicking a stage sets the status that stage represents. The decision stage has
# three real outcomes, so it stays on the verdict row rather than guessing one.
STAGE_CLICK = {"beadva": "submitted", "desk": "desk_review",
               "peer": "under_review", "revizio": "major_revision"}


def stage_track(p, sub):
    """The submission process, from 'beadva' onwards.

    Before submission there is no process to show — only a button that starts
    it. That is the point: 'beadva' is what turns a manuscript into a live
    submission with an editor on the other end.
    """
    if sub is None:
        return ""
    if not sub["submitted"]:
        return ('<div class="track notstarted">'
                '<span class="meta">A beadási folyamat még nem indult el.</span>'
                + button("▶ Beadva — folyamat indítása",
                         cmd=f"sm.py submit {p['slug']} --sent",
                         api={"path": "/api/submission",
                              "body": {"id": sub["id"], "field": "submitted",
                                       "value": 1}},
                         cls="primary") + "</div>")

    here = L.stage_index(sub["status"])
    cells = []
    for i, (key, label, _) in enumerate(L.STAGES):
        cls = "now" if i == here else ("past" if i < here else "todo")
        inner = esc(label)
        if key == "dontes":
            # The outcome is a real choice; do not let one click invent it.
            body = (f'<span class="lbl">{inner}</span>'
                    f'<span class="sub">{esc(L.STATUS_LABEL.get(sub["status"], ""))}</span>'
                    if i == here else f'<span class="lbl">{inner}</span>')
            cells.append(f'<div class="stage {cls}">{body}</div>')
        else:
            target = STAGE_CLICK[key]
            cells.append(
                f'<div class="stage {cls}">'
                + button(inner, cmd=f"sm.py submit {p['slug']} --status {target}",
                         api={"path": "/api/submission",
                              "body": {"id": sub["id"], "field": "status",
                                       "value": target}})
                + "</div>")
    when = f" · beadva {esc(sub['submitted_at'])}" if sub["submitted_at"] else ""
    return (f'<div class="track"><div class="trackhead">Beadási folyamat{when}</div>'
            f'<div class="stages">{"".join(cells)}</div></div>')


def next_steps(p, sub):
    """After a rejection the question is only ever: rewrite, correct, or move.

    A desk rejection carries no reviewer reasoning, so the honest default is a
    different journal; a post-review rejection has something to work with.
    """
    if sub is None or sub["status"] not in L.REJECTED:
        return ""
    desk = sub["status"] == "desk_rejection"
    why = ("Desk rejection — a szerkesztő nem küldte bírálatra, tehát a tudományról "
           "nem mond semmit; rendszerint scope vagy formátum. Alapértelmezésben "
           "célújság-váltás."
           if desk else
           "Bírálat utáni elutasítás — van bírálói indoklás, amiből az újraírás "
           "dolgozhat.")
    return (
        '<div class="nextsteps"><b>Tovább innen</b>'
        f'<p class="meta">{esc(why)}</p><div class="chips">'
        + button("Célújság választás", cmd=f"/sm:journal {p['slug']}",
                 cls="primary" if desk else "")
        + button("Újraírás", cmd=f"/sm:context {p['slug']}",
                 cls="" if desk else "primary")
        + button("Korrekció",
                 cmd=f"sm.py state {p['slug']} korrekcio",
                 api={"path": "/api/project",
                      "body": {"id": p["id"], "field": "state", "value": "korrekcio"}})
        + button("Új beadási kör",
                 cmd=f'sm.py submit {p["slug"]} --journal "..." --new')
        + "</div></div>")


COVER_NEXT = {"missing": "draft", "draft": "ready", "ready": "missing"}


def submission_controls(p, sub, live):
    """The chips that double as the one-click actions on a submission."""
    if sub is None:
        return chip("nincs beadás") + button(
            "Beadás nyitása", cmd=f'sm.py submit {p["slug"]} --journal "..."',
            cls="primary")

    out = []
    state = sub["cover_letter_state"]
    out.append(button(
        f"cover: {L.COVER_LABEL[state]}",
        cmd=f'sm.py submit {p["slug"]} --cover-state {COVER_NEXT[state]}',
        api={"path": "/api/submission",
             "body": {"id": sub["id"], "field": "cover_letter_state",
                      "value": COVER_NEXT[state]}},
        cls="done" if state == "ready" else ""))

    if sub["submitted"]:
        out.append(button(
            f"✓ beküldve {sub['submitted_at'] or '?'}",
            cmd=f'sm.py submit {p["slug"]} --unsent',
            api={"path": "/api/submission",
                 "body": {"id": sub["id"], "field": "submitted", "value": 0}},
            cls="done"))
    else:
        out.append(button(
            "Beküldve? — jelöld be",
            cmd=f'sm.py submit {p["slug"]} --sent',
            api={"path": "/api/submission",
                 "body": {"id": sub["id"], "field": "submitted", "value": 1}},
            cls="primary"))

    out.append(chip(L.STATUS_LABEL.get(sub["status"], sub["status"])))
    if sub["due_at"]:
        out.append(due_chip(sub["due_at"]))
    return "".join(out)


def gaps_html(items):
    if not items:
        return '<p class="meta" style="color:var(--ok)">Nincs hiány.</p>'
    order = {"blocker": 0, "warn": 1, "info": 2}
    rows = []
    for g in sorted(items, key=lambda x: order[x["severity"]]):
        act = ""
        if g["ask"]:
            act = button("Másol", cmd=g["ask"])
        elif g["fix"]:
            act = button("Másol", cmd=g["fix"])
        hint = g["ask"] or g["fix"] or ""
        rows.append(
            f'<li class="{g["severity"]}"><span class="ic">{SEV_ICON[g["severity"]]}</span>'
            f'<span class="txt">{esc(g["text"])}'
            + (f"<code>{esc(hint)}</code>" if hint else "")
            + f"</span>{act}</li>")
    return f'<ul class="gaps">{"".join(rows)}</ul>'


def checklist_html(conn, p, sub, live):
    if sub is None:
        return ""
    rows = L.checklist_of(conn, sub["id"])
    if not rows:
        return ('<details><summary>Beadási checklist</summary>'
                '<p class="meta">Nincs létrehozva.</p>'
                + button("Checklist létrehozása",
                         cmd=f"sm.py checklist init {p['slug']}",
                         api={"path": "/api/checklist/init", "body": {"id": sub["id"]}},
                         cls="primary")
                + "</details>")

    done, total = L.checklist_progress(conn, sub["id"])
    meter = f"m-check-{sub['id']}"
    items = []
    for r in rows:
        cls = "is-na" if r["na"] else ("is-done" if r["done"] else "")
        if live:
            box = (f'<input type="checkbox" data-kind="check" data-id="{r["id"]}" '
                   f'data-meter="{meter}"{" checked" if r["done"] else ""}'
                   f'{" disabled" if r["na"] else ""}>')
            na_btn = button("n/a", api={"path": "/api/checklist",
                                        "body": {"id": r["id"], "na": True}},
                            cls="na")
        else:
            box = '<span class="ic">' + ("⊘" if r["na"] else
                                         ("●" if r["done"] else "○")) + "</span>"
            na_btn = button("pipa", cmd=f"sm.py checklist set {p['slug']} {r['id']} --done",
                            cls="na")
        items.append(f'<li class="{cls}">{box}<span>{esc(r["label"])}</span>{na_btn}</li>')

    return (f'<details>'
            f'<summary>Beadási checklist — {bar_html(done, total, meter)}</summary>'
            f'<ul class="check">{"".join(items)}</ul></details>')


def reviews_html(conn, p, sub, live):
    if sub is None:
        return ""
    blocks = []
    for rv in L.open_reviews(conn, sub["id"]):
        pts = conn.execute("SELECT * FROM review_points WHERE review_id = ? "
                           "ORDER BY reviewer, idx", (rv["id"],)).fetchall()
        done, total = L.point_progress(conn, rv["id"])
        meter = f"m-rev-{rv['id']}"
        if not pts:
            body = ('<p class="meta">Nincs pontokra bontva.</p>'
                    + button("Bontsd pontokra", cmd=f"/sm:review {p['slug']}",
                             cls="primary"))
        else:
            items = []
            for pt in pts:
                is_done = pt["state"] in ("done", "declined")
                if live:
                    box = (f'<input type="checkbox" data-kind="point" '
                           f'data-id="{pt["id"]}" data-meter="{meter}"'
                           f'{" checked" if is_done else ""}>')
                else:
                    box = f'<span class="ic">{"●" if is_done else "○"}</span>'
                sev = " ⚠" if pt["severity"] == "major" else ""
                items.append(
                    f'<li class="{"is-done" if is_done else ""}">{box}'
                    f'<span><b>{esc(pt["reviewer"])}.{pt["idx"]}{sev}</b> '
                    f'{esc(pt["comment"][:220])}</span></li>')
            body = (f'<ul class="check">{"".join(items)}</ul>'
                    + button("Válaszlevél összeállítása",
                             cmd=f"/sm:respond {rv['id']}", cls="primary"))
        blocks.append(
            f'<details open><summary>Bírálat #{rv["id"]} — '
            f'{esc(rv["decision"] or "n/a")} {bar_html(done, total, meter)}'
            f'{due_chip(rv["due_at"])}</summary>{body}</details>')
    return "".join(blocks)


def build(conn, api_token=None):
    live = bool(api_token)
    projects = conn.execute(
        "SELECT * FROM projects WHERE archived = 0 ORDER BY id").fetchall()

    lane_cards = {key: [] for key, _ in LANES}
    cards, rows = [], []
    n_blockers = n_sub = n_unsent = 0

    for p in projects:
        sub = L.current_submission(conn, p["id"])
        status = sub["status"] if sub else "drafting"
        items = L.gaps(conn, p, sub)
        n_blockers += sum(1 for g in items if g["severity"] == "blocker")
        if sub and sub["submitted"]:
            n_sub += 1
        elif sub:
            n_unsent += 1

        anchor = f"p-{esc(p['slug'])}"
        lane_cards[p["state"]].append(
            f'<a href="#{anchor}">{esc(p["title"][:70])}'
            f'<small>{esc(sub["journal"]) if sub else "—"}</small></a>')

        cdone, ctotal = L.checklist_progress(conn, sub["id"]) if sub else (0, 0)
        rows.append(
            f'<tr><td><a href="#{anchor}" style="color:inherit">'
            f'{esc(p["title"][:60])}</a><br><code>{esc(p["slug"])}</code></td>'
            f'<td>{esc(sub["journal"]) if sub else "—"}</td>'
            f'<td class="n">{chip(L.PROJECT_STATE_LABEL[p["state"]], STATE_CLS[p["state"]])}</td>'
            f'<td class="n">{esc(L.COVER_LABEL[sub["cover_letter_state"]]) if sub else "—"}</td>'
            f'<td class="n">{"IGEN" if sub and sub["submitted"] else "nem"}</td>'
            f'<td class="n">{bar_html(cdone, ctotal) if ctotal else "—"}</td>'
            f'<td class="n">{sum(1 for g in items if g["severity"] == "blocker")}</td></tr>')

        cards.append(
            f'<div class="card" id="{anchor}">'
            f'<h3>{esc(p["title"])}</h3>'
            f'<div class="meta"><code>{esc(p["slug"])}</code> · {esc(p["kind"])} · {esc(L.CATEGORIES.get(p["category"], p["category"]))} · '
            + (f'{esc(sub["journal"])} (beadás #{sub["seq"]})' if sub else "nincs beadás")
            + (f' · ms {esc(sub["journal_ms_id"])}' if sub and sub["journal_ms_id"] else "")
            + "</div>"
            f'<div class="chips">{state_controls(p)}'
            + button("Archiválás", cmd=f"sm.py set {p['slug']} --archive",
                     api={"path": "/api/project",
                          "body": {"id": p["id"], "field": "archived", "value": 1}},
                     cls="ghost")
            + "</div>"
            + stage_track(p, sub)
            + (f'<div class="chips">{verdict_controls(p, sub)}</div>' if sub else "")
            + f'<div class="chips">{submission_controls(p, sub, live)}'
            + button("Kontextus behívása", cmd=f"/sm:context {p['slug']}")
            + button("Bírálat felvétele", cmd=f"/sm:review {p['slug']}")
            + button("Célújság", cmd=f"/sm:journal {p['slug']}")
            + "</div>"
            + next_steps(p, sub)
            + gaps_html(items)
            + checklist_html(conn, p, sub, live)
            + reviews_html(conn, p, sub, live)
            + "</div>")

    lanes_html = "".join(
        f'<div class="lane"><h3>{esc(label)} ({len(lane_cards[key])})</h3>'
        + ("".join(lane_cards[key]) or '<small style="color:var(--muted)">—</small>')
        + "</div>" for key, label in LANES)

    mode = ('<span class="mode live">élő — a gombok írnak az adatbázisba</span>'
            if live else
            '<span class="mode static">statikus — a gombok a parancsot másolják; '
            'élő módhoz: sm.py serve</span>')

    boot = (f"window.SM = {{live: true, token: {json.dumps(api_token)}}};"
            if live else "window.SM = {live: false, token: null};")

    return f"""<!doctype html>
<html lang="hu"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Science Monitor</title><style>{CSS}</style></head><body>
<div class="wrap">
  <h1>Science Monitor</h1>
  <div class="sub">{len(projects)} aktív kézirat · {datetime.now().strftime('%Y-%m-%d %H:%M')}
    · <code>{esc(L.DB_PATH)}</code></div>
  {mode}
  <div class="counts">
    <div class="count"><b>{len(projects)}</b><span>kézirat</span></div>
    <div class="count"><b>{n_sub}</b><span>beküldve</span></div>
    <div class="count"><b>{n_unsent}</b><span>beadásra vár</span></div>
    <div class="count"><b>{len(L.open_reviews(conn))}</b><span>nyitott bírálat</span></div>
    <div class="count"><b>{n_blockers}</b><span>blokkoló hiány</span></div>
  </div>
  {add_box(live)}
  <h2 class="sec">Folyamat</h2>
  <div class="lanes">{lanes_html}</div>
  <h2 class="sec">Kéziratok — hiánylista, checklist, bírálati pontok</h2>
  {"".join(cards) or '<div class="card">Nincs felvett kézirat.</div>'}
  <h2 class="sec">Összesítő</h2>
  <div class="tablewrap"><table>
    <thead><tr><th>Kézirat</th><th>Folyóirat</th><th>Állapot</th><th>Cover</th>
    <th>Beküldve</th><th>Checklist</th><th>Blokkoló</th></tr></thead>
    <tbody>{"".join(rows) or '<tr><td colspan="7">—</td></tr>'}</tbody>
  </table></div>
  {archived_section(conn, live)}
  <footer>
    Élő mód (a gombok és a pipák közvetlenül írnak): <code>sm.py serve</code><br>
    A fájl lokális, kiadatlan kéziratadatot tartalmaz — ne publikáld.
  </footer>
</div>
<div id="toast"></div>
<script>{boot}{JS}</script>
</body></html>"""


def render(conn, out_path):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(build(conn))
    return os.path.abspath(out_path)


if __name__ == "__main__":
    conn = L.connect()
    print(render(conn, sys.argv[1] if len(sys.argv) > 1 else L.DASHBOARD_PATH))
