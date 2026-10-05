#!/usr/bin/env python3
"""Global corpus store: every memo-index claim from the configured roots, in one SQLite DB.

Why it exists. memo-index keeps one `.memo/index.db` per corpus and rebuilds it from
scratch; memo-guard's recall never read any of it. On 2026-10-03 the workspace corpus held
844,538 claims in 20,444 memos that no session could reach except by running memo_query.py
by hand. This is PLAN-sql-gpu.md Part A, adapted to what the plugin already has:

  - data_dir()/memo.db, WAL. A separate file from memory.db on purpose: memory.db's daily
    maintenance deletes edges/entities that do not point at a `fact` (memify.prune,
    cognify.refresh_mentions), so claim rows living there would be swept away.
  - memo-index's status vocabulary kept exactly (CONFIRMED / DRIFTED / NEEDS_AGENT /
    PENDING / UNSUPPORTED / REFUTED / STALE). REFUTED and STALE never surface.
  - Incremental: a memo is re-read only when its mtime/size changed, and re-imported only
    when its bytes changed. A full rebuild is never needed to stay current.
  - Fast path: when the root's own index.db already describes a memo byte-for-byte (same
    memo_sha), its claims, keywords and scores are copied from there; otherwise the memo is
    parsed with memo-index's own parser (memo_db.parse_memo_text), never a second regex.
  - Staged sources (a PDF memo's `source:` is the staged .txt name) resolve back to the
    real file through <memo_dir>/_source_map.tsv and _recover_map*.tsv.

  store.py --stats
  store.py --sync [--root PATH] [--full]
  store.py --search "query" [--project P] [--limit N] [--unproven] [--json]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import itertools
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mg_lib as mg  # noqa: E402

# 2 (0.15.3): the search index holds only claims that can be answers. REFUTED/STALE rows were
# 34% of claim_fts and took a third of every query's 300 candidates before Python threw
# them away (measured 2026-10-03: FTS 80 -> 49 MB, query 61 -> 15 ms with the pair fallback).
SCHEMA_VERSION = "2"
BLOCKED = ("REFUTED", "STALE")
UNPROVEN = ("NEEDS_AGENT", "PENDING", "UNSUPPORTED")
TRUST = {"CONFIRMED": 1.0, "DRIFTED": 0.9, "NEEDS_AGENT": 0.5, "PENDING": 0.4,
         "UNSUPPORTED": 0.15}
# Top-level folders that hold many projects: the project is the next level down.
CONTAINERS = {"kutatas", "github", "eszkoz", "eloadas", "tamogato", "NAA_projekt"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS root (
  id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, memo_dir TEXT NOT NULL,
  added_at REAL, synced_at REAL);
CREATE TABLE IF NOT EXISTS doc (
  id INTEGER PRIMARY KEY, root_id INTEGER NOT NULL, memo TEXT NOT NULL,
  memo_sha TEXT, memo_mtime REAL, memo_size INTEGER,
  source TEXT, path TEXT, project TEXT, src_sha TEXT, profile TEXT,
  claims_n INTEGER DEFAULT 0, synced_at REAL,
  UNIQUE(root_id, memo));
CREATE INDEX IF NOT EXISTS doc_path ON doc(root_id, path);
CREATE INDEX IF NOT EXISTS doc_project ON doc(project);
CREATE TABLE IF NOT EXISTS claim (
  id INTEGER PRIMARY KEY, doc_id INTEGER NOT NULL, cid TEXT NOT NULL,
  text TEXT NOT NULL, status TEXT NOT NULL,
  anchor_line INTEGER, anchor_snip TEXT, region_lo INTEGER, region_hi INTEGER,
  specificity REAL DEFAULT 0, utility REAL DEFAULT 0, keywords TEXT DEFAULT '',
  hits INTEGER DEFAULT 0, last_hit REAL);
CREATE INDEX IF NOT EXISTS claim_doc ON claim(doc_id);
CREATE INDEX IF NOT EXISTS claim_status ON claim(status);
CREATE VIEW IF NOT EXISTS claim_live AS
  SELECT id, text, keywords FROM claim WHERE status NOT IN ('REFUTED', 'STALE');
""" + """
CREATE VIRTUAL TABLE IF NOT EXISTS claim_fts USING fts5(
  text, keywords, content='claim_live', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2');
"""
FTS_V1 = "content='claim',"
# The WHEN clauses must mirror claim_live exactly. An external-content FTS5 'delete' for a row
# that was never indexed does not fail, it corrupts the index; so a row is only ever deleted
# from the index if its old status made it indexable, and only inserted if its new one does.
TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS claim_ai AFTER INSERT ON claim
  WHEN new.status NOT IN ('REFUTED', 'STALE') BEGIN
  INSERT INTO claim_fts(rowid, text, keywords) VALUES (new.id, new.text, new.keywords);
END;
CREATE TRIGGER IF NOT EXISTS claim_ad AFTER DELETE ON claim
  WHEN old.status NOT IN ('REFUTED', 'STALE') BEGIN
  INSERT INTO claim_fts(claim_fts, rowid, text, keywords)
  VALUES ('delete', old.id, old.text, old.keywords);
END;
CREATE TRIGGER IF NOT EXISTS claim_au AFTER UPDATE OF text, keywords, status ON claim BEGIN
  INSERT INTO claim_fts(claim_fts, rowid, text, keywords)
  SELECT 'delete', old.id, old.text, old.keywords WHERE old.status NOT IN ('REFUTED', 'STALE');
  INSERT INTO claim_fts(rowid, text, keywords)
  SELECT new.id, new.text, new.keywords WHERE new.status NOT IN ('REFUTED', 'STALE');
END;
"""

STOP = frozenset("""the and for are was were with that this from what which who how why when
where does did has have had been can could would should will may might must about into
over than then there here some any all not but its their our your you also show tell
find give list paper study studies""".split()) | mg.HU_STOP


def db_path() -> Path:
    return mg.data_dir() / "memo.db"


def connect(readonly: bool = False, timeout: float = 5.0) -> sqlite3.Connection:
    if readonly:
        db = sqlite3.connect(f"file:{db_path().as_posix()}?mode=ro", uri=True, timeout=timeout)
        return db
    fresh = not db_path().exists()
    db = sqlite3.connect(db_path(), timeout=timeout)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.executescript(SCHEMA)
    if fresh:
        db.executescript(TRIGGERS)
        db.execute("INSERT OR REPLACE INTO meta (k,v) VALUES ('schema_version',?)", (SCHEMA_VERSION,))
        db.commit()
    else:
        _migrate(db)
    mg.secure_file(db_path())
    return db


def _migrate(db: sqlite3.Connection) -> None:
    """v1 -> v2: rebuild the search index over claim_live. Seconds, not minutes (3.7 s for
    861k claims): FTS5 'rebuild' streams the view once. The claims themselves are untouched."""
    ver = (db.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone() or ["1"])[0]
    sql = (db.execute("SELECT sql FROM sqlite_master WHERE name='claim_fts'").fetchone() or [""])[0]
    if ver == SCHEMA_VERSION and FTS_V1 not in (sql or "").replace(" ", ""):
        db.executescript(TRIGGERS)
        return
    _drop_triggers(db)
    db.execute("DROP TABLE IF EXISTS claim_fts")
    db.executescript(SCHEMA)
    db.execute("INSERT INTO claim_fts(claim_fts) VALUES('rebuild')")
    db.executescript(TRIGGERS)
    db.execute("INSERT OR REPLACE INTO meta (k,v) VALUES ('schema_version',?)", (SCHEMA_VERSION,))
    db.commit()


# --------------------------------------------------------------------------- helpers

def _memo_index(cfg: dict):
    """memo-index's memo_db module (parser + scoring), from the configured skill path."""
    sd = Path(os.path.expanduser(cfg.get("memo_index_path", ""))) / "scripts"
    if str(sd) not in sys.path:
        sys.path.insert(0, str(sd))
    import memo_db  # noqa: E402
    return memo_db


def project_of(path: str) -> str:
    parts = [p for p in (path or "").replace("\\", "/").split("/") if p]
    if not parts:
        return "?"
    if len(parts) > 2 and parts[0] in CONTAINERS:
        return f"{parts[0]}/{parts[1]}"
    return parts[0] if len(parts) > 1 else "(root)"


def load_source_map(memo_dir: Path) -> dict[str, str]:
    """staged name -> original path relative to the root."""
    m: dict[str, str] = {}
    sm = memo_dir / "_source_map.tsv"
    if sm.exists():
        for ln in sm.read_text(encoding="utf-8").splitlines()[1:]:
            parts = ln.split("\t")
            if len(parts) >= 2:
                m[parts[0]] = parts[1]
    for f in glob.glob(str(memo_dir / "_recover_map*.tsv")):
        for ln in Path(f).read_text(encoding="utf-8").splitlines():
            parts = ln.split("\t")
            if len(parts) >= 2 and parts[0] != "-":
                m.setdefault(parts[0], parts[1])
    return m


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _frontmatter(raw: str) -> dict:
    fm = {}
    if raw.startswith("---"):
        for ln in raw.split("\n", 40)[1:40]:
            ln = ln.rstrip("\r")
            if ln == "---":
                break
            k, _, v = ln.partition(": ")
            if v:
                fm[k.strip()] = v.strip()
    return fm


# --------------------------------------------------------------------------- sync

def _drop_triggers(db):
    for t in ("claim_ai", "claim_ad", "claim_au"):
        db.execute(f"DROP TRIGGER IF EXISTS {t}")


def sync_root(root: Path, full: bool = False, cfg: dict | None = None, log=print) -> dict:
    """Bring the store in line with <root>/.memo. Returns counts."""
    cfg = cfg or mg.load_config()
    root = Path(os.path.expanduser(str(root))).resolve()
    memo_dir = root / ".memo"
    if not memo_dir.is_dir():
        raise SystemExit(f"no memo dir: {memo_dir}")
    try:
        md = _memo_index(cfg)
    except Exception:
        md = None          # memo-index not installed: fall back to the plain line grammar
    db = connect()
    t0 = time.time()
    db.execute("INSERT OR IGNORE INTO root (path, memo_dir, added_at) VALUES (?,?,?)",
               (str(root), str(memo_dir), t0))
    rid = db.execute("SELECT id FROM root WHERE path=?", (str(root),)).fetchone()[0]
    smap = load_source_map(memo_dir)

    known = {r[0]: r[1:] for r in db.execute(
        "SELECT memo, id, memo_sha, memo_mtime, memo_size FROM doc WHERE root_id=?", (rid,))}
    on_disk = {p.name: p for p in memo_dir.glob("*.memo.md")}
    # corpus_exclude (0.15.13): the memo of an excluded path leaves the store like a deleted one.
    excluded = set()
    if cfg.get("corpus_exclude"):
        excluded = {m for m, path in db.execute("SELECT memo, path FROM doc WHERE root_id=?", (rid,))
                    if path and mg.corpus_excluded(path, cfg)}

    # 1) what changed
    todo = []
    for name, p in on_disk.items():
        if name in excluded:
            continue
        st = p.stat()
        k = known.get(name)
        if not full and k and k[2] == st.st_mtime and k[3] == st.st_size:
            continue
        todo.append((name, p, st))
    gone = [name for name in known if name not in on_disk or name in excluded]
    bulk = full or len(todo) > 2000
    if bulk:
        _drop_triggers(db)

    # 2) fast path from the root's own index.db where it describes the memo exactly
    fast: dict[str, tuple] = {}
    idx = memo_dir / "index.db"
    if idx.exists() and todo:
        try:
            src = sqlite3.connect(f"file:{idx.as_posix()}?mode=ro", uri=True, timeout=2.0)
            shas = dict(src.execute("SELECT path, memo_sha FROM memos"))
            fast = {"shas": shas, "conn": src}
        except sqlite3.Error:
            fast = {}

    added = changed = same = claims_n = 0
    for name, p, st in todo:
        raw_b = p.read_bytes()
        sha = hashlib.sha256(raw_b).hexdigest()
        k = known.get(name)
        if k and k[1] == sha:          # touched, not changed
            db.execute("UPDATE doc SET memo_mtime=?, memo_size=? WHERE id=?",
                       (st.st_mtime, st.st_size, k[0]))
            same += 1
            continue
        raw = raw_b.decode("utf-8", errors="replace")
        fm = _frontmatter(raw)
        source = fm.get("source", "")
        native = (root / source)
        if source and native.is_file():
            path = source.replace("\\", "/")
        else:
            path = smap.get(source, source).replace("\\", "/")
        if mg.corpus_excluded(path, cfg):
            if k:
                gone.append(name)
            continue
        old: dict = {}
        if k:
            for row in db.execute(
                    "SELECT id, cid, text, status, anchor_line, anchor_snip, region_lo, region_hi,"
                    " specificity, utility, keywords FROM claim WHERE doc_id=?", (k[0],)):
                old.setdefault((row[1], row[2]), []).append((row[0], row[3:]))
            db.execute("UPDATE doc SET memo_sha=?, memo_mtime=?, memo_size=?, source=?, path=?,"
                       " project=?, src_sha=?, profile=?, synced_at=? WHERE id=?",
                       (sha, st.st_mtime, st.st_size, source, path, project_of(path),
                        fm.get("sha256"), fm.get("profile"), t0, k[0]))
            did = k[0]; changed += 1
        else:
            cur = db.execute(
                "INSERT INTO doc (root_id, memo, memo_sha, memo_mtime, memo_size, source, path,"
                " project, src_sha, profile, synced_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rid, name, sha, st.st_mtime, st.st_size, source, path, project_of(path),
                 fm.get("sha256"), fm.get("profile"), t0))
            did = cur.lastrowid; added += 1

        rows = None
        if fast and fast["shas"].get(name) == sha:
            rows = _claims_from_index(fast["conn"], name)
        if rows is None:
            rows = _claims_from_memo(md, raw)
        # Re-import in place. A claim whose memo id and text are unchanged keeps its row, so
        # its vector, concept membership and recall hits survive a pass that only changed
        # statuses or anchors. Deleting and re-inserting every claim, as before, would have
        # thrown away about 450k vectors after the 2026-10-04 re-verification (18,833
        # memos rewritten, texts untouched): 1.5 GPU-hours of re-embedding unchanged text.
        new_rows, upd = [], []
        for r in rows:
            prev = old.get((r[0], r[1]))
            if prev:
                cl_id, vals = prev.pop()
                if tuple(vals) != tuple(r[2:]):
                    upd.append(tuple(r[2:]) + (cl_id,))
            else:
                new_rows.append(r)
        gone_ids = [cl_id for prev in old.values() for cl_id, _ in prev]
        for i in range(0, len(gone_ids), 500):
            part = gone_ids[i:i + 500]
            db.execute(f"DELETE FROM claim WHERE id IN ({','.join('?' * len(part))})", part)
        db.executemany(
            "UPDATE claim SET status=?, anchor_line=?, anchor_snip=?, region_lo=?, region_hi=?,"
            " specificity=?, utility=?, keywords=? WHERE id=?", upd)
        db.executemany(
            "INSERT INTO claim (doc_id, cid, text, status, anchor_line, anchor_snip, region_lo,"
            " region_hi, specificity, utility, keywords) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(did,) + r for r in new_rows])
        db.execute("UPDATE doc SET claims_n=? WHERE id=?", (len(rows), did))
        claims_n += len(rows)
        if (added + changed) % 2000 == 0:
            db.commit()
            log(f"  ... {added + changed}/{len(todo)} memo")

    for name in gone:
        did = known[name][0]
        db.execute("DELETE FROM claim WHERE doc_id=?", (did,))
        db.execute("DELETE FROM doc WHERE id=?", (did,))
    if bulk:
        db.execute("INSERT INTO claim_fts(claim_fts) VALUES('rebuild')")
        db.executescript(TRIGGERS)
    db.execute("UPDATE root SET synced_at=? WHERE id=?", (time.time(), rid))
    db.commit()
    if fast:
        fast["conn"].close()
    if added or changed or gone:
        import dbmaint
        dbmaint.light_conn(db, ["claim_fts"])
    res = {"root": str(root), "added": added, "changed": changed, "unchanged_touched": same,
           "removed": len(gone), "claims_written": claims_n, "seconds": round(time.time() - t0, 1)}
    mg.append_metrics({"ts": time.time(), **res}, event="store_sync")
    return res


def _claims_from_index(src: sqlite3.Connection, memo_name: str):
    rows = src.execute(
        "SELECT c.rowid, c.claim_id, c.text, c.status, c.anchor_line, c.anchor_snip,"
        " c.region_lo, c.region_hi, c.specificity, c.utility FROM claims c WHERE c.memo=?",
        (memo_name,)).fetchall()
    if not rows:
        return None
    kws = {}
    ids = [r[0] for r in rows]
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        for rid, kw in src.execute(
                f"SELECT claim_rowid, group_concat(keyword, ' ') FROM kw WHERE claim_rowid IN"
                f" ({','.join('?' * len(part))}) GROUP BY claim_rowid", part):
            kws[rid] = kw
    return [(r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8] or 0.0, r[9] or 0.0,
             kws.get(r[0], "")) for r in rows]


# Only used when memo-index is not installed (a published-plugin user, a CI box): the same
# line grammar as memo_db.CLAIM_RE, with neutral scores instead of memo_db's keyword model.
_CLAIM_RE = re.compile(r"^- \[C(\d+)\] \[(\w+)\] (.*?) (?:@L(\d+) `([^`]*)`|@semantic L(\d+)-(\d+))"
                       r"\s*(?:<!--(.*)-->)?\s*$")


def _claims_fallback(raw: str):
    out = []
    for ln in raw.splitlines():
        m = _CLAIM_RE.match(ln.rstrip("\r"))
        if not m:
            continue
        cid, status, text, aline, snip, rlo, rhi, _ = m.groups()
        spec = 0.5
        out.append((cid, text.strip(), status, int(aline) if aline else None, snip,
                    int(rlo) if rlo else None, int(rhi) if rhi else None, spec,
                    round(TRUST.get(status, 0.0) * 0.5, 4), " ".join(mg.terms(f"{text} {snip or ''}"))))
    return out


def _claims_from_memo(md, raw: str):
    if md is None:
        return _claims_fallback(raw)
    _, claims, _ = md.parse_memo_text(raw)
    out = []
    for c in claims:
        kws = md.extract_keywords(c["text"], c["anchor_snip"])
        spec = md.specificity(c["text"], c["anchor_snip"])
        util = md.utility(c["status"], spec, 0.5, 0, 0, 0)   # corpus idf unknown here: neutral
        out.append((c["claim_id"], c["text"], c["status"], c["anchor_line"], c["anchor_snip"],
                    c["region_lo"], c["region_hi"], spec, util, " ".join(kws)))
    return out


# --------------------------------------------------------------------------- search

def search(query: str, project: str | None = None, limit: int = 8, unproven: bool = False,
           db: sqlite3.Connection | None = None, candidates: int = 300) -> list[dict]:
    """Ranked claims for a free-text query. REFUTED/STALE never come back; unproven
    claims only when asked for, and then flagged."""
    terms = [t for t in mg.terms(query, STOP)][:10]
    if not terms:
        return []
    own = db is None
    db = db or connect(readonly=True, timeout=1.0)
    try:
        tset = set(terms)
        found: dict[int, tuple] = {}
        # Precise first: every term must be there. If that is thin, any TWO terms together;
        # any single term only when no pair co-occurs at all. A single common term ("weight",
        # "dose") matched tens of thousands of claims, all of them scored by bm25 and nearly
        # all of them noise: the pair step is 4x faster and its answers cover more of the
        # question (measured 2026-10-03: mean coverage 0.60 -> 0.76 on a dose/regain query).
        exprs = [" AND ".join(f'"{t}"' for t in terms)]
        if len(terms) > 1:
            if len(terms) > 2:
                exprs.append(" OR ".join(f'("{a}" AND "{b}")'
                                         for a, b in itertools.combinations(terms, 2)))
            exprs.append(" OR ".join(f'"{t}"' for t in terms))
        for i, q in enumerate(exprs):
            if i == len(exprs) - 1 and i > 1 and found:
                break                      # some pair co-occurred: single terms add only noise
            for row in db.execute(
                    "SELECT c.id, c.text, c.status, c.utility, c.anchor_line, d.path, d.project,"
                    " c.keywords, bm25(claim_fts, 1.0, 0.5) AS b FROM claim_fts"
                    " JOIN claim c ON c.id = claim_fts.rowid JOIN doc d ON d.id = c.doc_id"
                    " WHERE claim_fts MATCH ? ORDER BY b LIMIT ?", (q, candidates)):
                found.setdefault(row[0], row)
            if len(found) >= limit * 3 or len(terms) == 1:
                break
        if not found:
            return []
        best = min(r[8] for r in found.values())          # bm25: more negative = better
        out, by_text = [], {}
        for cid, text, status, util, line, path, proj, kws, b in found.values():
            if status in BLOCKED or (status in UNPROVEN and not unproven):
                continue
            if project and proj != project:
                continue
            # A claim that is only an anchor ("@L8122 `Kockazat / kezeles`"), a numbered
            # heading ("7616: Kezeles") or two words says nothing a reader can use; it
            # matched because its one word did.
            body = re.sub(r"^\d+\s*[:.)-]?\s*", "", text.strip())
            if body.startswith("@L") or len(body) < 15 or len(body.split()) < 3:
                continue
            words = set(mg.terms(f"{text} {kws}", min_len=3))
            cov = len(tset & words) / len(tset)
            rel = (b / best) if best else 0.0
            score = (rel * max(0.25, min(1.0, cov * 1.5)) * TRUST.get(status, 0.3)
                     * (0.3 + 0.7 * (util or 0)))
            hit = {"id": cid, "text": text, "status": status, "path": path, "line": line,
                   "project": proj, "score": round(score, 4), "coverage": round(cov, 2),
                   "copies": 0}
            # Byte-identical copies of one paper (three repos holding the same PDF) give the
            # same claim three times; one is the answer, the rest are a count.
            key = mg.fold(body)
            prev = by_text.get(key)
            if prev is None:
                by_text[key] = hit
                out.append(hit)
            else:
                prev["copies"] += 1
                if hit["score"] > prev["score"]:
                    prev.update({k: hit[k] for k in ("id", "path", "line", "project", "score")})
        out.sort(key=lambda r: -r["score"])
        return out[:limit]
    finally:
        if own:
            db.close()


# --------------------------------------------------------------------------- stats / cli

def stats() -> dict:
    db = connect(readonly=True)
    try:
        s = {"db": str(db_path()), "mb": round(db_path().stat().st_size / 1e6, 1),
             "roots": [r[0] for r in db.execute("SELECT path FROM root")],
             "docs": db.execute("SELECT COUNT(*) FROM doc").fetchone()[0],
             "claims": db.execute("SELECT COUNT(*) FROM claim").fetchone()[0],
             "by_status": dict(db.execute("SELECT status, COUNT(*) FROM claim GROUP BY status")),
             "projects": db.execute("SELECT COUNT(DISTINCT project) FROM doc").fetchone()[0]}
        return s
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--root", action="append")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--search")
    ap.add_argument("--project")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--unproven", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    cfg = mg.load_config()
    if a.sync:
        roots = a.root or cfg.get("corpus_roots") or []
        if not roots:
            print("no corpus_roots configured (config.json) and no --root given")
            return 1
        for r in roots:
            res = sync_root(Path(r), full=a.full, cfg=cfg)
            print(json.dumps(res, ensure_ascii=False))
        return 0
    if a.search:
        t0 = time.time()
        hits = search(a.search, project=a.project, limit=a.limit, unproven=a.unproven)
        if a.json:
            print(json.dumps(hits, ensure_ascii=False, indent=2))
        else:
            print(f"# {len(hits)} claim(s) for: {a.search}   ({(time.time() - t0) * 1000:.0f} ms)")
            for h in hits:
                flag = "" if h["status"] in ("CONFIRMED", "DRIFTED") else f" [{h['status']}]"
                cp = f", +{h['copies']} masolat" if h["copies"] else ""
                print(f"- {h['text'][:200]}{flag}\n    {h['path']}:{h['line'] or '-'}   ({h['project']}, {h['score']}{cp})")
        return 0
    if a.stats:
        print(json.dumps(stats(), ensure_ascii=False, indent=2))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
