#!/usr/bin/env python3
"""Keep memo-guard's SQLite stores fast and sound: lightly after every write, thoroughly daily.

light   after each store/tables sync, on the sync's own connection. PRAGMA optimize
        (re-ANALYZEs only what changed), a small FTS5 'merge' so segments never pile up,
        a PASSIVE WAL checkpoint. Milliseconds; never blocks a reader.
heavy   once a day from `doctor.py --maintain` (SessionEnd, or SessionStart when due), in
        the background. Steps:
        - quick_check: a failure is reported, never "fixed" by deleting anything;
        - FTS5 integrity-check against the content table, and 'rebuild' when the index
          disagrees with it;
        - FTS5 'optimize' and ANALYZE;
        - VACUUM when free pages exceed 10% (or 50 MB);
        - a TRUNCATE checkpoint.

Only derived structures are ever rebuilt (search indexes, statistics). Rows are never
touched: repairing a store must not be a way of losing it.

  dbmaint.py --heavy [--db memo|data|memory|claims] [--json]
  dbmaint.py --light [--db ...]
  dbmaint.py --status
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mg_lib as mg  # noqa: E402

# name -> (file in data_dir(), FTS5 tables, whether each has external content to check against)
DBS = {
    "memo": ("memo.db", ["claim_fts"]),
    "data": ("data.db", ["rows_fts"]),
    "memory": ("memory.db", ["fact_fts"]),
    "claims": ("claims.db", []),
}
VACUUM_FREE_SHARE = 0.10
VACUUM_FREE_BYTES = 50 * 1024 * 1024


def _state_path() -> Path:
    return mg.data_dir() / "dbmaint.json"


def _load_state() -> dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(st: dict) -> None:
    try:
        _state_path().write_text(json.dumps(st, indent=1), encoding="utf-8")
    except OSError:
        pass


def _fts_present(db: sqlite3.Connection, names: list[str]) -> list[str]:
    have = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return [n for n in names if n in have]


def light_conn(db: sqlite3.Connection, fts: list[str]) -> None:
    """The per-sync step, on an open write connection. Swallows lock errors: the next
    sync, or the daily heavy pass, does the same work."""
    try:
        for f in _fts_present(db, fts):
            db.execute(f"INSERT INTO {f}({f}, rank) VALUES('merge', 64)")
        db.execute("PRAGMA optimize")
        db.commit()
        db.execute("PRAGMA wal_checkpoint(PASSIVE)")
    except sqlite3.Error:
        pass


def light(name: str) -> dict:
    fn, fts = DBS[name]
    p = mg.data_dir() / fn
    if not p.exists():
        return {"db": name, "skipped": "absent"}
    db = sqlite3.connect(p, timeout=5.0)
    try:
        t0 = time.time()
        light_conn(db, fts)
        return {"db": name, "seconds": round(time.time() - t0, 2)}
    finally:
        db.close()


def heavy(name: str, log=lambda *a: None) -> dict:
    fn, fts = DBS[name]
    p = mg.data_dir() / fn
    if not p.exists():
        return {"db": name, "skipped": "absent"}
    out = {"db": name, "mb_before": round(p.stat().st_size / 1e6, 1), "steps": []}
    t0 = time.time()
    db = sqlite3.connect(p, timeout=60.0)
    try:
        db.execute("PRAGMA busy_timeout=60000")
        qc = db.execute("PRAGMA quick_check").fetchone()[0]
        out["quick_check"] = qc
        if qc != "ok":
            # Page-level damage is not something to repair automatically: report it loudly
            # and stop here, so nothing below writes on top of a broken file.
            out["error"] = "quick_check failed - not touching this file; see doctor"
            return out
        for f in _fts_present(db, fts):
            try:
                db.execute(f"INSERT INTO {f}({f}, rank) VALUES('integrity-check', 1)")
                out["steps"].append(f"{f}: integrity ok")
            except sqlite3.DatabaseError as e:
                log(f"{name}/{f}: integrity-check failed ({e}); rebuilding")
                db.execute(f"INSERT INTO {f}({f}) VALUES('rebuild')")
                db.commit()
                out["steps"].append(f"{f}: REBUILT ({str(e)[:80]})")
            db.execute(f"INSERT INTO {f}({f}) VALUES('optimize')")
            db.commit()
        db.execute("ANALYZE")
        db.commit()
        out["steps"].append("analyze")
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        free = db.execute("PRAGMA freelist_count").fetchone()[0]
        psize = db.execute("PRAGMA page_size").fetchone()[0]
        if pages and (free / pages > VACUUM_FREE_SHARE or free * psize > VACUUM_FREE_BYTES):
            db.execute("VACUUM")
            out["steps"].append(f"vacuum ({free} free pages)")
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        db.close()
    out["mb_after"] = round(p.stat().st_size / 1e6, 1)
    out["seconds"] = round(time.time() - t0, 1)
    return out


def heavy_all(names=None, log=lambda *a: None) -> list[dict]:
    res = []
    for n in names or list(DBS):
        try:
            res.append(heavy(n, log))
        except sqlite3.Error as e:
            res.append({"db": n, "error": f"{type(e).__name__}: {e}"[:200]})
    st = _load_state()
    st["heavy"] = {"ts": time.time(), "results": res}
    _save_state(st)
    mg.append_metrics({"ts": time.time(), "dbs": res}, event="dbmaint")
    return res


def status() -> list[dict]:
    rows = []
    st = _load_state()
    for n, (fn, fts) in DBS.items():
        p = mg.data_dir() / fn
        if not p.exists():
            continue
        db = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=2.0)
        try:
            pages = db.execute("PRAGMA page_count").fetchone()[0]
            free = db.execute("PRAGMA freelist_count").fetchone()[0]
            stat1 = db.execute("SELECT count(*) FROM sqlite_master WHERE name='sqlite_stat1'").fetchone()[0]
            blocks = {f: db.execute(f"SELECT count(*) FROM {f}_data").fetchone()[0]
                      for f in _fts_present(db, fts)}
        finally:
            db.close()
        rows.append({"db": n, "mb": round(p.stat().st_size / 1e6, 1),
                     "free_pct": round(free * 100 / max(pages, 1), 1), "analyzed": bool(stat1),
                     "fts_blocks": blocks})
    last = st.get("heavy", {}).get("ts")
    if last:
        rows.append({"last_heavy_h": round((time.time() - last) / 3600, 1)})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--light", action="store_true")
    ap.add_argument("--heavy", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--db", choices=sorted(DBS), action="append")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.heavy:
        res = heavy_all(a.db, log=lambda m: print(m, file=sys.stderr))
    elif a.light:
        res = [light(n) for n in (a.db or list(DBS))]
    else:
        res = status()
    print(json.dumps(res, indent=1, ensure_ascii=False) if a.json or not a.status else
          "\n".join(json.dumps(r, ensure_ascii=False) for r in res))
    return 1 if any(r.get("error") for r in res) else 0


if __name__ == "__main__":
    sys.exit(main())
