#!/usr/bin/env python3
"""cognify — turn stored facts into a graph, the way Cognee's cognify stage does.

What this borrows, and what it does not
---------------------------------------
Cognee splits memory into three phases: add (ingest), cognify (extract
structure), memify (refine it afterwards). memo-guard already had add — archive
and distil — and had vectors, but its graph was empty in practice because every
edge had to be created by hand. That is the gap this fills.

Cognee itself is not a dependency here. It is a pip package with database and
LLM-provider backends, and this plugin's hooks run on every tool call; the
stdlib-only property is load-bearing, not an aesthetic. So the semantics are
reimplemented on what is already present: SQLite, FTS5, the vector store, the
edge table, and a local model when one is reachable.

Four stages, each degrading rather than failing:

  classify   assign a kind (decision/constraint/finding/reference). Rules first;
             the model is only asked about what rules could not settle.
  extract    pull entities and relations out of claim text. With a model this is
             real extraction; without one it falls back to capitalised-phrase
             and identifier heuristics, which are worse but not useless.
  link       facts sharing an entity get an edge. This is where an empty graph
             becomes a connected one, and it is the whole point.
  summarise  left to compressor.py, which already builds the RESUME.

Every model call goes through broker.slot(), so cognify cannot starve a
compression that is already running, and gives up on a deadline instead of
blocking.

  cognify.py --run                 process facts that have no entities yet
  cognify.py --run --all           reprocess everything
  cognify.py --stats               entities, edges, coverage
  cognify.py --entities <fact-id>  what was extracted from one fact

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg          # noqa: E402
import memory as mem         # noqa: E402

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

SCHEMA = """
CREATE TABLE IF NOT EXISTS entity (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  norm       TEXT NOT NULL UNIQUE,
  etype      TEXT DEFAULT 'thing',
  first_seen REAL,
  mentions   INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS entity_norm ON entity(norm);
CREATE TABLE IF NOT EXISTS fact_entity (
  fact_id   INTEGER NOT NULL,
  entity_id INTEGER NOT NULL,
  PRIMARY KEY (fact_id, entity_id)
);
CREATE INDEX IF NOT EXISTS fe_entity ON fact_entity(entity_id);
CREATE TABLE IF NOT EXISTS cognified (
  fact_id INTEGER PRIMARY KEY,
  at      REAL,
  mode    TEXT
);
"""

# Rules run before the model, because most claims announce their own kind and
# asking an 8b model to re-decide what a regex already knows is pure latency.
KIND_RULES = [
    ("constraint", re.compile(
        r"\b(must|must not|may not|required|requires|forbid|forbidden|not allowed"
        r"|deadline|limit(ed)? to|no more than|at most|mandatory)\b", re.I)),
    ("decision", re.compile(
        r"\b(decided|chose|chosen|we will|agreed|settled on|opted|rejected"
        r"|switched to|dropped)\b", re.I)),
    ("reference", re.compile(
        r"(https?://|doi:|\bPMID\b|\bPROSPERO\b|\bissue #\d+|\bPR #\d+)", re.I)),
]

# Capitalised multiword names, ALLCAPS acronyms, identifiers with digits.
# Order matters: alternation is first-match-wins, so the longest forms must come
# first. With ACRONYM before identifier, "CRD42024518822" matched only "CRD" and
# the registration number — the part that identifies it — was thrown away.
_ENT_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}"                                 # 2026-03-01
    r"|[A-Za-z]{2,}[-_]?\d{3,}"                               # CRD42024518822, gfx1100
    r"|[A-Z][a-zA-Z0-9]*(?:[ -][A-Z][a-zA-Z0-9]*)+"           # Title Case Phrase
    r"|[A-Z]{2,}(?:-\d+)?)")                                  # ACRONYM, CR-14

# Stripped from the front of a captured name. "The PROSPERO ID" and "PROSPERO"
# must be the same entity or the two facts about it never link — which is
# exactly how the graph stayed empty.
_LEAD = re.compile(r"^(the|a|an|this|that|these|those|its|our|their)\s+", re.I)
_TRAIL = re.compile(r"\s+(id|ids|number|no|form|section|field|fields)$", re.I)

_ENT_STOP = {"the", "this", "that", "there", "then", "when", "with", "from",
             "and", "but", "for", "not", "all", "any", "one", "two", "i", "it"}


def connect() -> sqlite3.Connection:
    db = mem.connect()
    db.executescript(SCHEMA)
    return db


# --------------------------------------------------------------------------- classify

def classify(text: str) -> tuple[str, str]:
    """(kind, how). Rules settle most of it; 'unsure' is handed to the model."""
    for kind, rx in KIND_RULES:
        if rx.search(text):
            return kind, "rule"
    return "finding", "default"


# --------------------------------------------------------------------------- extract

def extract_deterministic(text: str) -> list[tuple[str, str]]:
    """(name, type) with no model. Worse than extraction, better than nothing."""
    out, seen = [], set()
    for m in _ENT_RE.finditer(text):
        name = m.group(0).strip(" -_")
        if len(name) < 3 or name.lower() in _ENT_STOP:
            continue
        n = name.lower()
        if n in seen:
            continue
        seen.add(n)
        etype = ("date" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", name)
                 else "identifier" if re.search(r"\d", name)
                 else "acronym" if name.isupper() else "name")
        out.append((name, etype))
    return out[:12]


_PROMPT = """Extract named entities from this sentence. Return ONLY a JSON array
of objects with "name" and "type". Types: person, org, work, identifier, date,
metric, thing. No prose, no markdown fence, at most 8 entities.

Sentence: {text}

JSON:"""


def extract_model(text: str, model: str, timeout: float = 30.0
                  ) -> list[tuple[str, str]] | None:
    try:
        req = urllib.request.Request(
            f"{OLLAMA}/api/generate",
            data=json.dumps({"model": model, "stream": False,
                             "prompt": _PROMPT.format(text=text),
                             "options": {"temperature": 0, "num_predict": 220}}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = json.loads(r.read()).get("response", "")
    except Exception:
        return None
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    out = []
    for d in data if isinstance(data, list) else []:
        if isinstance(d, dict) and d.get("name"):
            out.append((str(d["name"])[:80], str(d.get("type", "thing"))[:20]))
    return out[:8] or None


# --------------------------------------------------------------------------- link

def _norm_entity(name: str) -> str:
    n = _LEAD.sub("", name.strip())
    n = _TRAIL.sub("", n)
    return re.sub(r"[^a-z0-9]+", " ", n.lower()).strip()


def upsert_entity(db: sqlite3.Connection, name: str, etype: str) -> int | None:
    n = _norm_entity(name)
    if len(n) < 3 or n in _ENT_STOP:
        return None
    # Store the cleaned name, not the raw capture: "The trial" and "trial" are
    # one entity, and the display should say so too.
    display = _TRAIL.sub("", _LEAD.sub("", name.strip())) or name.strip()
    # mentions is NOT incremented here. It was, and re-running --all counted the
    # same fact again — PROSPERO showed "seen in 4 facts" when two mentioned it.
    # A stored counter drifts; a derived one cannot.
    db.execute("INSERT INTO entity (name,norm,etype,first_seen,mentions)"
               " VALUES (?,?,?,?,0) ON CONFLICT(norm) DO NOTHING",
               (display, n, etype, time.time()))
    row = db.execute("SELECT id FROM entity WHERE norm=?", (n,)).fetchone()
    return row[0] if row else None


def refresh_mentions(db: sqlite3.Connection) -> None:
    """Recompute mentions from the join table. Cheap, and always right."""
    db.execute("UPDATE entity SET mentions = ("
               " SELECT COUNT(*) FROM fact_entity WHERE entity_id = entity.id)")
    db.execute("DELETE FROM entity WHERE mentions = 0")
    db.commit()


def link_by_entity(db: sqlite3.Connection, fact_id: int, min_shared: int = 1,
                   max_links: int = 6) -> int:
    """Edge every fact that shares an entity with this one.

    Weight is the shared-entity count, normalised. An edge built from three
    shared entities is worth more than one built from a single incidental match,
    and graph expansion should feel that difference.
    """
    rows = db.execute(
        "SELECT fe2.fact_id, COUNT(*) AS shared FROM fact_entity fe1"
        " JOIN fact_entity fe2 ON fe1.entity_id = fe2.entity_id"
        " WHERE fe1.fact_id=? AND fe2.fact_id<>?"
        " GROUP BY fe2.fact_id HAVING shared>=?"
        " ORDER BY shared DESC LIMIT ?",
        (fact_id, fact_id, min_shared, max_links)).fetchall()
    n = 0
    for other, shared in rows:
        lo, hi = sorted((fact_id, other))
        db.execute("INSERT INTO edge (src,dst,rel,weight,created_at)"
                   " VALUES (?,?, 'relates_to', ?, ?)"
                   " ON CONFLICT(src,dst,rel) DO UPDATE SET weight=excluded.weight",
                   (lo, hi, min(1.0, 0.4 + 0.2 * shared), time.time()))
        n += 1
    return n


# --------------------------------------------------------------------------- run

def cognify_fact(db: sqlite3.Connection, fact_id: int, text: str,
                 model: str | None) -> dict:
    ents = extract_model(text, model) if model else None
    mode = "model" if ents else "deterministic"
    if not ents:
        ents = extract_deterministic(text)
    # Reprocessing must replace, not accumulate: a second extraction may find a
    # different set, and leaving the old rows means the fact keeps linking
    # through entities the current extraction no longer supports.
    db.execute("DELETE FROM fact_entity WHERE fact_id=?", (fact_id,))
    ids = [i for i in (upsert_entity(db, n, t) for n, t in ents) if i]
    for eid in ids:
        db.execute("INSERT OR IGNORE INTO fact_entity (fact_id,entity_id)"
                   " VALUES (?,?)", (fact_id, eid))
    kind, how = classify(text)
    if how == "rule":
        db.execute("UPDATE fact SET kind=? WHERE id=?", (kind, fact_id))
    links = link_by_entity(db, fact_id)
    db.execute("INSERT INTO cognified (fact_id,at,mode) VALUES (?,?,?)"
               " ON CONFLICT(fact_id) DO UPDATE SET at=excluded.at, mode=excluded.mode",
               (fact_id, time.time(), mode))
    db.commit()
    return {"fact_id": fact_id, "entities": len(ids), "links": links,
            "kind": kind, "mode": mode}


def run(db: sqlite3.Connection, redo: bool = False, limit: int = 500,
        use_model: bool = True) -> dict:
    q = ("SELECT id,text FROM fact" if redo else
         "SELECT f.id,f.text FROM fact f LEFT JOIN cognified c ON c.fact_id=f.id"
         " WHERE c.fact_id IS NULL")
    rows = list(db.execute(q + " LIMIT ?", (limit,)))
    if not rows:
        return {"processed": 0, "mode": "-", "entities": 0, "links": 0}

    model = None
    if use_model:
        try:
            import broker
            if broker.healthy(3.0):
                # Adaptive: the task picks the family, measured VRAM picks the size.
                model = broker.route("extract")
        except Exception:
            model = None

    ents = links = 0
    modes: dict[str, int] = {}
    if model:
        # Hold one slot for the whole batch. Reacquiring per fact would let a
        # compression interleave and thrash the model in and out of memory.
        import broker
        with broker.slot("model", deadline_s=120, owner="cognify",
                         model=model) as got:
            if not got:
                model = None
            else:
                for fid, text in rows:
                    broker.beat("model")
                    r = cognify_fact(db, fid, text, model)
                    ents += r["entities"]; links += r["links"]
                    modes[r["mode"]] = modes.get(r["mode"], 0) + 1
    if not model:
        for fid, text in rows:
            r = cognify_fact(db, fid, text, None)
            ents += r["entities"]; links += r["links"]
            modes[r["mode"]] = modes.get(r["mode"], 0) + 1
    refresh_mentions(db)
    return {"processed": len(rows), "entities": ents, "links": links,
            "mode": ", ".join(f"{k}={v}" for k, v in modes.items())}


# --------------------------------------------------------------------------- cli

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--all", action="store_true", help="reprocess every fact")
    ap.add_argument("--no-model", action="store_true",
                    help="deterministic extraction only")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--entities", metavar="FACT_ID")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = connect()

    if args.entities:
        rows = list(db.execute(
            "SELECT e.name,e.etype,e.mentions FROM fact_entity fe"
            " JOIN entity e ON e.id=fe.entity_id WHERE fe.fact_id=?",
            (args.entities,)))
        if not rows:
            print("no entities (not cognified yet?)")
            return 1
        for name, etype, men in rows:
            print(f"  {name:<34} {etype:<12} seen in {men} fact(s)")
        return 0

    if args.stats:
        nf = db.execute("SELECT COUNT(*) FROM fact").fetchone()[0]
        nc = db.execute("SELECT COUNT(*) FROM cognified").fetchone()[0]
        ne = db.execute("SELECT COUNT(*) FROM entity").fetchone()[0]
        nl = db.execute("SELECT COUNT(*) FROM edge").fetchone()[0]
        auto = db.execute("SELECT COUNT(*) FROM edge WHERE rel='relates_to'").fetchone()[0]
        d = {"facts": nf, "cognified": nc, "entities": ne, "edges": nl,
             "auto_edges": auto,
             "coverage": f"{(100.0*nc/nf if nf else 0):.0f}%"}
        if args.json:
            print(json.dumps(d, indent=2)); return 0
        for k, v in d.items():
            print(f"  {k:<12} {v}")
        top = list(db.execute(
            "SELECT name,mentions FROM entity ORDER BY mentions DESC LIMIT 8"))
        if top:
            print("\n  most connected entities:")
            for n, m in top:
                print(f"    {n:<34} {m}")
        return 0

    if args.run:
        r = run(db, redo=args.all, limit=args.limit, use_model=not args.no_model)
        print(json.dumps(r, indent=2) if args.json else
              f"cognified {r['processed']} fact(s): {r['entities']} entity links, "
              f"{r['links']} graph edges  [{r['mode']}]")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
