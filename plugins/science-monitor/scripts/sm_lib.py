#!/usr/bin/env python3
"""Store and domain model for science-monitor.

One SQLite file under ~/.science-monitor/ holds every manuscript, every
submission attempt for it, and every reviewer letter that came back.
Nothing here talks to the network; the Gmail side is driven from the
slash command and lands via `sm.py review add`.
"""

import json
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
ROOT = os.environ.get("SCIENCE_MONITOR_HOME", os.path.join(HOME, ".science-monitor"))
DB_PATH = os.path.join(ROOT, "monitor.db")
LETTERS_DIR = os.path.join(ROOT, "letters")
DASHBOARD_PATH = os.path.join(ROOT, "dashboard.html")
CONFIG_PATH = os.path.join(ROOT, "config.json")

# Everything machine- or person-specific lives here, not in the code or the
# command docs, so the plugin itself is shareable.
CONFIG_DEFAULTS = {
    "scan_roots": ["~/Documents"],
    "mail_address": "",
    "mail_provider": "",        # "outlook" | "gmail" | ""
    "data_repo": "",            # git working copy holding the shared registry
    "sync_roles": ["manuscript", "cover_letter", "response", "supplement", "refs"],
    "machine": "",              # label for files that stay on one machine
}


def load_config():
    cfg = dict(CONFIG_DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except (json.JSONDecodeError, OSError):
            pass
    if not cfg.get("machine"):
        import socket
        cfg["machine"] = socket.gethostname().split(".")[0]
    return cfg


def save_config(cfg):
    os.makedirs(ROOT, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return CONFIG_PATH

# --- vocabulary -------------------------------------------------------------

# Where a submission attempt stands. Ordered from earliest to terminal.
STATUSES = [
    "drafting",         # manuscript still being written
    "ready",            # complete, not sent
    "submitted",        # sent, no editor action yet
    "under_review",     # with reviewers
    "desk_rejection",   # refused by the editor without going to review
    "major_revision",
    "minor_revision",
    "revision_sent",    # revised version returned to the journal
    "accepted",
    "rejected",         # refused after peer review
    "withdrawn",
]

TERMINAL = {"accepted", "rejected", "desk_rejection", "withdrawn"}

# A rejection is not one thing. A desk rejection says nothing about the science
# — usually scope or format — so the next step is a different journal. A
# post-review rejection carries reviewer reasoning that a rewrite should use.
REJECTED = {"rejected", "desk_rejection"}
NEEDS_ACTION = {"major_revision", "minor_revision"}

# The extra state the user asked for: the cover letter is tracked on its own,
# separately from whether the package actually went out.
COVER_STATES = ["missing", "draft", "ready"]

# Where a *work unit* stands, independently of any journal. A manuscript can be
# finished (kesz) without being submitted; a research thread can be folyamatban
# with no submission at all. Submission status answers a different question.
PROJECT_STATES = [
    "folyamatban",   # aktív munka
    "hianypotlas",   # hiányzik valami, mielőtt tovább mehet
    "korrekcio",     # javítás alatt (bírálat vagy saját átnézés után)
    "kesz",          # ✓ kész, lezárt munka
    "elfogadva",     # elfogadva közlésre
    "elutasitva",    # elutasítva
]

PROJECT_STATE_LABEL = {
    "folyamatban": "folyamatban",
    "hianypotlas": "hiánypótlás",
    "korrekcio": "korrekció",
    "kesz": "kész ✓",
    "elfogadva": "elfogadva",
    "elutasitva": "elutasítva",
}

# What kind of work a unit is. Only `kutatas` is held to a submission
# checklist; the rest are real work with no manuscript to submit.
CATEGORIES = {
    "kutatas": "kutatás / kézirat",
    "tamogato": "támogató kutatás (nem kézirat)",
    "eszkoz": "eszköz- és specialista-konfiguráció",
    "pelda": "platform példaprojekt",
}
MANUSCRIPT_CATEGORIES = {"kutatas"}

# Which submission status implies which project state, when we can tell.
STATE_FROM_STATUS = {
    "accepted": "elfogadva",
    "rejected": "elutasitva",
    "desk_rejection": "elutasitva",
    "withdrawn": "elutasitva",
    "major_revision": "korrekcio",
    "minor_revision": "korrekcio",
    "revision_sent": "folyamatban",
    "ready": "kesz",
}

FILE_ROLES = [
    "manuscript", "cover_letter", "response", "supplement",
    "figure", "table", "refs", "data", "code", "session", "other",
]

REVIEW_STATES = ["open", "in_progress", "answered"]
POINT_STATES = ["open", "drafted", "done", "declined"]


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today():
    return datetime.now().strftime("%Y-%m-%d")


def days_until(date_str):
    """Whole days from today to an ISO date. None if unparseable/empty."""
    if not date_str:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(date_str))
    if not m:
        return None
    try:
        target = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return (target.date() - datetime.now().date()).days


def slugify(text):
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return re.sub(r"-{2,}", "-", text)[:48] or "untitled"


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id          INTEGER PRIMARY KEY,
  slug        TEXT UNIQUE NOT NULL,
  title       TEXT NOT NULL,
  kind        TEXT NOT NULL DEFAULT 'article',
  root_path   TEXT NOT NULL DEFAULT '',
  lang        TEXT NOT NULL DEFAULT 'en',
  notes       TEXT NOT NULL DEFAULT '',
  archived    INTEGER NOT NULL DEFAULT 0,
  state       TEXT NOT NULL DEFAULT 'folyamatban',
  category    TEXT NOT NULL DEFAULT 'kutatas',
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,
  path        TEXT NOT NULL,
  label       TEXT NOT NULL DEFAULT '',
  added_at    TEXT NOT NULL,
  UNIQUE(project_id, role, path)
);

CREATE TABLE IF NOT EXISTS submissions (
  id                INTEGER PRIMARY KEY,
  project_id        INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  seq               INTEGER NOT NULL,
  journal           TEXT NOT NULL,
  portal            TEXT NOT NULL DEFAULT '',
  journal_ms_id     TEXT NOT NULL DEFAULT '',
  status            TEXT NOT NULL DEFAULT 'drafting',
  cover_letter_path TEXT NOT NULL DEFAULT '',
  cover_letter_state TEXT NOT NULL DEFAULT 'missing',
  submitted         INTEGER NOT NULL DEFAULT 0,
  submitted_at      TEXT NOT NULL DEFAULT '',
  decision          TEXT NOT NULL DEFAULT '',
  decision_at       TEXT NOT NULL DEFAULT '',
  due_at            TEXT NOT NULL DEFAULT '',
  notes             TEXT NOT NULL DEFAULT '',
  created_at        TEXT NOT NULL,
  UNIQUE(project_id, seq)
);

CREATE TABLE IF NOT EXISTS events (
  id            INTEGER PRIMARY KEY,
  project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  submission_id INTEGER REFERENCES submissions(id) ON DELETE CASCADE,
  at            TEXT NOT NULL,
  kind          TEXT NOT NULL,
  summary       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reviews (
  id            INTEGER PRIMARY KEY,
  submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  received_at   TEXT NOT NULL DEFAULT '',
  source        TEXT NOT NULL DEFAULT 'manual',
  decision      TEXT NOT NULL DEFAULT '',
  due_at        TEXT NOT NULL DEFAULT '',
  letter_path   TEXT NOT NULL DEFAULT '',
  editor        TEXT NOT NULL DEFAULT '',
  state         TEXT NOT NULL DEFAULT 'open',
  notes         TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_points (
  id         INTEGER PRIMARY KEY,
  review_id  INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  reviewer   TEXT NOT NULL DEFAULT 'R1',
  idx        INTEGER NOT NULL DEFAULT 0,
  comment    TEXT NOT NULL,
  severity   TEXT NOT NULL DEFAULT 'normal',
  targets    TEXT NOT NULL DEFAULT '',
  response   TEXT NOT NULL DEFAULT '',
  action     TEXT NOT NULL DEFAULT '',
  state      TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS checklist (
  id            INTEGER PRIMARY KEY,
  submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  idx           INTEGER NOT NULL DEFAULT 0,
  label         TEXT NOT NULL,
  done          INTEGER NOT NULL DEFAULT 0,
  na            INTEGER NOT NULL DEFAULT 0,
  note          TEXT NOT NULL DEFAULT '',
  UNIQUE(submission_id, label)
);

CREATE INDEX IF NOT EXISTS idx_checklist_sub ON checklist(submission_id);
CREATE INDEX IF NOT EXISTS idx_sub_project ON submissions(project_id);
CREATE INDEX IF NOT EXISTS idx_files_project ON files(project_id);
CREATE INDEX IF NOT EXISTS idx_points_review ON review_points(review_id);
CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id, at);
"""


# Columns added after the first release. Applied on every connect; adding a
# column that is already there is not an error worth surfacing.
MIGRATIONS = [
    ("projects", "state", "TEXT NOT NULL DEFAULT 'folyamatban'"),
    ("projects", "category", "TEXT NOT NULL DEFAULT 'kutatas'"),
]


def connect():
    os.makedirs(ROOT, exist_ok=True)
    os.makedirs(LETTERS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    for table, column, decl in MIGRATIONS:
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    conn.commit()
    return conn


# --- lookups ----------------------------------------------------------------

class NotFound(Exception):
    pass


def get_project(conn, ref):
    """Resolve a project by slug, id, or unique title prefix."""
    ref = str(ref).strip()
    row = conn.execute("SELECT * FROM projects WHERE slug = ?", (ref,)).fetchone()
    if row:
        return row
    if ref.isdigit():
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (int(ref),)).fetchone()
        if row:
            return row
    rows = conn.execute(
        "SELECT * FROM projects WHERE slug LIKE ? OR lower(title) LIKE ?",
        (f"%{ref}%", f"%{ref.lower()}%"),
    ).fetchall()
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        names = ", ".join(r["slug"] for r in rows)
        raise NotFound(f"'{ref}' is ambiguous — matches: {names}")
    raise NotFound(f"no project matches '{ref}'")


def current_submission(conn, project_id):
    """The live attempt: highest seq that is not terminal, else highest seq."""
    rows = conn.execute(
        "SELECT * FROM submissions WHERE project_id = ? ORDER BY seq DESC",
        (project_id,),
    ).fetchall()
    if not rows:
        return None
    for r in rows:
        if r["status"] not in TERMINAL:
            return r
    return rows[0]


def submissions_of(conn, project_id):
    return conn.execute(
        "SELECT * FROM submissions WHERE project_id = ? ORDER BY seq",
        (project_id,),
    ).fetchall()


def files_of(conn, project_id, role=None):
    if role:
        return conn.execute(
            "SELECT * FROM files WHERE project_id = ? AND role = ? ORDER BY path",
            (project_id, role),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM files WHERE project_id = ? ORDER BY role, path",
        (project_id,),
    ).fetchall()


_REVIEW_Q = ("SELECT r.*, s.project_id, s.journal, p.slug, p.title "
             "FROM reviews r "
             "JOIN submissions s ON s.id = r.submission_id "
             "JOIN projects p ON p.id = s.project_id ")


def open_reviews(conn, submission_id=None):
    """Reviews still needing work. Answered ones are history, not a to-do."""
    if submission_id:
        return conn.execute(
            _REVIEW_Q + "WHERE r.submission_id = ? AND r.state != 'answered' "
            "ORDER BY r.id DESC", (submission_id,)).fetchall()
    return conn.execute(
        _REVIEW_Q + "WHERE r.state != 'answered' ORDER BY r.due_at, r.id").fetchall()


def all_reviews(conn, submission_id):
    """Every review for a submission, answered ones included."""
    return conn.execute(_REVIEW_Q + "WHERE r.submission_id = ? ORDER BY r.id",
                        (submission_id,)).fetchall()


def point_progress(conn, review_id):
    rows = conn.execute(
        "SELECT state, COUNT(*) n FROM review_points WHERE review_id = ? GROUP BY state",
        (review_id,),
    ).fetchall()
    counts = {r["state"]: r["n"] for r in rows}
    total = sum(counts.values())
    done = counts.get("done", 0) + counts.get("declined", 0)
    return done, total


def log_event(conn, project_id, kind, summary, submission_id=None):
    conn.execute(
        "INSERT INTO events (project_id, submission_id, at, kind, summary) "
        "VALUES (?,?,?,?,?)",
        (project_id, submission_id, now(), kind, summary),
    )


# --- presentation helpers ---------------------------------------------------

STATUS_LABEL = {
    "drafting": "írás alatt",
    "ready": "kész, nincs beküldve",
    "submitted": "beküldve",
    "under_review": "peer-review alatt",
    "desk_rejection": "desk rejection",
    "major_revision": "major revision",
    "minor_revision": "minor revision",
    "revision_sent": "javítás visszaküldve",
    "accepted": "elfogadva",
    "rejected": "elutasítva",
    "withdrawn": "visszavonva",
}

COVER_LABEL = {"missing": "nincs", "draft": "piszkozat", "ready": "kész"}


def submitted_label(sub):
    """The headline the user asked for: cover letter state + is it actually in."""
    if sub is None:
        return "nincs beadás"
    cover = COVER_LABEL.get(sub["cover_letter_state"], sub["cover_letter_state"])
    if sub["submitted"]:
        when = sub["submitted_at"] or "?"
        return f"cover: {cover} · BEKÜLDVE {when}"
    return f"cover: {cover} · NINCS beküldve"


# --- submission-readiness checklist -----------------------------------------

# Journal-agnostic items every submission needs, in the order a submission
# portal usually asks for them.
CHECKLIST_BASE = [
    "Címoldal: szerzők, affiliációk, levelező szerző",
    "Absztrakt a folyóirat formátumában és szóhatárán belül",
    "Szószám ellenőrizve a folyóirat limitje ellen",
    "Cover letter kész",
    "Hivatkozások a folyóirat stílusában, minden DOI feloldva",
    "Ábrák külön fájlban, előírt felbontásban",
    "Táblázatok szerkeszthető formában (nem kép)",
    "Supplementary fájlok listázva és hivatkozva a szövegben",
    "Etikai nyilatkozat / IRB engedély",
    "Funding statement",
    "Conflict of interest / Disclosure",
    "Data availability statement",
    "Author contributions (CRediT)",
    "ORCID minden szerzőnél",
    "AI-használat nyilatkozata",
    "Javasolt bírálók megadva",
]

# Extra items that only apply to certain article types.
CHECKLIST_BY_KIND = {
    "systematic-review": [
        "PRISMA 2020 flow diagram a tényleges számokkal",
        "PRISMA 2020 checklist csatolva",
        "Protokoll-regisztráció (PROSPERO) vagy annak hiánya indokolva",
        "Risk-of-bias értékelés (RoB 2 / ROBINS-I)",
        "Teljes keresési stratégia adatbázisonként",
    ],
    "review": [
        "Keresési stratégia dokumentálva",
        "Evidenciaszint minden oksági állításnál jelölve",
    ],
    "hypothesis": [
        "Hipotézisek falszifikálhatóan megfogalmazva",
        "Modell / kód elérhetővé téve",
    ],
    "position": [
        "Az állásfoglalás és az evidencia egyértelműen elválasztva",
    ],
    "article": [
        "Reporting guideline (STROBE / CONSORT) csatolva",
        "Etikai engedély száma a szövegben",
    ],
    "protocol": [
        "SPIRIT checklist csatolva",
        "Regisztrációs szám megadva",
    ],
}


def seed_checklist(conn, submission_id, kind):
    """Create the checklist rows for a submission. Existing rows are kept."""
    items = CHECKLIST_BASE + CHECKLIST_BY_KIND.get(kind, [])
    for i, label in enumerate(items):
        conn.execute(
            "INSERT OR IGNORE INTO checklist (submission_id, idx, label) VALUES (?,?,?)",
            (submission_id, i, label))
    return len(items)


def checklist_of(conn, submission_id):
    return conn.execute(
        "SELECT * FROM checklist WHERE submission_id = ? ORDER BY idx, id",
        (submission_id,)).fetchall()


def checklist_progress(conn, submission_id):
    rows = checklist_of(conn, submission_id)
    live = [r for r in rows if not r["na"]]
    return sum(1 for r in live if r["done"]), len(live)


# --- gap analysis -----------------------------------------------------------

def gaps(conn, project, sub):
    """What is missing or inconsistent. Each gap carries the command that fixes it.

    severity: 'blocker' stops a submission, 'warn' needs attention, 'info' is
    bookkeeping. `fix` is a shell command; `ask` is a slash command for the
    things only a session can do.
    """
    slug = project["slug"]
    out = []
    # Tooling and demo units are real work, but they have no manuscript, no
    # cover letter and no journal — holding them to a submission checklist
    # would fill the list with noise that can never be cleared.
    manuscript_work = (project["category"] if "category" in project.keys()
                       else "kutatas") in MANUSCRIPT_CATEGORIES

    def add(sev, text, fix=None, ask=None):
        out.append({"severity": sev, "text": text, "fix": fix, "ask": ask})

    missing = [f["path"] for f in files_of(conn, project["id"])
               if not os.path.exists(f["path"])]
    if missing:
        add("warn", f"{len(missing)} nyilvántartott fájl nincs meg a lemezen",
            fix=f"sm.py show {slug}")

    if not manuscript_work:
        return out

    if not files_of(conn, project["id"], "manuscript"):
        add("blocker", "Nincs nyilvántartva kézirat-fájl",
            ask=f"/sm:scan {project['root_path']}" if project["root_path"] else None)

    if sub is None:
        add("warn", "Nincs megnyitott beadás",
            fix=f'sm.py submit {slug} --journal "..."')
        return out

    if sub["cover_letter_state"] == "missing":
        add("blocker", "Nincs cover letter",
            fix=f"sm.py submit {slug} --cover PATH --cover-state ready")
    elif sub["cover_letter_state"] == "draft":
        add("warn", "A cover letter csak piszkozat",
            fix=f"sm.py submit {slug} --cover-state ready")

    done, total = checklist_progress(conn, sub["id"])
    if total == 0:
        add("info", "A beadási checklist nincs létrehozva",
            fix=f"sm.py checklist init {slug}")
    elif done < total:
        add("warn" if sub["status"] in ("ready", "drafting") else "info",
            f"Beadási checklist: {total - done} tétel nyitva",
            fix=f"sm.py checklist show {slug}")

    if sub["submitted"] and not sub["journal_ms_id"]:
        add("info", "Nincs rögzítve a folyóirat kéziratazonosítója",
            fix=f'sm.py submit {slug} --ms-id "..."', ask="/sm:inbox")
    if sub["submitted"] and not sub["submitted_at"]:
        add("info", "Beküldve, de dátum nélkül",
            fix=f"sm.py submit {slug} --sent --date YYYY-MM-DD")
    if not sub["submitted"] and sub["status"] == "ready":
        add("blocker", f"Kész, de nincs beküldve ide: {sub['journal']}",
            fix=f"sm.py submit {slug} --sent")

    revs = open_reviews(conn, sub["id"])
    if sub["status"] in NEEDS_ACTION and not revs:
        add("blocker", "Revíziót kértek, de nincs betöltve bírálói levél",
            ask=f"/sm:review {slug}")
    if sub["status"] in REJECTED:
        which = ("Desk rejection" if sub["status"] == "desk_rejection"
                 else "Bírálat utáni elutasítás")
        add("warn", f"{which} — nincs kijelölve új folyóirat",
            ask=f"/sm:journal {slug}")
    for rv in revs:
        rdone, rtotal = point_progress(conn, rv["id"])
        if rtotal == 0:
            add("blocker", f"A #{rv['id']} bírálat nincs pontokra bontva",
                ask=f"/sm:review {slug}")
        elif rdone < rtotal:
            d = days_until(rv["due_at"])
            sev = "blocker" if (d is not None and d <= 14) else "warn"
            add(sev, f"{rtotal - rdone} megválaszolatlan bírálói pont"
                     + (f", {d} nap a határidőig" if d is not None else ""),
                ask=f"/sm:respond {rv['id']}")
    if sub["status"] in NEEDS_ACTION and not sub["due_at"]:
        add("warn", "Revízió határidő nélkül",
            fix=f"sm.py submit {slug} --due YYYY-MM-DD")

    return out


def suggest_state(conn, project, sub):
    """-> (state, definite).

    `definite` means the record itself settles it — an editor accepted or
    rejected it, or a revision was requested. Those override whatever was set
    by hand, because they are facts. Everything else is a guess and must not
    clobber a state the user chose.
    """
    if sub is not None:
        mapped = STATE_FROM_STATUS.get(sub["status"])
        if mapped in ("elfogadva", "elutasitva", "korrekcio"):
            return mapped, True
        if mapped == "kesz":
            # 'ready' only means kész if nothing is actually missing.
            if any(g["severity"] == "blocker" for g in gaps(conn, project, sub)):
                return "hianypotlas", False
            return "kesz", False
        if mapped or sub["status"] in ("submitted", "under_review"):
            return "folyamatban", False
    if any(g["severity"] == "blocker" for g in gaps(conn, project, sub)):
        return "hianypotlas", False
    return "folyamatban", False


def die(msg, code=2):
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def dump_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
