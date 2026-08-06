#!/usr/bin/env python3
"""science-monitor CLI — manuscripts, submissions, reviewer letters.

Every slash command in this plugin is a thin wrapper around one subcommand
here, so the same thing works from a plain terminal.

    sm.py status                     what is where, what needs action
    sm.py scan [ROOT] [--apply]      find manuscript projects on disk
    sm.py show SLUG                  everything about one manuscript
    sm.py context SLUG               ordered read-plan for a session
    sm.py submit SLUG --journal J    open / update a submission attempt
    sm.py review add SLUG --file L   ingest a reviewer letter
    sm.py dashboard [--open]         write the HTML overview
"""

import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sm_lib as L  # noqa: E402


# ---------------------------------------------------------------- formatting

def bar(done, total, width=10):
    if not total:
        return "—"
    filled = round(width * done / total)
    return "█" * filled + "░" * (width - filled) + f" {done}/{total}"


def flag(sub):
    """Compact submitted/cover chip used in list views."""
    if sub is None:
        return "· nincs beadás"
    cover = {"missing": "✗cover", "draft": "~cover", "ready": "✓cover"}[sub["cover_letter_state"]]
    sent = f"✓beküldve {sub['submitted_at']}" if sub["submitted"] else "✗nincs beküldve"
    return f"{cover} · {sent}"


def due_note(date_str):
    d = L.days_until(date_str)
    if d is None:
        return ""
    if d < 0:
        return f"  ⚠ HATÁRIDŐ LEJÁRT {abs(d)} napja ({date_str})"
    if d <= 7:
        return f"  ⚠ határidő {d} nap ({date_str})"
    return f"  határidő: {date_str} ({d} nap)"


# -------------------------------------------------------------------- status

def cmd_status(conn, args):
    projects = conn.execute(
        "SELECT * FROM projects WHERE archived = ? OR ? = 1 ORDER BY id",
        (0, 1 if args.all else 0),
    ).fetchall()
    if not projects:
        print("Nincs felvett kézirat. Indulj a `sm.py scan --apply` paranccsal,")
        print("vagy vegyél fel egyet kézzel: `sm.py add --title \"...\" --path DIR`.")
        return

    actionable = []
    print(f"SCIENCE MONITOR — {len(projects)} kézirat\n")
    for p in projects:
        sub = L.current_submission(conn, p["id"])
        icon = STATE_ICON.get(p["state"], "·")
        print(f"{icon} [{p['slug']}]  {p['title'][:62]}")
        print(f"    {L.PROJECT_STATE_LABEL.get(p['state'], p['state']).upper()}"
              + (f" · {p['category']}" if p["category"] != "kutatas" else ""))
        if sub is None:
            print(f"    {L.STATUS_LABEL['drafting']:<24} · nincs beadás")
        else:
            label = L.STATUS_LABEL.get(sub["status"], sub["status"])
            print(f"    {label:<24} → {sub['journal']}"
                  + (f" (#{sub['journal_ms_id']})" if sub["journal_ms_id"] else "")
                  + f"  [beadás {sub['seq']}]")
            print(f"    {flag(sub)}")
            if sub["due_at"]:
                print(f"   {due_note(sub['due_at'])}")
            for rv in L.open_reviews(conn, sub["id"]):
                done, total = L.point_progress(conn, rv["id"])
                print(f"    review #{rv['id']} ({rv['decision'] or 'n/a'}): {bar(done, total)}"
                      + due_note(rv["due_at"]))
                actionable.append((p, sub, rv, done, total))
            if sub["status"] in L.NEEDS_ACTION and not L.open_reviews(conn, sub["id"]):
                print("    ⚠ revision kért, de nincs betöltve bírálói levél "
                      f"→ `/sm:review {p['slug']}`")
        print()

    if actionable:
        print("SÜRGŐS — nyitott bírálat:")
        for p, sub, rv, done, total in sorted(
                actionable, key=lambda t: (L.days_until(t[2]["due_at"]) is None,
                                           L.days_until(t[2]["due_at"]) or 0)):
            print(f"  · {p['slug']} @ {sub['journal']} — {total - done} megválaszolatlan pont"
                  + due_note(rv["due_at"]))
        print()

    ready = [p for p in projects
             if (s := L.current_submission(conn, p["id"])) and not s["submitted"]
             and s["status"] == "ready"]
    if ready:
        print("KÉSZ, DE NINCS BEKÜLDVE:")
        for p in ready:
            s = L.current_submission(conn, p["id"])
            print(f"  · {p['slug']} → {s['journal']} ({L.COVER_LABEL[s['cover_letter_state']]} cover letter)")


# ---------------------------------------------------------------------- show

def cmd_show(conn, args):
    p = L.get_project(conn, args.ref)
    print(f"{p['title']}\n{'=' * min(len(p['title']), 78)}")
    print(f"slug      : {p['slug']}")
    print(f"állapot   : {STATE_ICON.get(p['state'], '·')} "
          f"{L.PROJECT_STATE_LABEL.get(p['state'], p['state'])}"
          f"   kategória: {p['category']}")
    print(f"típus     : {p['kind']}   nyelv: {p['lang']}")
    print(f"mappa     : {p['root_path'] or '—'}")
    if p["notes"]:
        print(f"jegyzet   : {p['notes']}")

    subs = L.submissions_of(conn, p["id"])
    print(f"\nBEADÁSOK ({len(subs)})")
    if not subs:
        print("  — még egy sincs —")
    for s in subs:
        print(f"  #{s['seq']} {s['journal']}"
              + (f" · {s['portal']}" if s["portal"] else "")
              + (f" · ms {s['journal_ms_id']}" if s["journal_ms_id"] else ""))
        print(f"      státusz : {L.STATUS_LABEL.get(s['status'], s['status'])}")
        print(f"      cover   : {L.COVER_LABEL[s['cover_letter_state']]}"
              + (f"  ({s['cover_letter_path']})" if s["cover_letter_path"] else ""))
        print(f"      beküldve: {'IGEN — ' + (s['submitted_at'] or '?') if s['submitted'] else 'NEM'}")
        if s["decision"]:
            print(f"      döntés  : {s['decision']} ({s['decision_at'] or '?'})")
        if s["due_at"]:
            print(f"      határidő: {s['due_at']}")
        if s["notes"]:
            print(f"      jegyzet : {s['notes']}")
        for rv in L.all_reviews(conn, s["id"]):
            done, total = L.point_progress(conn, rv["id"])
            print(f"      review #{rv['id']} [{rv['state']}] {bar(done, total)}")

    files = L.files_of(conn, p["id"])
    print(f"\nFÁJLOK ({len(files)})")
    by_role = {}
    for f in files:
        by_role.setdefault(f["role"], []).append(f)
    for role in L.FILE_ROLES:
        group = by_role.get(role)
        if not group:
            continue
        shown = group[:6]
        print(f"  {role:<12} {len(group):>3} db")
        for f in shown:
            mark = "" if os.path.exists(f["path"]) else "  [HIÁNYZIK]"
            print(f"      {f['path']}{mark}")
        if len(group) > len(shown):
            print(f"      … +{len(group) - len(shown)} további")

    evs = conn.execute(
        "SELECT * FROM events WHERE project_id = ? ORDER BY at DESC LIMIT 12",
        (p["id"],)).fetchall()
    if evs:
        print("\nIDŐVONAL (legutóbbi 12)")
        for e in evs:
            print(f"  {e['at'][:10]}  {e['kind']:<16} {e['summary']}")


# ----------------------------------------------------------------- add / set

def cmd_add(conn, args):
    slug = args.slug or L.slugify(args.title)
    root = os.path.abspath(os.path.expanduser(args.path)) if args.path else ""
    conn.execute(
        "INSERT INTO projects (slug, title, kind, root_path, lang, notes, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (slug, args.title, args.kind, root, args.lang, args.notes or "", L.now()),
    )
    pid = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()["id"]
    L.log_event(conn, pid, "project_added", args.title)
    conn.commit()
    print(f"felvéve: [{slug}] {args.title}")


def cmd_set(conn, args):
    p = L.get_project(conn, args.ref)
    fields, values = [], []
    for name in ("title", "kind", "lang", "notes", "root_path"):
        val = getattr(args, name, None)
        if val is not None:
            fields.append(f"{name} = ?")
            values.append(os.path.abspath(os.path.expanduser(val))
                          if name == "root_path" else val)
    if args.archive:
        fields.append("archived = 1")
    if args.unarchive:
        fields.append("archived = 0")
    if not fields:
        L.die("nincs megadva módosítandó mező")
    values.append(p["id"])
    conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", values)
    L.log_event(conn, p["id"], "project_updated", ", ".join(f.split(" =")[0] for f in fields))
    conn.commit()
    print(f"frissítve: {p['slug']}")


def cmd_file(conn, args):
    p = L.get_project(conn, args.ref)
    if args.action == "add":
        path = os.path.abspath(os.path.expanduser(args.path))
        conn.execute(
            "INSERT OR REPLACE INTO files (project_id, role, path, label, added_at) "
            "VALUES (?,?,?,?,?)",
            (p["id"], args.role, path, args.label or "", L.now()),
        )
        conn.commit()
        print(f"fájl felvéve [{args.role}]: {path}")
    else:
        conn.execute("DELETE FROM files WHERE project_id = ? AND path = ?",
                     (p["id"], os.path.abspath(os.path.expanduser(args.path))))
        conn.commit()
        print("fájl törölve a nyilvántartásból")


# ---------------------------------------------------------------- submission

def _resolve_submission(conn, project_id, seq=None):
    if seq:
        row = conn.execute("SELECT * FROM submissions WHERE project_id = ? AND seq = ?",
                           (project_id, seq)).fetchone()
        if not row:
            L.die(f"nincs {seq}. beadás ehhez a kézirathoz")
        return row
    row = L.current_submission(conn, project_id)
    if not row:
        L.die("ehhez a kézirathoz még nincs beadás — `sm.py submit SLUG --journal ...`")
    return row


def cmd_submit(conn, args):
    p = L.get_project(conn, args.ref)
    sub = L.current_submission(conn, p["id"])

    # A new journal, or an explicit --new, opens the next attempt.
    if args.new or sub is None or (args.journal and args.journal != sub["journal"]) \
            or (sub and sub["status"] in L.TERMINAL and args.journal):
        if not args.journal:
            L.die("új beadáshoz kell --journal")
        seq = (conn.execute("SELECT COALESCE(MAX(seq), 0) s FROM submissions WHERE project_id = ?",
                            (p["id"],)).fetchone()["s"]) + 1
        conn.execute(
            "INSERT INTO submissions (project_id, seq, journal, portal, journal_ms_id, "
            "status, created_at) VALUES (?,?,?,?,?,?,?)",
            (p["id"], seq, args.journal, args.portal or "", args.ms_id or "",
             "drafting", L.now()),
        )
        sub = conn.execute("SELECT * FROM submissions WHERE project_id = ? AND seq = ?",
                           (p["id"], seq)).fetchone()
        n = L.seed_checklist(conn, sub["id"], p["kind"], p["category"])
        L.log_event(conn, p["id"], "submission_opened", f"#{seq} → {args.journal}", sub["id"])
        print(f"új beadás nyitva: #{seq} → {args.journal} ({n} tételes checklisttel)")

    sets, vals = [], []

    def put(col, val):
        sets.append(f"{col} = ?")
        vals.append(val)

    if args.journal and args.journal != sub["journal"]:
        put("journal", args.journal)
    if args.portal:
        put("portal", args.portal)
    if args.ms_id:
        put("journal_ms_id", args.ms_id)
    if args.status:
        if args.status not in L.STATUSES:
            L.die(f"ismeretlen státusz '{args.status}'; válassz: {', '.join(L.STATUSES)}")
        put("status", args.status)
    if args.cover:
        cover = os.path.abspath(os.path.expanduser(args.cover))
        put("cover_letter_path", cover)
        if not args.cover_state:
            put("cover_letter_state", "ready" if os.path.exists(cover) else "draft")
        conn.execute("INSERT OR REPLACE INTO files (project_id, role, path, label, added_at) "
                     "VALUES (?,?,?,?,?)",
                     (p["id"], "cover_letter", cover, f"beadás #{sub['seq']}", L.now()))
    if args.cover_state:
        if args.cover_state not in L.COVER_STATES:
            L.die(f"a cover letter állapota csak ez lehet: {', '.join(L.COVER_STATES)}")
        put("cover_letter_state", args.cover_state)
    if args.due:
        put("due_at", args.due)
    if args.notes:
        put("notes", args.notes)

    if args.sent:
        when = args.date or L.today()
        put("submitted", 1)
        put("submitted_at", when)
        if not args.status:
            put("status", "submitted")
        L.log_event(conn, p["id"], "submitted", f"{sub['journal']} — {when}", sub["id"])
    if args.unsent:
        put("submitted", 0)
        put("submitted_at", "")
        L.log_event(conn, p["id"], "submit_undone", sub["journal"], sub["id"])

    if sets:
        vals.append(sub["id"])
        conn.execute(f"UPDATE submissions SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()

    sub = conn.execute("SELECT * FROM submissions WHERE id = ?", (sub["id"],)).fetchone()
    print(f"[{p['slug']}] #{sub['seq']} {sub['journal']}: "
          f"{L.STATUS_LABEL.get(sub['status'], sub['status'])} · {L.submitted_label(sub)}")


def cmd_decision(conn, args):
    p = L.get_project(conn, args.ref)
    sub = _resolve_submission(conn, p["id"], args.seq)
    status = args.decision
    if status not in L.STATUSES:
        L.die(f"ismeretlen döntés '{status}'; válassz: {', '.join(L.STATUSES)}")
    conn.execute(
        "UPDATE submissions SET status = ?, decision = ?, decision_at = ?, due_at = ? WHERE id = ?",
        (status, args.decision, args.date or L.today(), args.due or sub["due_at"], sub["id"]),
    )
    L.log_event(conn, p["id"], "decision", f"{sub['journal']}: {status}", sub["id"])
    conn.commit()
    print(f"[{p['slug']}] #{sub['seq']} {sub['journal']} → {L.STATUS_LABEL.get(status, status)}"
          + (f", határidő {args.due}" if args.due else ""))


def cmd_event(conn, args):
    p = L.get_project(conn, args.ref)
    sub = L.current_submission(conn, p["id"])
    L.log_event(conn, p["id"], args.kind, args.summary, sub["id"] if sub else None)
    conn.commit()
    print("esemény rögzítve")


# ------------------------------------------------------------------- context

CONTEXT_ORDER = ["manuscript", "cover_letter", "response", "supplement",
                 "refs", "table", "code", "data", "figure", "other"]

READ_HINT = {
    ".docx": "doc-tools: doctotext",
    ".doc": "doc-tools: doctotext",
    ".pdf": "doc-tools: pdftotext",
    ".xlsx": "doc-tools: xlstotext",
    ".xls": "doc-tools: xlstotext",
    ".pptx": "doc-tools: doctotext",
    ".tex": "doc-tools: latextotext",
    ".png": "Read (kép)",
    ".jpg": "Read (kép)",
    ".tif": "konvertálás kell",
    ".tiff": "konvertálás kell",
}


def cmd_context(conn, args):
    p = L.get_project(conn, args.ref)
    sub = L.current_submission(conn, p["id"])
    files = L.files_of(conn, p["id"])

    out = {
        "slug": p["slug"], "title": p["title"], "kind": p["kind"], "lang": p["lang"],
        "root": p["root_path"], "notes": p["notes"],
        "submission": None, "open_reviews": [], "read_plan": [], "missing": [],
    }
    if sub:
        out["submission"] = {
            "seq": sub["seq"], "journal": sub["journal"], "portal": sub["portal"],
            "journal_ms_id": sub["journal_ms_id"],
            "status": sub["status"], "status_hu": L.STATUS_LABEL.get(sub["status"], sub["status"]),
            "cover_letter_state": sub["cover_letter_state"],
            "cover_letter_path": sub["cover_letter_path"],
            "submitted": bool(sub["submitted"]), "submitted_at": sub["submitted_at"],
            "decision": sub["decision"], "decision_at": sub["decision_at"],
            "due_at": sub["due_at"], "days_left": L.days_until(sub["due_at"]),
            "notes": sub["notes"],
        }
        for rv in L.open_reviews(conn, sub["id"]):
            done, total = L.point_progress(conn, rv["id"])
            pts = conn.execute(
                "SELECT idx, reviewer, severity, state, comment FROM review_points "
                "WHERE review_id = ? ORDER BY reviewer, idx", (rv["id"],)).fetchall()
            out["open_reviews"].append({
                "id": rv["id"], "decision": rv["decision"], "state": rv["state"],
                "due_at": rv["due_at"], "days_left": L.days_until(rv["due_at"]),
                "letter_path": rv["letter_path"], "done": done, "total": total,
                "open_points": [dict(x) for x in pts if x["state"] == "open"],
            })

    # Only the core of the manuscript is queued for reading; everything else is
    # inventory the session can reach for on demand. A read plan that says
    # "open all 75 files" is the same as no plan at all.
    if args.all:
        queued_roles = set(CONTEXT_ORDER) - {"figure", "data"}
    elif args.roles:
        queued_roles = set(args.roles.split(","))
    else:
        queued_roles = {"manuscript", "cover_letter", "response"}

    budget = args.limit
    for role in CONTEXT_ORDER:
        for f in files:
            if f["role"] != role:
                continue
            if not os.path.exists(f["path"]):
                out["missing"].append(f["path"])
                continue
            size = os.path.getsize(f["path"])
            ext = os.path.splitext(f["path"])[1].lower()
            queue = role in queued_roles and size <= args.max_bytes and budget > 0
            if queue:
                budget -= 1
            out["read_plan"].append({
                "role": role, "path": f["path"], "bytes": size,
                "how": READ_HINT.get(ext, "Read"),
                "read_now": queue,
                "label": f["label"],
            })

    if args.json:
        L.dump_json(out)
        return

    print(f"KONTEXTUS — {p['title']}")
    print(f"slug: {p['slug']}   típus: {p['kind']}   mappa: {p['root_path'] or '—'}")
    if p["notes"]:
        print(f"jegyzet: {p['notes']}")
    s = out["submission"]
    if s:
        print(f"\nAKTUÁLIS BEADÁS #{s['seq']} — {s['journal']}"
              + (f" (ms {s['journal_ms_id']})" if s["journal_ms_id"] else ""))
        print(f"  státusz : {s['status_hu']}")
        print(f"  cover   : {L.COVER_LABEL[s['cover_letter_state']]}"
              + (f" — {s['cover_letter_path']}" if s["cover_letter_path"] else ""))
        print(f"  beküldve: {'IGEN, ' + s['submitted_at'] if s['submitted'] else 'NEM'}")
        if s["due_at"]:
            print(f"  határidő: {s['due_at']} ({s['days_left']} nap)")
    else:
        print("\nNincs nyitott beadás.")

    for rv in out["open_reviews"]:
        print(f"\nNYITOTT BÍRÁLAT #{rv['id']} — {rv['decision'] or 'n/a'} "
              f"({rv['done']}/{rv['total']} pont kész)")
        if rv["letter_path"]:
            print(f"  levél: {rv['letter_path']}")
        for pt in rv["open_points"][:20]:
            print(f"  [{pt['reviewer']}.{pt['idx']}] {pt['comment'][:150]}")
        if len(rv["open_points"]) > 20:
            print(f"  … +{len(rv['open_points']) - 20} további nyitott pont")

    queued = [x for x in out["read_plan"] if x["read_now"]]
    rest = [x for x in out["read_plan"] if not x["read_now"]]
    total_kb = sum(x["bytes"] for x in queued) / 1024
    print(f"\nOLVASD MOST ({len(queued)} fájl, ~{total_kb:.0f} kB)")
    for item in queued:
        print(f"  → [{item['role']}] {item['path']}"
              f"  ({item['bytes'] / 1024:.0f} kB, {item['how']})")
    if not queued:
        print("  — nincs olvasandó fájl —")

    if rest:
        by_role = {}
        for item in rest:
            by_role.setdefault(item["role"], []).append(item)
        print(f"\nKÉSZLET — nyilvántartva, csak ha kell ({len(rest)} fájl)")
        for role, group in by_role.items():
            kb = sum(x["bytes"] for x in group) / 1024
            print(f"  · {role:<12} {len(group):>3} db, {kb:.0f} kB")
            for item in group[:3]:
                print(f"        {item['path']}")
            if len(group) > 3:
                print(f"        … +{len(group) - 3} további "
                      f"(`sm.py context {p['slug']} --roles {role}`)")

    if out["missing"]:
        print("\nHIÁNYZÓ FÁJLOK (nyilvántartva, de nincsenek a lemezen):")
        for m in out["missing"]:
            print(f"  ✗ {m}")


# ---------------------------------------------------------------------- scan

MANUSCRIPT_EXT = {".docx", ".doc", ".tex", ".md", ".odt"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             ".memo", ".claude", "build", "dist", ".DS_Store"}

ROLE_PATTERNS = [
    ("cover_letter", r"cover[\s_-]*letter|covering[\s_-]*letter|kiser[oő][\s_-]*level"),
    ("response",     r"response|rebuttal|reviewer|valasz|v[aá]lasz|point[\s_-]*by[\s_-]*point"),
    ("supplement",   r"suppl|supporting|appendix|s\d+_"),
    ("refs",         r"\.bib$|\.enl$|\.ris$|refs?[\s_-]|bibliograph"),
    ("figure",       r"^fig|figure|\.png$|\.jpe?g$|\.tiff?$|\.svg$|\.eps$"),
    ("table",        r"^table|table_|\.csv$"),
    ("code",         r"\.(r|py|do|sas|jl)$"),
    ("manuscript",   r"manuscript|kezirat|k[eé]zirat|_ms_|paper|draft"),
]


# Markdown that is repo furniture, not a manuscript.
NOT_MANUSCRIPT = re.compile(
    r"^(readme|license|licence|changelog|contributing|todo|notes?|plan|"
    r"design|artifact_prompt|claude|agents)\b")


def classify(path):
    name = os.path.basename(path).lower()
    parent = os.path.basename(os.path.dirname(path)).lower()
    ext = os.path.splitext(name)[1].lower()
    if NOT_MANUSCRIPT.match(name):
        return "other"
    for role, pat in ROLE_PATTERNS:
        if re.search(pat, name):
            return role
    if parent in ("ms", "manuscript", "kezirat") and ext in MANUSCRIPT_EXT:
        return "manuscript"
    if parent in ("figs", "figures"):
        return "figure"
    if parent in ("supplementary", "suppl"):
        return "supplement"
    if ext in MANUSCRIPT_EXT:
        return "manuscript"
    if ext in (".csv", ".xlsx"):
        return "data"
    return "other"


def walk_project(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.startswith("~$") or fn.startswith("."):
                continue
            path = os.path.join(dirpath, fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext in {".pyc", ".log", ".lock", ".zip", ".gz"}:
                continue
            found.append((classify(path), path))
    return found


def cmd_scan(conn, args):
    target = args.root or (L.load_config()["scan_roots"] or ["~"])[0]
    root = os.path.abspath(os.path.expanduser(target))
    if not os.path.isdir(root):
        L.die(f"nincs ilyen mappa: {root}")

    # `--single` treats ROOT itself as one project rather than as a folder of
    # projects — the right mode for a prepared submission package.
    entries = ["."] if args.single else sorted(os.listdir(root))
    candidates = []
    for entry in entries:
        d = os.path.realpath(os.path.join(root, entry))
        if not os.path.isdir(d) or entry in SKIP_DIRS or (
                entry.startswith(".") and entry != "."):
            continue
        if entry == ".":
            entry = os.path.basename(d)
        files = walk_project(d)
        # A stray .md is not enough — require a real manuscript file, or a
        # markdown whose name says so.
        manuscripts = [
            p for role, p in files
            if role == "manuscript" and (
                os.path.splitext(p)[1].lower() in {".docx", ".doc", ".tex", ".odt"}
                or re.search(r"manuscript|kezirat|k[eé]zirat|_ms_|paper|draft",
                             os.path.basename(p).lower()))]
        if not manuscripts:
            continue
        existing = conn.execute("SELECT slug FROM projects WHERE root_path = ?", (d,)).fetchone()
        candidates.append({
            "dir": d, "slug": L.slugify(entry), "title": entry,
            "files": files, "n_manuscripts": len(manuscripts),
            "already": existing["slug"] if existing else None,
        })

    if not candidates:
        print(f"Nem találtam kézirat-projektet itt: {root}")
        return

    print(f"SCAN — {root}\n")
    for c in candidates:
        counts = {}
        for role, _ in c["files"]:
            counts[role] = counts.get(role, 0) + 1
        summary = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
        state = f"MÁR FELVÉVE ({c['already']})" if c["already"] else "új"
        print(f"  [{c['slug']}]  {state}")
        print(f"      {c['dir']}")
        print(f"      {summary}")
    print()

    if not args.apply:
        print("Ez csak javaslat. Felvételhez: ugyanez a parancs `--apply` kapcsolóval.")
        print("A címeket utána pontosítsd: `sm.py set SLUG --title \"...\"`.")
        return

    added = updated = 0
    for c in candidates:
        if c["already"]:
            pid = conn.execute("SELECT id FROM projects WHERE slug = ?",
                               (c["already"],)).fetchone()["id"]
            updated += 1
        else:
            conn.execute(
                "INSERT INTO projects (slug, title, kind, root_path, created_at) "
                "VALUES (?,?,?,?,?)",
                (c["slug"], c["title"], "article", c["dir"], L.now()))
            pid = conn.execute("SELECT id FROM projects WHERE slug = ?",
                               (c["slug"],)).fetchone()["id"]
            L.log_event(conn, pid, "scanned", c["dir"])
            added += 1
        for role, path in c["files"]:
            conn.execute(
                "INSERT OR IGNORE INTO files (project_id, role, path, label, added_at) "
                "VALUES (?,?,?,?,?)", (pid, role, path, "", L.now()))
    conn.commit()
    print(f"Kész: {added} új kézirat, {updated} meglévő frissítve.")
    print("Következő lépés: `sm.py set SLUG --title \"...\"` és "
          "`sm.py submit SLUG --journal \"...\"`.")


# -------------------------------------------------------------------- review

def cmd_review(conn, args):
    if args.action == "add":
        return _review_add(conn, args)
    if args.action == "points":
        return _review_points(conn, args)
    if args.action == "show":
        return _review_show(conn, args)
    if args.action == "set":
        return _review_set(conn, args)
    if args.action == "list":
        return _review_list(conn, args)


def _review_add(conn, args):
    p = L.get_project(conn, args.ref)
    sub = _resolve_submission(conn, p["id"], args.seq)
    letter_path = ""
    if args.file:
        src = os.path.abspath(os.path.expanduser(args.file))
        if not os.path.exists(src):
            L.die(f"nincs ilyen fájl: {src}")
        letter_path = src
    elif args.text:
        letter_path = os.path.join(L.LETTERS_DIR, f"{p['slug']}_s{sub['seq']}_{L.today()}.txt")
        with open(letter_path, "w", encoding="utf-8") as fh:
            fh.write(args.text)

    conn.execute(
        "INSERT INTO reviews (submission_id, received_at, source, decision, due_at, "
        "letter_path, editor, state, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sub["id"], args.received or L.today(), args.source, args.decision or "",
         args.due or "", letter_path, args.editor or "", "open", args.notes or "", L.now()))
    rid = conn.execute("SELECT last_insert_rowid() r").fetchone()["r"]

    if args.decision and args.decision in L.STATUSES:
        conn.execute("UPDATE submissions SET status = ?, decision = ?, decision_at = ?, "
                     "due_at = COALESCE(NULLIF(?, ''), due_at) WHERE id = ?",
                     (args.decision, args.decision, args.received or L.today(),
                      args.due or "", sub["id"]))
    L.log_event(conn, p["id"], "review_received",
                f"{sub['journal']}: {args.decision or 'levél'} (review #{rid})", sub["id"])
    conn.commit()
    print(f"bírálat felvéve: review #{rid} — {p['slug']} @ {sub['journal']}")
    if letter_path:
        print(f"levél: {letter_path}")
    print("Következő: bontsd pontokra és töltsd be — "
          f"`sm.py review points {rid} --json points.json`")


def _review_points(conn, args):
    rv = conn.execute("SELECT * FROM reviews WHERE id = ?", (args.review_id,)).fetchone()
    if not rv:
        L.die(f"nincs ilyen bírálat: #{args.review_id}")
    if args.json_file:
        with open(os.path.expanduser(args.json_file), encoding="utf-8") as fh:
            payload = json.load(fh)
    elif args.json_stdin:
        payload = json.load(sys.stdin)
    else:
        L.die("adj meg --json FILE vagy --json-stdin bemenetet")

    if isinstance(payload, dict):
        payload = payload.get("points", [])
    if args.replace:
        conn.execute("DELETE FROM review_points WHERE review_id = ?", (args.review_id,))

    n = 0
    for item in payload:
        conn.execute(
            "INSERT INTO review_points (review_id, reviewer, idx, comment, severity, "
            "targets, response, action, state) VALUES (?,?,?,?,?,?,?,?,?)",
            (args.review_id, item.get("reviewer", "R1"), int(item.get("idx", n + 1)),
             item["comment"], item.get("severity", "normal"),
             item.get("targets", ""), item.get("response", ""),
             item.get("action", ""), item.get("state", "open")))
        n += 1
    conn.execute("UPDATE reviews SET state = 'in_progress' WHERE id = ? AND state = 'open'",
                 (args.review_id,))
    conn.commit()
    print(f"{n} bírálói pont betöltve a review #{args.review_id} alá")


def _review_show(conn, args):
    rv = conn.execute(
        "SELECT r.*, s.journal, s.seq, p.slug, p.title, p.id pid FROM reviews r "
        "JOIN submissions s ON s.id = r.submission_id "
        "JOIN projects p ON p.id = s.project_id WHERE r.id = ?",
        (args.review_id,)).fetchone()
    if not rv:
        L.die(f"nincs ilyen bírálat: #{args.review_id}")
    pts = conn.execute("SELECT * FROM review_points WHERE review_id = ? "
                       "ORDER BY reviewer, idx", (args.review_id,)).fetchall()
    if args.json:
        L.dump_json({"review": dict(rv), "points": [dict(x) for x in pts]})
        return
    done, total = L.point_progress(conn, args.review_id)
    print(f"REVIEW #{rv['id']} — {rv['title']}")
    print(f"  {rv['journal']} (beadás #{rv['seq']}) · {rv['decision'] or 'n/a'} · "
          f"érkezett {rv['received_at']} · forrás: {rv['source']}")
    if rv["due_at"]:
        print(f" {due_note(rv['due_at'])}")
    if rv["letter_path"]:
        print(f"  levél: {rv['letter_path']}")
    print(f"  haladás: {bar(done, total)}\n")
    current = None
    for pt in pts:
        if pt["reviewer"] != current:
            current = pt["reviewer"]
            print(f"  — {current} —")
        icon = {"open": "○", "drafted": "◐", "done": "●", "declined": "⊘"}[pt["state"]]
        sev = "!" if pt["severity"] == "major" else " "
        print(f"  {icon}{sev}[{pt['idx']}] {pt['comment']}")
        if pt["targets"]:
            print(f"       érint: {pt['targets']}")
        if pt["response"]:
            print(f"       válasz: {pt['response'][:300]}")
        if pt["action"]:
            print(f"       teendő: {pt['action']}")


def _review_set(conn, args):
    if args.point:
        row = conn.execute("SELECT * FROM review_points WHERE id = ?", (args.point,)).fetchone()
        if not row:
            L.die(f"nincs ilyen pont: {args.point}")
        sets, vals = [], []
        # `--action` lands in `action_text`; plain `action` is the subcommand name.
        for col in ("response", "action", "state", "severity", "targets"):
            val = getattr(args, "action_text" if col == "action" else col, None)
            if val is not None:
                if col == "state" and val not in L.POINT_STATES:
                    L.die(f"a pont állapota csak ez lehet: {', '.join(L.POINT_STATES)}")
                sets.append(f"{col} = ?")
                vals.append(val)
        if not sets:
            L.die("nincs megadva módosítandó mező")
        vals.append(args.point)
        conn.execute(f"UPDATE review_points SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
        print(f"pont #{args.point} frissítve")
        return

    if not args.review_id:
        L.die("adj meg --review ID vagy --point ID azonosítót")
    sets, vals = [], []
    for col in ("state", "due_at", "notes", "decision", "editor"):
        val = getattr(args, col, None)
        if val is not None:
            if col == "state" and val not in L.REVIEW_STATES:
                L.die(f"a bírálat állapota csak ez lehet: {', '.join(L.REVIEW_STATES)}")
            sets.append(f"{col} = ?")
            vals.append(val)
    if not sets:
        L.die("nincs megadva módosítandó mező")
    vals.append(args.review_id)
    conn.execute(f"UPDATE reviews SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    print(f"review #{args.review_id} frissítve")


def _review_list(conn, args):
    rows = L.open_reviews(conn)
    if not rows:
        print("Nincs nyitott bírálat.")
        return
    for rv in rows:
        done, total = L.point_progress(conn, rv["id"])
        print(f"#{rv['id']}  [{rv['slug']}] {rv['journal']} — {rv['decision'] or 'n/a'} "
              f"{bar(done, total)}{due_note(rv['due_at'])}")


def cmd_respond(conn, args):
    """Emit a point-by-point response skeleton from the stored points."""
    rv = conn.execute(
        "SELECT r.*, s.journal, s.journal_ms_id, p.title, p.slug, p.root_path FROM reviews r "
        "JOIN submissions s ON s.id = r.submission_id "
        "JOIN projects p ON p.id = s.project_id WHERE r.id = ?",
        (args.review_id,)).fetchone()
    if not rv:
        L.die(f"nincs ilyen bírálat: #{args.review_id}")
    pts = conn.execute("SELECT * FROM review_points WHERE review_id = ? "
                       "ORDER BY reviewer, idx", (args.review_id,)).fetchall()
    if not pts:
        L.die("ehhez a bírálathoz még nincsenek betöltve pontok")

    lines = [
        f"# Response to Reviewers — {rv['title']}",
        "",
        f"Manuscript: {rv['journal_ms_id'] or '(ms ID)'} · {rv['journal']}",
        f"Decision: {rv['decision'] or '(decision)'} · received {rv['received_at']}",
        "",
        "We thank the editor and the reviewers for their careful reading of our "
        "manuscript. Below we respond to each point in turn; reviewer comments are "
        "given in italics and our responses in plain text. All changes are marked in "
        "the revised manuscript.",
        "",
    ]
    current = None
    for pt in pts:
        if pt["reviewer"] != current:
            current = pt["reviewer"]
            lines += [f"## Reviewer {current}", ""]
        lines += [f"**{current}.{pt['idx']}** *{pt['comment']}*", ""]
        lines += [pt["response"] or "> TODO: válasz", ""]
        if pt["action"]:
            lines += [f"*Change made:* {pt['action']}", ""]
        if pt["targets"]:
            lines += [f"*Location:* {pt['targets']}", ""]

    text = "\n".join(lines)
    out = args.out or os.path.join(
        rv["root_path"] or L.ROOT, f"response_to_reviewers_r{rv['id']}.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"vázlat kiírva: {out}")
    todo = sum(1 for pt in pts if not pt["response"])
    print(f"{len(pts)} pont, ebből {todo} még válasz nélkül")


# ----------------------------------------------------------------- checklist

def cmd_checklist(conn, args):
    p = L.get_project(conn, args.ref)
    sub = _resolve_submission(conn, p["id"], args.seq)

    if args.action == "init":
        n = L.seed_checklist(conn, sub["id"], p["kind"], p["category"])
        conn.commit()
        print(f"checklist kész: {n} tétel ({p['kind']} típusra szabva)")
        return

    if args.action == "set":
        rows = L.checklist_of(conn, sub["id"])
        targets = [r for r in rows if str(r["id"]) == str(args.item)
                   or args.item.lower() in r["label"].lower()]
        if not targets:
            L.die(f"nincs ilyen checklist-tétel: {args.item}")
        if len(targets) > 1:
            print("több tétel illeszkedik:")
            for r in targets:
                print(f"  #{r['id']} {r['label']}")
            L.die("pontosíts az id-vel")
        row = targets[0]
        done = 1 if args.done else (0 if args.undone else row["done"])
        na = 1 if args.na else (0 if args.applicable else row["na"])
        conn.execute("UPDATE checklist SET done = ?, na = ?, note = ? WHERE id = ?",
                     (done, na, args.note if args.note is not None else row["note"],
                      row["id"]))
        conn.commit()
        mark = "n/a" if na else ("kész" if done else "nyitva")
        print(f"#{row['id']} {row['label']} → {mark}")
        return

    rows = L.checklist_of(conn, sub["id"])
    if not rows:
        print("Nincs checklist ehhez a beadáshoz — `sm.py checklist init "
              f"{p['slug']}`")
        return
    done, total = L.checklist_progress(conn, sub["id"])
    print(f"BEADÁSI CHECKLIST — {p['title'][:60]}")
    print(f"  {sub['journal']} (beadás #{sub['seq']})  {bar(done, total)}\n")
    for r in rows:
        icon = "⊘" if r["na"] else ("●" if r["done"] else "○")
        print(f"  {icon} #{r['id']:<4} {r['label']}")
        if r["note"]:
            print(f"          {r['note']}")
    if done < total:
        print(f"\n{total - done} tétel nyitva. Pipálás: "
              f"`sm.py checklist set {p['slug']} ID --done`")


STATE_ICON = {"folyamatban": "◐", "hianypotlas": "!", "korrekcio": "✎",
              "kesz": "✓", "elfogadva": "★", "elutasitva": "✗"}


def cmd_state(conn, args):
    if args.auto:
        changed = 0
        for p in conn.execute("SELECT * FROM projects ORDER BY id").fetchall():
            sub = L.current_submission(conn, p["id"])
            want, definite = L.suggest_state(conn, p, sub)
            # Only the default and the heuristic states get overwritten by a
            # guess; a state the user chose stands unless the record disproves it.
            settled = p["state"] not in ("folyamatban", "hianypotlas")
            if settled and not definite and not args.force:
                continue
            if want != p["state"]:
                conn.execute("UPDATE projects SET state = ? WHERE id = ?", (want, p["id"]))
                L.log_event(conn, p["id"], "state", f"{p['state']} → {want} (automatikus)")
                print(f"  {p['slug']}: {L.PROJECT_STATE_LABEL[p['state']]} → "
                      f"{L.PROJECT_STATE_LABEL[want]}")
                changed += 1
        conn.commit()
        print(f"{changed} állapot frissítve.")
        return

    if not args.ref:
        counts = conn.execute(
            "SELECT state, COUNT(*) n FROM projects WHERE archived = 0 GROUP BY state"
        ).fetchall()
        by = {r["state"]: r["n"] for r in counts}
        for s in L.PROJECT_STATES:
            print(f"  {STATE_ICON[s]} {L.PROJECT_STATE_LABEL[s]:<14} {by.get(s, 0)}")
        return

    p = L.get_project(conn, args.ref)
    if not args.value:
        sub = L.current_submission(conn, p["id"])
        want, definite = L.suggest_state(conn, p, sub)
        print(f"[{p['slug']}] {L.PROJECT_STATE_LABEL[p['state']]}"
              f"  (a nyilvántartás alapján: {L.PROJECT_STATE_LABEL[want]}"
              f"{', bizonyított' if definite else ', becslés'})")
        return
    if args.value not in L.PROJECT_STATES:
        L.die(f"ismeretlen állapot '{args.value}'; válassz: {', '.join(L.PROJECT_STATES)}")
    conn.execute("UPDATE projects SET state = ? WHERE id = ?", (args.value, p["id"]))
    L.log_event(conn, p["id"], "state", f"{p['state']} → {args.value}")
    conn.commit()
    print(f"[{p['slug']}] {L.PROJECT_STATE_LABEL[p['state']]} → "
          f"{L.PROJECT_STATE_LABEL[args.value]}")


def cmd_gaps(conn, args):
    projects = ([L.get_project(conn, args.ref)] if args.ref else
                conn.execute("SELECT * FROM projects WHERE archived = 0 ORDER BY id"
                             ).fetchall())
    order = {"blocker": 0, "warn": 1, "info": 2}
    any_found = False
    for p in projects:
        sub = L.current_submission(conn, p["id"])
        items = sorted(L.gaps(conn, p, sub), key=lambda g: order[g["severity"]])
        if not items:
            continue
        any_found = True
        print(f"[{p['slug']}] {p['title'][:60]}")
        for g in items:
            icon = {"blocker": "✗", "warn": "!", "info": "·"}[g["severity"]]
            print(f"  {icon} {g['text']}")
            if g["ask"]:
                print(f"      → {g['ask']}")
            elif g["fix"]:
                print(f"      → {g['fix']}")
        print()
    if not any_found:
        print("Nincs hiány. Minden beadás rendben.")


# ----------------------------------------------------------------- dashboard

def cmd_dashboard(conn, args):
    import dashboard as D
    path = D.render(conn, args.out or L.DASHBOARD_PATH)
    print(f"dashboard: {path}")
    if args.open:
        subprocess.run(["open", path], check=False)


def cmd_import_science(conn, args):
    import import_science as I
    mapping = {}
    if args.map:
        with open(os.path.expanduser(args.map), encoding="utf-8") as fh:
            mapping = {str(k): v for k, v in json.load(fh).items()}
    I.run(conn, args.manifest, args.apply, mapping, root=args.root,
          artifacts_db=args.artifacts)


def cmd_repo(conn, args):
    import repo as R
    try:
        if args.action == "init":
            R.cmd_init(conn, args.path)
        elif args.action == "push":
            R.cmd_push(conn, args.repo, args.message, do_push=not args.no_push)
        elif args.action == "pull":
            R.cmd_pull(conn, args.repo, do_fetch=not args.no_fetch)
        else:
            R.cmd_status(conn, args.repo)
    except RuntimeError as exc:
        L.die(str(exc))


def cmd_config(conn, args):
    cfg = L.load_config()
    if args.key is None:
        for k in sorted(cfg):
            val = cfg[k]
            print(f"  {k:<14} {val if val != '' else '—'}")
        print(f"\n  ({L.CONFIG_PATH})")
        return
    if args.key not in L.CONFIG_DEFAULTS:
        L.die(f"ismeretlen kulcs '{args.key}'; "
              f"választható: {', '.join(sorted(L.CONFIG_DEFAULTS))}")
    if args.value is None:
        print(cfg[args.key])
        return
    if isinstance(L.CONFIG_DEFAULTS[args.key], list):
        cfg[args.key] = [v.strip() for v in args.value.split(",") if v.strip()]
    else:
        cfg[args.key] = args.value
    print(f"{args.key} = {cfg[args.key]}\n{L.save_config(cfg)}")


def cmd_serve(conn, args):
    import serve as S
    conn.close()  # the server opens its own connection per request
    S.run(port=args.port, open_browser=not args.no_open)


def cmd_deadlines(conn, args):
    rows = conn.execute(
        "SELECT p.slug, p.title, s.journal, s.due_at, s.status FROM submissions s "
        "JOIN projects p ON p.id = s.project_id "
        "WHERE s.due_at != '' AND s.status NOT IN ('accepted','rejected','withdrawn') "
        "ORDER BY s.due_at").fetchall()
    rrows = conn.execute(
        "SELECT p.slug, s.journal, r.id, r.due_at FROM reviews r "
        "JOIN submissions s ON s.id = r.submission_id "
        "JOIN projects p ON p.id = s.project_id "
        "WHERE r.due_at != '' AND r.state != 'answered' ORDER BY r.due_at").fetchall()
    if not rows and not rrows:
        print("Nincs rögzített határidő.")
        return
    for r in rows:
        print(f"{r['due_at']}  [{r['slug']}] {r['journal']} — "
              f"{L.STATUS_LABEL.get(r['status'], r['status'])}{due_note(r['due_at'])}")
    for r in rrows:
        print(f"{r['due_at']}  [{r['slug']}] review #{r['id']} @ {r['journal']}"
              f"{due_note(r['due_at'])}")


# --------------------------------------------------------------------- parse

def build_parser():
    ap = argparse.ArgumentParser(prog="sm.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="áttekintés")
    p.add_argument("--all", action="store_true", help="archivált kéziratokkal együtt")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("show", help="egy kézirat részletei")
    p.add_argument("ref")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("add", help="kézirat felvétele")
    p.add_argument("--title", required=True)
    p.add_argument("--slug")
    p.add_argument("--path")
    p.add_argument("--kind", default="article")
    p.add_argument("--lang", default="en")
    p.add_argument("--notes")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("set", help="kézirat mezőinek módosítása")
    p.add_argument("ref")
    p.add_argument("--title")
    p.add_argument("--kind")
    p.add_argument("--lang")
    p.add_argument("--notes")
    p.add_argument("--root-path", dest="root_path")
    p.add_argument("--archive", action="store_true")
    p.add_argument("--unarchive", action="store_true")
    p.set_defaults(fn=cmd_set)

    p = sub.add_parser("file", help="fájl nyilvántartása")
    p.add_argument("action", choices=["add", "rm"])
    p.add_argument("ref")
    p.add_argument("path")
    p.add_argument("--role", default="other", choices=L.FILE_ROLES)
    p.add_argument("--label")
    p.set_defaults(fn=cmd_file)

    p = sub.add_parser("submit", help="beadás nyitása / frissítése")
    p.add_argument("ref")
    p.add_argument("--journal")
    p.add_argument("--portal")
    p.add_argument("--ms-id", dest="ms_id")
    p.add_argument("--status", choices=L.STATUSES)
    p.add_argument("--cover", help="cover letter útvonala")
    p.add_argument("--cover-state", dest="cover_state", choices=L.COVER_STATES)
    p.add_argument("--sent", action="store_true", help="beküldve jelölés")
    p.add_argument("--unsent", action="store_true", help="beküldés visszavonása")
    p.add_argument("--date", help="beküldés dátuma (alap: ma)")
    p.add_argument("--due", help="határidő ISO dátumként")
    p.add_argument("--notes")
    p.add_argument("--new", action="store_true", help="új beadási kör nyitása")
    p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("decision", help="szerkesztői döntés rögzítése")
    p.add_argument("ref")
    p.add_argument("decision", choices=L.STATUSES)
    p.add_argument("--date")
    p.add_argument("--due")
    p.add_argument("--seq", type=int)
    p.set_defaults(fn=cmd_decision)

    p = sub.add_parser("event", help="esemény a idővonalra")
    p.add_argument("ref")
    p.add_argument("kind")
    p.add_argument("summary")
    p.set_defaults(fn=cmd_event)

    p = sub.add_parser("context", help="olvasási terv egy kézirathoz")
    p.add_argument("ref")
    p.add_argument("--json", action="store_true")
    p.add_argument("--roles", help="ezeket a szerepeket sorolja olvasásra, vesszővel")
    p.add_argument("--all", action="store_true", help="ábrákon/adatokon kívül mindent")
    p.add_argument("--limit", type=int, default=8, help="max ennyi fájl olvasásra")
    p.add_argument("--max-bytes", dest="max_bytes", type=int, default=400_000)
    p.set_defaults(fn=cmd_context)

    p = sub.add_parser("scan", help="kézirat-projektek keresése a lemezen")
    p.add_argument("root", nargs="?", help="alap: a config scan_roots első eleme")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--single", action="store_true",
                   help="ROOT maga egy kézirat, nem projektek gyűjtője")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("review", help="bírálatok kezelése")
    rs = p.add_subparsers(dest="action", required=True)

    r = rs.add_parser("add")
    r.add_argument("ref")
    r.add_argument("--file", help="a bírálói levél fájlja")
    r.add_argument("--text", help="a levél szövege közvetlenül")
    r.add_argument("--decision", choices=L.STATUSES)
    r.add_argument("--due")
    r.add_argument("--received")
    r.add_argument("--editor")
    r.add_argument("--source", default="manual", choices=["manual", "gmail", "portal", "file"])
    r.add_argument("--notes")
    r.add_argument("--seq", type=int)

    r = rs.add_parser("points")
    r.add_argument("review_id", type=int)
    r.add_argument("--json", dest="json_file")
    r.add_argument("--json-stdin", dest="json_stdin", action="store_true")
    r.add_argument("--replace", action="store_true")

    r = rs.add_parser("show")
    r.add_argument("review_id", type=int)
    r.add_argument("--json", action="store_true")

    r = rs.add_parser("set")
    r.add_argument("--review", dest="review_id", type=int)
    r.add_argument("--point", type=int)
    r.add_argument("--response")
    r.add_argument("--action", dest="action_text")
    r.add_argument("--state")
    r.add_argument("--severity")
    r.add_argument("--targets")
    r.add_argument("--due", dest="due_at")
    r.add_argument("--notes")
    r.add_argument("--decision")
    r.add_argument("--editor")

    rs.add_parser("list")
    p.set_defaults(fn=cmd_review)

    p = sub.add_parser("searchlog", help="irodalomkeresési napló (audit trail)")
    p.add_argument("action", choices=["add", "import", "show", "methods"])
    p.add_argument("ref")
    p.add_argument("--query")
    p.add_argument("--source", default="pubmed", choices=L.SEARCH_SOURCES)
    # No default: `show` must not silently filter to one purpose. `add`/`import`
    # fall back to "topic" themselves.
    p.add_argument("--purpose", choices=L.SEARCH_PURPOSES)
    p.add_argument("--filters", help="dátumtartomány, nyelv, publikációtípus")
    p.add_argument("--hits", type=int, default=0)
    p.add_argument("--kept", type=int, default=0)
    p.add_argument("--ran-at", dest="ran_at", help="a keresés dátuma (alap: ma)")
    p.add_argument("--notes")
    p.add_argument("--json", dest="json_file", help="import: JSON fájl")
    p.set_defaults(fn=cmd_searchlog)

    p = sub.add_parser("respond", help="response-to-reviewers vázlat")
    p.add_argument("review_id", type=int)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_respond)

    p = sub.add_parser("dashboard", help="HTML áttekintő")
    p.add_argument("--out")
    p.add_argument("--open", action="store_true")
    p.set_defaults(fn=cmd_dashboard)

    p = sub.add_parser("deadlines", help="közelgő határidők")
    p.set_defaults(fn=cmd_deadlines)

    p = sub.add_parser("checklist", help="beadási checklist")
    cs = p.add_subparsers(dest="action", required=True)
    for name in ("show", "init"):
        c = cs.add_parser(name)
        c.add_argument("ref")
        c.add_argument("--seq", type=int)
    c = cs.add_parser("set")
    c.add_argument("ref")
    c.add_argument("item", help="tétel id-je vagy szövegrészlete")
    c.add_argument("--done", action="store_true")
    c.add_argument("--undone", action="store_true")
    c.add_argument("--na", action="store_true", help="nem alkalmazható")
    c.add_argument("--applicable", action="store_true")
    c.add_argument("--note")
    c.add_argument("--seq", type=int)
    p.set_defaults(fn=cmd_checklist)

    p = sub.add_parser("gaps", help="hiánylista: mi hiányzik és mi javítja")
    p.add_argument("ref", nargs="?")
    p.set_defaults(fn=cmd_gaps)

    p = sub.add_parser("state", help="munkaállapot: folyamatban / hiánypótlás / "
                                     "korrekció / kész / elfogadva / elutasítva")
    p.add_argument("ref", nargs="?")
    p.add_argument("value", nargs="?", choices=L.PROJECT_STATES)
    p.add_argument("--auto", action="store_true",
                   help="a nyilvántartásból következő állapot beállítása mindenhol")
    p.add_argument("--force", action="store_true",
                   help="--auto felülírja a kézzel lezárt állapotokat is")
    p.set_defaults(fn=cmd_state)

    p = sub.add_parser("import-science", help="Claude Science munkaegység-export beolvasása")
    p.add_argument("manifest", help="a 00_MANIFEST.json útvonala")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--map", help="JSON: {\"15\": \"meglévő-slug\"} — csatolás új projekt helyett")
    p.add_argument("--root", help="az átiratok mappája (alap: a manifest mappája)")
    p.add_argument("--artifacts", metavar="OPERON_DB",
                   help="a Claude Science operon-cli.db — ebből jönnek a tényleges "
                        "artifact-fájlok (docx, ábrák, táblák)")
    p.set_defaults(fn=cmd_import_science)

    p = sub.add_parser("repo", help="közös git adat-repo: init / push / pull / status")
    rp = p.add_subparsers(dest="action", required=True)
    c = rp.add_parser("init")
    c.add_argument("path")
    for name in ("push", "pull", "status"):
        c = rp.add_parser(name)
        c.add_argument("--repo", help="útvonal (alap: a konfigban beállított)")
        if name == "push":
            c.add_argument("-m", "--message")
            c.add_argument("--no-push", action="store_true", help="csak helyi commit")
        if name == "pull":
            c.add_argument("--no-fetch", action="store_true", help="git pull nélkül")
    p.set_defaults(fn=cmd_repo)

    p = sub.add_parser("config", help="beállítások (gépfüggő és személyes adatok)")
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.set_defaults(fn=cmd_config)

    p = sub.add_parser("serve", help="élő dashboard, kattintható gombokkal")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--no-open", dest="no_open", action="store_true")
    p.set_defaults(fn=cmd_serve)

    return ap


# ---------------------------------------------------------------- searchlog

def _searchlog_rows(conn, project_id, purpose=None):
    sql = "SELECT * FROM search_log WHERE project_id = ?"
    vals = [project_id]
    if purpose:
        sql += " AND purpose = ?"
        vals.append(purpose)
    return conn.execute(sql + " ORDER BY ran_at, id", vals).fetchall()


def _searchlog_insert(conn, pid, item):
    """Upsert one search record. Re-running the same query updates its counts."""
    conn.execute(
        "INSERT INTO search_log (project_id, ran_at, source, query, filters, hits, "
        "kept, purpose, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(project_id, source, query) DO UPDATE SET "
        "hits = excluded.hits, kept = excluded.kept, filters = excluded.filters, "
        "purpose = excluded.purpose, "
        "ran_at = CASE WHEN excluded.ran_at != '' THEN excluded.ran_at ELSE search_log.ran_at END, "
        "notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE search_log.notes END",
        (pid, item.get("ran_at", ""), item.get("source", "web"), item["query"],
         item.get("filters", ""), int(item.get("hits", 0) or 0),
         int(item.get("kept", 0) or 0), item.get("purpose", "topic"),
         item.get("notes", ""), L.now()))


def cmd_searchlog(conn, args):
    project = L.get_project(conn, args.ref)
    pid = project["id"]

    if args.action == "add":
        _searchlog_insert(conn, pid, {
            "ran_at": args.ran_at or L.today(), "source": args.source,
            "query": args.query, "filters": args.filters or "",
            "hits": args.hits, "kept": args.kept,
            "purpose": args.purpose or "topic", "notes": args.notes or ""})
        conn.commit()
        print(f"keresés rögzítve [{args.source}/{args.purpose or 'topic'}]: {args.query[:70]}")
        return

    if args.action == "import":
        if args.json_file:
            with open(os.path.expanduser(args.json_file), encoding="utf-8") as fh:
                payload = json.load(fh)
        else:
            payload = json.load(sys.stdin)
        # Accept {"searches": [...]}, a bare list, or {"query": hits} mapping.
        if isinstance(payload, dict):
            payload = payload.get("searches", payload)
        if isinstance(payload, dict):
            payload = [{"query": q, "hits": n} for q, n in payload.items()]
        n = 0
        for item in payload:
            item.setdefault("source", args.source)
            item.setdefault("purpose", args.purpose or "topic")
            item.setdefault("ran_at", args.ran_at or "")
            _searchlog_insert(conn, pid, item)
            n += 1
        conn.commit()
        print(f"{n} keresés betöltve — {project['slug']}")
        return

    rows = _searchlog_rows(conn, pid, args.purpose if args.action == "show" else None)
    if not rows:
        L.die(f"nincs rögzített keresés ehhez: {project['slug']} — "
              f"`sm.py searchlog add {project['slug']} --query ... --hits N`")

    if args.action == "show":
        print(f"KERESÉSI NAPLÓ — {project['title'][:70]}")
        print(f"  {len(rows)} keresés · {sum(r['hits'] for r in rows)} találati tétel")
        cur = None
        for r in rows:
            if r["purpose"] != cur:
                cur = r["purpose"]
                sub = [x for x in rows if x["purpose"] == cur]
                print(f"\n  — {cur} ({len(sub)} keresés, {sum(x['hits'] for x in sub)} tétel) —")
            keep = f" → megtartva {r['kept']}" if r["kept"] else ""
            when = f"{r['ran_at']} " if r["ran_at"] else ""
            print(f"  [{r['source']:>10}] {when}{r['hits']:>3} találat{keep}")
            print(f"       {r['query']}")
            if r["filters"]:
                print(f"       szűrők: {r['filters']}")
        return

    # methods: paste-ready search-strategy paragraph
    topic = [r for r in rows if r["purpose"] in ("topic", "citation-chase")]
    verif = [r for r in rows if r["purpose"] == "verification"]
    other = [r for r in rows if r["purpose"] == "journal-selection"]
    srcs = sorted({r["source"] for r in topic}) or ["web"]
    dates = sorted({r["ran_at"] for r in topic if r["ran_at"]})
    span = f"between {dates[0]} and {dates[-1]}" if len(dates) > 1 else (
        f"on {dates[0]}" if dates else "")
    # `kept` is attributed per query, so it is only summed within a purpose —
    # never across all rows, which would conflate the original sweep with later
    # verification searches and overstate what the log actually knows.
    kept_topic = sum(r["kept"] for r in topic)
    kept_verif = sum(r["kept"] for r in verif)

    print("% --- Search strategy (paste into Materials and Methods) ---")
    print(f"Literature was identified through {len(topic)} searches "
          f"({', '.join(srcs)}) {span}, which surfaced {sum(r['hits'] for r in topic)} "
          f"records in total.", end=" ")
    if kept_topic:
        print(f"Screening against the inclusion criteria retained {kept_topic} "
              f"of these.", end=" ")
    if verif:
        print(f"A further {len(verif)} targeted searches were run to verify "
              f"specific claims"
              + (f", adding {kept_verif} references" if kept_verif else "")
              + ".", end=" ")
    print("\n")
    print("% Full query list:")
    for i, r in enumerate(topic + verif, 1):
        print(f"%  {i:2d}. [{r['source']}] {r['query']}  ({r['hits']} hits)")
    if other:
        print(f"% ({len(other)} further searches were run for journal selection "
              f"and are not part of the evidence base.)")


def main():
    args = build_parser().parse_args()
    conn = L.connect()
    try:
        args.fn(conn, args)
    except L.NotFound as exc:
        L.die(str(exc))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
