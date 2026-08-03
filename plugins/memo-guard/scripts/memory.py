#!/usr/bin/env python3
"""Long-term memory across projects — reachable only through a stated goal.

The control rule
----------------
Without a goal, you see the current project only. State a goal and the whole
store opens. That is the entire access model, and it is deliberate: an agent
that can silently reach into every project you have ever worked on will
eventually surface a claim from a clinical manuscript in an unrelated session.
Requiring a goal makes the reach an explicit act with a recorded reason, and it
gives retrieval something to rank against — "what did I learn that bears on
THIS" is answerable; "tell me everything you know" is not.

  memory.py --promote "PROSPERO ID was truncated by the submission form" \
            --kind constraint --goal "PMOS manuscript submission"
  memory.py --goal "preparing a health-economics review for BMC"   # opens everything
  memory.py --recall "reference style"          # current project only, no goal
  memory.py --projects            # what is in the store, per project
  memory.py --disable <slug>      # a project that must never be recalled from
  memory.py --forget <id>

Nothing enters this store on its own. Promotion is explicit unless you turn on
`auto_promote` in config.json, and even then only claims above a utility floor
are taken. A memory that fills itself becomes a memory you cannot trust.

Every returned fact carries its provenance — project, date, source — because a
fact from another project read as if it were current context is worse than not
recalling it at all.

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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402

KINDS = ("decision", "constraint", "finding", "reference")

SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
  id         INTEGER PRIMARY KEY,
  slug       TEXT UNIQUE NOT NULL,
  cwd        TEXT DEFAULT '',
  first_seen REAL,
  last_seen  REAL,
  enabled    INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS goal (
  id         INTEGER PRIMARY KEY,
  text       TEXT NOT NULL,
  norm       TEXT NOT NULL UNIQUE,
  created_at REAL,
  last_used  REAL,
  uses       INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fact (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL,
  goal_id     INTEGER,
  session_id  TEXT DEFAULT '',
  source      TEXT DEFAULT '',
  text        TEXT NOT NULL,
  norm        TEXT NOT NULL,
  kind        TEXT NOT NULL DEFAULT 'finding',
  anchor      TEXT DEFAULT '',
  utility     REAL DEFAULT 0,
  promoted_by TEXT DEFAULT 'manual',
  created_at  REAL,
  hits        INTEGER DEFAULT 0,
  last_hit    REAL,
  UNIQUE(project_id, norm)
);
CREATE INDEX IF NOT EXISTS fact_project ON fact(project_id);
CREATE INDEX IF NOT EXISTS fact_kind ON fact(kind);
-- NOT contentless. A contentless fts5 table cannot be DELETEd from by rowid;
-- the supported 'delete' command requires handing back exactly the values that
-- were indexed. cognify rewrites fact.kind after promotion, so those values had
-- already drifted by the time anything tried to delete — which corrupted the
-- index. Storing the text costs a few bytes per fact and makes DELETE correct.
CREATE VIRTUAL TABLE IF NOT EXISTS fact_fts USING fts5(text, kind);
CREATE TABLE IF NOT EXISTS edge (
  src        INTEGER NOT NULL,
  dst        INTEGER NOT NULL,
  rel        TEXT NOT NULL,
  weight     REAL DEFAULT 1.0,
  created_at REAL,
  PRIMARY KEY (src, dst, rel)
);
CREATE INDEX IF NOT EXISTS edge_src ON edge(src);
CREATE INDEX IF NOT EXISTS edge_dst ON edge(dst);
CREATE TABLE IF NOT EXISTS fact_vec (
  fact_id INTEGER NOT NULL,
  model   TEXT NOT NULL,
  dim     INTEGER NOT NULL,
  data    BLOB NOT NULL,
  PRIMARY KEY (fact_id, model)
);
-- A deletion has to travel, or it is not a deletion. Union merge alone means
-- every machine that still holds a fact resurrects it on the next sync, so
-- --forget and `memify --hard` were both silently undone. The fingerprint is
-- kept, never the text: a tombstone should not re-leak what was removed.
CREATE TABLE IF NOT EXISTS tombstone (
  fp         TEXT PRIMARY KEY,
  deleted_at REAL,
  machine    TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""

# `contradicts` and `supersedes` are the two that earn the graph its place: they
# are the relations a plain search cannot express, because the fact you need is
# precisely the one that does NOT match your query.
RELS = ("supersedes", "contradicts", "depends_on", "part_of", "relates_to")

# Measured, not chosen. See the gate in recall() for the bands this sits between.
SEMANTIC_FLOOR = float(os.environ.get("MEMO_SEMANTIC_FLOOR", "0.48"))

# Question words and function words. These carry no retrieval signal but appear
# in almost every stored fact, so an unfiltered query matches everything equally.
_QUERY_STOP = {
    "the", "and", "for", "was", "were", "are", "with", "that", "this", "from",
    "what", "which", "who", "whom", "whose", "how", "why", "when", "where",
    "many", "much", "did", "does", "do", "has", "have", "had", "been", "being",
    "can", "could", "would", "should", "will", "shall", "may", "might", "must",
    "about", "into", "over", "under", "than", "then", "there", "here", "some",
    "any", "all", "not", "but", "its", "their", "our", "your", "his", "her",
    "you", "take", "took", "get", "got", "want", "need", "use", "used",
}


def db_path() -> Path:
    return mg.data_dir() / "memory.db"


def connect() -> sqlite3.Connection:
    fresh = not db_path().exists()
    db = sqlite3.connect(db_path(), timeout=5.0)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    if fresh:
        db.execute("INSERT OR REPLACE INTO meta (k,v) VALUES ('schema_version','1')")
        db.commit()
    try:  # one file now holds facts from every project; keep it private
        db_path().chmod(0o600)
    except OSError:
        pass
    return db


# --------------------------------------------------------------------------- helpers

def _norm(text: str) -> str:
    t = re.sub(r"\s+", " ", text.strip().lower())
    return re.sub(r"[^a-z0-9\s.%<>=-]", "", t)


def project_id(db: sqlite3.Connection, cwd: str) -> int:
    slug = mg.project_slug(cwd)
    now = time.time()
    db.execute(
        "INSERT INTO project (slug,cwd,first_seen,last_seen) VALUES (?,?,?,?)"
        " ON CONFLICT(slug) DO UPDATE SET last_seen=excluded.last_seen",
        (slug, cwd, now, now))
    db.commit()
    return db.execute("SELECT id FROM project WHERE slug=?", (slug,)).fetchone()[0]


def goal_id(db: sqlite3.Connection, text: str | None) -> int | None:
    if not text:
        return None
    n = _norm(text)
    now = time.time()
    db.execute(
        "INSERT INTO goal (text,norm,created_at,last_used,uses) VALUES (?,?,?,?,1)"
        " ON CONFLICT(norm) DO UPDATE SET last_used=excluded.last_used, uses=uses+1",
        (text.strip(), n, now, now))
    db.commit()
    return db.execute("SELECT id FROM goal WHERE norm=?", (n,)).fetchone()[0]


def fts_delete(db: sqlite3.Connection, fid: int) -> None:
    """Remove a row from the search index. Mechanical, and says nothing.

    This must NOT record a tombstone. It briefly did, and the consequence was
    severe: promote() calls it as part of delete-then-reindex, so every fact was
    tombstoned by its own creation. Syncing then deleted the entire store on the
    receiving machine and skipped every incoming fact as already-deleted.
    Re-indexing is not a deletion; only forget() is.
    """
    try:
        db.execute("DELETE FROM fact_fts WHERE rowid=?", (fid,))
    except sqlite3.OperationalError:
        pass


def repair_tombstones(db: sqlite3.Connection) -> int:
    """Drop tombstones contradicted by a newer live fact.

    A tombstone and a live fact with the same fingerprint cannot both be true.
    v0.9.0 produced that state on every promotion — fts_delete recorded a
    tombstone and promote calls it while re-indexing — so a sync would have
    wiped the receiving machine. It also arises legitimately when a fact is
    deleted and later re-promoted. Both are settled the same way: whichever
    happened last wins, which is the only reading that does not lose work.
    """
    import sync
    killed = 0
    ts = {r[0]: (r[1] or 0) for r in db.execute("SELECT fp,deleted_at FROM tombstone")}
    for fid, text, created in db.execute("SELECT id,text,created_at FROM fact"):
        f = sync.fp(text)
        if f in ts and (created or 0) >= ts[f]:
            db.execute("DELETE FROM tombstone WHERE fp=?", (f,))
            killed += 1
    db.commit()
    return killed


def forget(db: sqlite3.Connection, fid: int) -> bool:
    """Delete a fact and record that the deletion happened.

    The tombstone is what makes a deletion survive a sync: without it, the next
    pull from any machine that still holds the fact simply puts it back. Only
    deliberate removal calls this — `--forget` and `memify --hard`.
    """
    row = db.execute("SELECT text FROM fact WHERE id=?", (fid,)).fetchone()
    if not row:
        return False
    try:
        import sync
        db.execute("INSERT INTO tombstone (fp,deleted_at,machine)"
                   " VALUES (?,?,?) ON CONFLICT(fp) DO NOTHING",
                   (sync.fp(row[0]), time.time(), os.uname().nodename))
    except Exception:
        pass
    fts_delete(db, fid)
    db.execute("DELETE FROM fact_vec WHERE fact_id=?", (fid,))
    db.execute("DELETE FROM edge WHERE src=? OR dst=?", (fid, fid))
    db.execute("DELETE FROM fact WHERE id=?", (fid,))
    db.commit()
    return True


def reindex_fts(db: sqlite3.Connection) -> int:
    """Rebuild the search index from `fact`, which is the source of truth.

    Also migrates a database created with the old contentless table: that one
    cannot be repaired in place, so it is dropped and rebuilt. No fact is lost —
    the index was only ever derived.
    """
    # Read the table's definition, not its behaviour. 'integrity-check' succeeds
    # on a contentless table too, so probing with it reported "not contentless"
    # every time and the migration never ran.
    row = db.execute("SELECT sql FROM sqlite_master WHERE name='fact_fts'").fetchone()
    contentless = bool(row) and "content=''" in (row[0] or "").replace(" ", "")
    cols = [r[1] for r in db.execute("PRAGMA table_info(fact_fts)")]
    if contentless or not cols:
        db.execute("DROP TABLE IF EXISTS fact_fts")
        db.execute("CREATE VIRTUAL TABLE fact_fts USING fts5(text, kind)")
    else:
        db.execute("DELETE FROM fact_fts")
    n = 0
    for fid, text, kind in db.execute("SELECT id,text,kind FROM fact"):
        db.execute("INSERT INTO fact_fts (rowid,text,kind) VALUES (?,?,?)",
                   (fid, text, kind))
        n += 1
    db.commit()
    return n


def _request_sync() -> None:
    """Ask for a coalesced background push. Never blocks, never raises."""
    try:
        if not mg.load_config().get("sync"):
            return
        import sync
        sync.request()
    except Exception:
        pass


def _cosine_all(qv: list[float], vecs: list, E) -> dict[int, float]:
    """Cosine of the query against every candidate vector.

    numpy is optional. When it is missing the loop below is identical in result,
    just slower — the plugin's stdlib-only promise is kept, and a machine with
    numpy simply gets a faster answer.
    """
    if not vecs:
        return {}
    try:
        import numpy as np
        import struct as _s
        dim = len(qv)
        mat = np.frombuffer(b"".join(b for _, b in vecs), dtype="<f4").reshape(len(vecs), dim)
        sims = mat @ np.asarray(qv, dtype="<f4")
        return {fid: float(s) for (fid, _), s in zip(vecs, sims)}
    except ImportError:
        return {fid: E.cosine(qv, E.unpack(blob)) for fid, blob in vecs}


def _refuted(text: str) -> bool:
    """A fact the claim store has since judged must never be recalled."""
    try:
        import claims as cl
        v = cl.match(cl.connect(), text)
        return bool(v and v["status"] == "REFUTED")
    except Exception:
        return False


# --------------------------------------------------------------------------- writes

def promote(db: sqlite3.Connection, text: str, cwd: str, kind: str = "finding",
            goal: str | None = None, source: str = "", anchor: str = "",
            session_id: str = "", utility: float = 0.0,
            by: str = "manual") -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    n = _norm(text)
    if len(n) < 12:
        raise ValueError("too short to be a useful memory")
    pid = project_id(db, cwd)
    gid = goal_id(db, goal)
    cur = db.execute(
        "INSERT INTO fact (project_id,goal_id,session_id,source,text,norm,kind,anchor,"
        "utility,promoted_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(project_id,norm) DO UPDATE SET kind=excluded.kind,"
        " goal_id=COALESCE(excluded.goal_id,fact.goal_id), anchor=excluded.anchor",
        (pid, gid, session_id, source, text.strip(), n, kind, anchor, utility, by,
         time.time()))
    db.commit()
    fid = cur.lastrowid or db.execute(
        "SELECT id FROM fact WHERE project_id=? AND norm=?", (pid, n)).fetchone()[0]
    # FTS5 has no UPSERT; delete-then-insert is the supported way to re-index.
    fts_delete(db, fid)
    db.execute("INSERT INTO fact_fts (rowid,text,kind) VALUES (?,?,?)",
               (fid, text.strip(), kind))
    _request_sync()
    # Both spaces, because which one a future query uses is not knowable now and
    # vectors from different models cannot be compared. Two embeds at write time
    # (rare) buys free model choice at read time (frequent).
    try:
        import embed as E
        for profile in ("bulk", "recall"):
            r = E.embed(text, profile=profile)
            if not r:
                continue
            v = E.normalize(r[1])
            db.execute("INSERT INTO fact_vec (fact_id,model,dim,data)"
                       " VALUES (?,?,?,?) ON CONFLICT(fact_id,model)"
                       " DO UPDATE SET data=excluded.data",
                       (fid, r[0], len(v), E.pack(v)))
    except Exception:
        pass
    db.commit()
    return {"id": fid, "kind": kind, "project": mg.project_slug(cwd)}


# --------------------------------------------------------------------------- reads

def recall(db: sqlite3.Connection, query: str, cwd: str, goal: str | None,
           budget_tokens: int = 700, limit: int = 40) -> dict:
    """The gate. No goal -> this project only. Goal -> the whole store.

    Cross-project facts are ranked below same-project ones even when the goal is
    stated: relevance to the current work is not the same as relevance to the
    words in the query, and the current project is the better prior.
    """
    pid = project_id(db, cwd)
    scope = "all projects" if goal else "current project only"
    if goal:
        goal_id(db, goal)

    # Candidates are ALL enabled facts, not the FTS hits. Using FTS as a gate is
    # the standard hybrid-retrieval mistake: when the query shares no words with
    # the right answer — exactly the case vectors exist to solve — the gate drops
    # it before the vector is ever consulted, and no re-ranking can bring it back.
    # FTS still runs, but only to contribute a lexical signal to the score.
    # Bounded by recency so a large store cannot make this loop unbounded.
    rows = list(db.execute(
        "SELECT f.id,f.text,f.kind,f.anchor,f.utility,f.hits,f.created_at,"
        "       p.slug,p.id,0"
        " FROM fact f JOIN project p ON p.id=f.project_id"
        " WHERE p.enabled=1 ORDER BY f.created_at DESC LIMIT 2000"))

    # Stopwords must go before the FTS match, not after. Left in, a question like
    # "how many people took part in the study" matches any fact containing "the",
    # and a position-based rank then hands that noise a perfect lexical score —
    # which is exactly how an unrelated fact won every query here.
    terms = [w for w in re.findall(r"[a-z0-9]{3,}", (query or goal or "").lower())
             if w not in _QUERY_STOP]
    lex_rank: dict[int, float] = {}
    if terms:
        q = " OR ".join(terms[:12])
        try:
            hits_ = list(db.execute(
                "SELECT fact_fts.rowid, bm25(fact_fts) AS r FROM fact_fts"
                " WHERE fact_fts MATCH ? ORDER BY r LIMIT 200", (q,)))
            # Magnitude, not position: bm25 is negative and more-negative is a
            # better match, so the best hit scores 1.0 and a weak hit scores in
            # proportion to how much worse it actually is.
            if hits_:
                best = min(r for _, r in hits_) or -1e-9
                lex_rank = {rid: max(0.0, min(1.0, r / best)) for rid, r in hits_}
        except sqlite3.OperationalError:
            lex_rank = {}

    # Vector comparison over EVERY candidate, not a slice of them. This was
    # capped at the 60 newest rows at first, which kept recall flat at ~60 ms
    # for any corpus size — because it was not doing the work. A fact with 60
    # newer facts in front of it became permanently unfindable: semantic search
    # never saw it, and the lexical path cannot find what shares no words with
    # the query. For a store whose purpose is recalling things from months ago,
    # that is the one failure that matters. numpy is used when present purely
    # for speed; the pure-Python path is the same computation.
    semantic: dict[int, float] = {}
    try:
        import embed as E
        qr = E.embed(query or goal or "", profile="recall")
        if qr:
            qv = E.normalize(qr[1])
            cand = {r[0] for r in rows}
            vecs = [(fid, blob) for fid, dim, blob in db.execute(
                "SELECT fact_id,dim,data FROM fact_vec WHERE model=? AND dim=?",
                (qr[0], len(qv))) if fid in cand]
            semantic = _cosine_all(qv, vecs, E)
    except Exception:
        semantic = {}

    now = time.time()
    scored = []
    n_rows = max(1, len(rows))
    for i, (fid, text, kind, anchor, util, hits, created, slug, fpid, rank) in enumerate(rows):
        same = fpid == pid
        if not same and not goal:
            continue  # the gate
        # rows arrive ordered by bm25 when FTS matched, so position IS relevance.
        # Without this the best answer to the question can rank last, which is
        # how a recall looks like it works and quietly returns the wrong facts.
        lex = lex_rank.get(fid, 0.0)
        sem = semantic.get(fid)
        # When both signals exist, semantic carries more: it is the one that can
        # tell "412 participants" from "n=412". Lexical stays in the blend as a
        # guard against an embedding that is confidently about the wrong topic.
        relevance = (0.35 * lex + 0.65 * max(0.0, sem)) if sem is not None else lex
        age_days = max(0.0, (now - (created or now)) / 86400)
        recency = 1.0 / (1.0 + age_days / 90.0)
        # `hits` is deliberately NOT scored. It fed back into ranking at first,
        # and a fact returned once scored higher, so it was returned again — a
        # rich-get-richer loop that made one fact win unrelated queries. It is a
        # usage statistic, not evidence of relevance.
        score = (0.70 * relevance + 0.10 * min(1.0, util) + 0.10 * recency
                 + (0.10 if same else 0.0))
        # Gate on the semantic score itself, never the composite. The composite
        # carries a constant floor (recency + same-project) that an irrelevant
        # fact collects for free, and cosine between unrelated text is ~0.3, not
        # 0 — so composite bands for real and nonsense queries overlap.
        # Measured on this corpus: relevant best 0.562-0.724, noise best
        # 0.320-0.408. SEMANTIC_FLOOR sits in that gap. Re-measure with
        # --calibrate after changing the embedding model.
        if sem is not None:
            if sem < SEMANTIC_FLOOR:
                continue
        elif relevance < 0.15:
            continue        # no embedder; fall back to a lexical floor
        scored.append((score, fid, text, kind, anchor, slug, same, created))
    scored.sort(reverse=True, key=lambda r: r[0])

    # Graph expansion. A fact that contradicts or supersedes a strong hit is
    # exactly what the query will not match — it uses different words, that is
    # what makes it a contradiction. Pulling one hop off the top hits is the
    # cheapest way to stop confidently recalling a fact that something else in
    # the store already overturned.
    seen_ids = {r[1] for r in scored}
    neighbours = []
    for score, fid, *_ in scored[:5]:
        for nid, rel, w in db.execute(
                "SELECT dst, rel, weight FROM edge WHERE src=?"
                " UNION SELECT src, rel, weight FROM edge WHERE dst=?", (fid, fid)):
            if nid in seen_ids:
                continue
            row = db.execute(
                "SELECT f.id,f.text,f.kind,f.anchor,p.slug,f.project_id,f.created_at"
                " FROM fact f JOIN project p ON p.id=f.project_id"
                " WHERE f.id=? AND p.enabled=1", (nid,)).fetchone()
            if not row:
                continue
            seen_ids.add(nid)
            boost = 1.0 if rel in ("contradicts", "supersedes") else 0.6
            neighbours.append((score * 0.8 * boost * w, row[0], row[1], row[2],
                               row[3], row[4], row[5] == pid, row[6], rel))
    scored = [(s, i, t, k, a, sl, sa, c, None) for s, i, t, k, a, sl, sa, c in scored]
    scored.extend(neighbours)
    scored.sort(reverse=True, key=lambda r: r[0])

    out, spent = [], 0
    for score, fid, text, kind, anchor, slug, same, created, via in scored:
        if _refuted(text):
            continue
        cost = len(text) // 4 + 12
        if spent + cost > budget_tokens:
            break
        spent += cost
        out.append({"id": fid, "text": text, "kind": kind, "anchor": anchor,
                    "project": slug, "same_project": same, "via": via,
                    "when": time.strftime("%Y-%m-%d", time.localtime(created or now)),
                    "score": round(score, 3)})
        db.execute("UPDATE fact SET hits=hits+1, last_hit=? WHERE id=?", (now, fid))
        if len(out) >= limit:
            break
    # Record which facts came back together. memify turns this into edge weight:
    # two facts repeatedly answering the same question belong to the same
    # question, which is evidence a keyword match cannot produce.
    if len(out) > 1:
        try:
            import memify
            memify.record_coaccess(db, [f["id"] for f in out])
        except Exception:
            pass
    db.commit()
    return {"scope": scope, "goal": goal, "returned": len(out),
            "tokens_est": spent, "budget": budget_tokens, "facts": out}


# --------------------------------------------------------------------------- cli

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--promote", metavar="TEXT")
    ap.add_argument("--kind", default="finding", choices=KINDS)
    ap.add_argument("--goal", metavar="TEXT")
    ap.add_argument("--recall", metavar="QUERY")
    ap.add_argument("--source", default="")
    ap.add_argument("--anchor", default="")
    ap.add_argument("--session", default="")
    ap.add_argument("--utility", type=float, default=0.0)
    ap.add_argument("--budget", type=int, default=700, help="max tokens to return")
    ap.add_argument("--cwd", default=str(Path.cwd()))
    ap.add_argument("--projects", action="store_true")
    ap.add_argument("--disable", metavar="SLUG")
    ap.add_argument("--enable", metavar="SLUG")
    ap.add_argument("--forget", metavar="ID")
    ap.add_argument("--repair", action="store_true",
                    help="drop tombstones contradicted by a newer live fact")
    ap.add_argument("--reindex", action="store_true",
                    help="rebuild the search index from the facts")
    ap.add_argument("--link", nargs=2, metavar=("SRC", "DST"))
    ap.add_argument("--rel", default="relates_to", choices=RELS)
    ap.add_argument("--weight", type=float, default=1.0)
    ap.add_argument("--neighbors", metavar="ID")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = connect()

    if args.promote:
        try:
            r = promote(db, args.promote, args.cwd, args.kind, args.goal,
                        args.source, args.anchor, args.session, args.utility)
        except ValueError as e:
            print(f"not promoted: {e}", file=sys.stderr)
            return 2
        print(json.dumps(r) if args.json else
              f"promoted [{r['id']}] {r['kind']} in {r['project']}")
        return 0

    if args.repair:
        print(f"removed {repair_tombstones(db)} contradicted tombstone(s)")
        return 0

    if args.reindex:
        n = reindex_fts(db)
        print(f"reindexed {n} fact(s)")
        return 0

    if args.link:
        src, dst = int(args.link[0]), int(args.link[1])
        for i in (src, dst):
            if not db.execute("SELECT 1 FROM fact WHERE id=?", (i,)).fetchone():
                print(f"no fact with id {i}", file=sys.stderr)
                return 2
        db.execute("INSERT INTO edge (src,dst,rel,weight,created_at)"
                   " VALUES (?,?,?,?,?) ON CONFLICT(src,dst,rel)"
                   " DO UPDATE SET weight=excluded.weight",
                   (src, dst, args.rel, args.weight, time.time()))
        db.commit()
        print(f"{src} --{args.rel}--> {dst}")
        return 0

    if args.neighbors:
        rows = list(db.execute(
            "SELECT e.rel, f.id, f.kind, f.text FROM edge e JOIN fact f"
            " ON f.id = CASE WHEN e.src=? THEN e.dst ELSE e.src END"
            " WHERE e.src=? OR e.dst=?",
            (args.neighbors, args.neighbors, args.neighbors)))
        if not rows:
            print("no edges")
            return 1
        for rel, fid, kind, text in rows:
            print(f"  --{rel}--> [{fid}] ({kind}) {text[:70]}")
        return 0

    if args.disable or args.enable:
        slug, val = (args.disable, 0) if args.disable else (args.enable, 1)
        cur = db.execute("UPDATE project SET enabled=? WHERE slug=?", (val, slug))
        db.commit()
        print(f"{'disabled' if val == 0 else 'enabled'}: {slug} "
              f"({cur.rowcount} row)")
        return 0 if cur.rowcount else 1

    if args.forget:
        ok = forget(db, int(args.forget))
        print(f"forgotten: {1 if ok else 0}")
        return 0 if ok else 1

    if args.projects:
        rows = list(db.execute(
            "SELECT p.slug,p.enabled,COUNT(f.id),MAX(f.created_at)"
            " FROM project p LEFT JOIN fact f ON f.project_id=p.id"
            " GROUP BY p.id ORDER BY COUNT(f.id) DESC"))
        if args.json:
            print(json.dumps([{"project": r[0], "enabled": bool(r[1]),
                               "facts": r[2]} for r in rows], indent=2))
            return 0
        if not rows:
            print("long-term memory is empty")
            print(f"store: {db_path()}")
            return 0
        print(f"{'project':<46}{'facts':>7}  state")
        print("-" * 66)
        for slug, en, n, last in rows:
            print(f"{slug[:44]:<46}{n:>7}  {'on' if en else 'DISABLED'}")
        return 0

    if args.recall is not None or args.goal:
        res = recall(db, args.recall or "", args.cwd, args.goal, args.budget)
        if args.json:
            print(json.dumps(res, indent=2))
            return 0
        print(f"scope: {res['scope']}   returned {res['returned']} fact(s), "
              f"~{res['tokens_est']}/{res['budget']} tok")
        if res["goal"]:
            print(f"goal : {res['goal']}")
        if not res["facts"]:
            print("\n(nothing recalled — promote something first, or state a goal "
                  "to open the whole store)")
            return 1
        print()
        for f in res["facts"]:
            where = "" if f["same_project"] else f"  ← {f['project']}"
            via = f"  (via {f['via']})" if f.get("via") else ""
            print(f"  [{f['kind']}]{via} {f['text']}")
            print(f"      {f['when']}{where}"
                  + (f"  {f['anchor']}" if f["anchor"] else ""))
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
