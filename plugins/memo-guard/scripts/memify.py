#!/usr/bin/env python3
"""memify — refine the graph after cognify built it.

Cognee's memify stage prunes outdated nodes, reweights frequently accessed
connections, and derives new facts from interaction patterns. cognify decides
what the graph IS; memify decides what it is still WORTH.

Three passes, and one deliberate difference from the obvious reading:

  prune      drop what has stopped earning its place — facts superseded or
             refuted elsewhere, entities nothing mentions any more, edges whose
             endpoints are gone.
  reweight   strengthen edges between facts that keep being retrieved together.
             NOT facts by hit count. That distinction is the whole design: an
             earlier version scored facts by `hits`, which made a fact that had
             been returned once more likely to be returned again, until one
             fact won every query regardless of what was asked. Co-retrieval
             between a PAIR is different evidence — it says these two belong to
             the same question — and it only affects graph expansion, never the
             relevance ranking that decides what surfaces first.
  derive     add what follows from what is already known: transitive supersedes,
             and contradiction edges where a refuted claim shares its subject
             with a live one.

Everything here is idempotent and reversible except --prune --hard.

  memify.py --run                 all three passes, nothing deleted
  memify.py --run --hard          same, but actually delete pruned facts
  memify.py --stats               what memify would change
  memify.py --explain <fact-id>   why this fact is or is not a prune candidate

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import memory as mem      # noqa: E402
import cognify as cog     # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS coaccess (
  a     INTEGER NOT NULL,
  b     INTEGER NOT NULL,
  n     INTEGER DEFAULT 0,
  last  REAL,
  PRIMARY KEY (a, b)
);
"""

STALE_DAYS = 180          # never retrieved in this long, and not pinned
MIN_COACCESS = 2          # pairs seen together fewer times than this are noise


def connect() -> sqlite3.Connection:
    db = cog.connect()
    db.executescript(SCHEMA)
    return db


def record_coaccess(db: sqlite3.Connection, fact_ids: list[int]) -> None:
    """Called by recall() with the set it returned. Pairs, not singletons."""
    now = time.time()
    ids = sorted(set(fact_ids))
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            db.execute("INSERT INTO coaccess (a,b,n,last) VALUES (?,?,1,?)"
                       " ON CONFLICT(a,b) DO UPDATE SET n=n+1, last=excluded.last",
                       (a, b, now))
    db.commit()


# --------------------------------------------------------------------------- prune

def prune_candidates(db: sqlite3.Connection) -> list[dict]:
    """Facts that have stopped earning their place, with the reason for each."""
    now = time.time()
    out = []
    for fid, text, created, hits, last_hit in db.execute(
            "SELECT id,text,created_at,hits,last_hit FROM fact"):
        age_d = (now - (created or now)) / 86400
        idle_d = (now - (last_hit or created or now)) / 86400
        reason = None
        if hits == 0 and age_d > STALE_DAYS:
            reason = f"never retrieved in {age_d:.0f} days"
        else:
            try:
                import claims as cl
                v = cl.match(cl.connect(), text)
                if v and v["status"] == "REFUTED":
                    reason = "refuted by the claim store"
                elif v and v["status"] == "SUPERSEDED":
                    reason = "superseded by the claim store"
            except Exception:
                pass
        if reason:
            out.append({"id": fid, "text": text[:70], "reason": reason,
                        "idle_days": round(idle_d)})
    return out


def prune(db: sqlite3.Connection, hard: bool = False) -> dict:
    cands = prune_candidates(db)
    removed = 0
    if hard:
        for c in cands:
            db.execute("DELETE FROM fact_vec WHERE fact_id=?", (c["id"],))
            db.execute("DELETE FROM fact_entity WHERE fact_id=?", (c["id"],))
            db.execute("DELETE FROM edge WHERE src=? OR dst=?", (c["id"], c["id"]))
            db.execute("DELETE FROM coaccess WHERE a=? OR b=?", (c["id"], c["id"]))
            mem.fts_delete(db, c["id"])
            db.execute("DELETE FROM fact WHERE id=?", (c["id"],))
            removed += 1
    # Dangling structure goes regardless: an edge to a fact that no longer
    # exists is not a link, it is a lie the graph tells during expansion.
    orphan_edges = db.execute(
        "DELETE FROM edge WHERE src NOT IN (SELECT id FROM fact)"
        "    OR dst NOT IN (SELECT id FROM fact)").rowcount
    orphan_fe = db.execute(
        "DELETE FROM fact_entity WHERE fact_id NOT IN (SELECT id FROM fact)").rowcount
    db.commit()
    cog.refresh_mentions(db)      # also drops entities nothing mentions
    return {"candidates": len(cands), "deleted": removed,
            "orphan_edges": orphan_edges, "orphan_entity_links": orphan_fe,
            "detail": cands[:10]}


# --------------------------------------------------------------------------- reweight

def reweight(db: sqlite3.Connection) -> dict:
    """Strengthen edges between facts repeatedly retrieved together.

    Only pairs seen together at least MIN_COACCESS times count; a single joint
    appearance is as likely to be coincidence as signal. Weight is capped so a
    heavily-used pair cannot dominate expansion outright.
    """
    changed = created = 0
    for a, b, n in db.execute(
            "SELECT a,b,n FROM coaccess WHERE n>=?", (MIN_COACCESS,)):
        bonus = min(0.4, 0.05 * n)
        row = db.execute("SELECT weight FROM edge WHERE src=? AND dst=?"
                         " AND rel='relates_to'", (a, b)).fetchone()
        if row:
            db.execute("UPDATE edge SET weight=? WHERE src=? AND dst=?"
                       " AND rel='relates_to'",
                       (min(1.5, row[0] + bonus), a, b))
            changed += 1
        else:
            db.execute("INSERT INTO edge (src,dst,rel,weight,created_at)"
                       " VALUES (?,?, 'relates_to', ?, ?)"
                       " ON CONFLICT(src,dst,rel) DO NOTHING",
                       (a, b, 0.4 + bonus, time.time()))
            created += 1
    db.commit()
    return {"strengthened": changed, "created_from_coaccess": created}


# --------------------------------------------------------------------------- derive

def derive(db: sqlite3.Connection) -> dict:
    """New edges that follow from existing ones."""
    trans = contra = 0

    # If A supersedes B and B supersedes C, then A supersedes C. Without this,
    # recalling C surfaces B — itself already outdated — and stops there.
    for a, b in db.execute("SELECT src,dst FROM edge WHERE rel='supersedes'"):
        for _, c in db.execute(
                "SELECT src,dst FROM edge WHERE rel='supersedes' AND src=?", (b,)):
            if c == a:
                continue
            cur = db.execute("SELECT 1 FROM edge WHERE src=? AND dst=?"
                             " AND rel='supersedes'", (a, c)).fetchone()
            if not cur:
                db.execute("INSERT INTO edge (src,dst,rel,weight,created_at)"
                           " VALUES (?,?, 'supersedes', 0.8, ?)"
                           " ON CONFLICT(src,dst,rel) DO NOTHING", (a, c, time.time()))
                trans += 1

    # A refuted fact and a live one that share an entity are about the same
    # thing and disagree. Marking that is what stops the live one from being
    # recalled as if nothing had ever been questioned about it.
    try:
        import claims as cl
        cdb = cl.connect()
        refuted = [fid for fid, text in db.execute("SELECT id,text FROM fact")
                   if (lambda v: v and v["status"] == "REFUTED")(cl.match(cdb, text))]
    except Exception:
        refuted = []
    for fid in refuted:
        for other, in db.execute(
                "SELECT DISTINCT fe2.fact_id FROM fact_entity fe1"
                " JOIN fact_entity fe2 ON fe1.entity_id=fe2.entity_id"
                " WHERE fe1.fact_id=? AND fe2.fact_id<>?", (fid, fid)):
            if other in refuted:
                continue
            db.execute("INSERT INTO edge (src,dst,rel,weight,created_at)"
                       " VALUES (?,?, 'contradicts', 0.9, ?)"
                       " ON CONFLICT(src,dst,rel) DO NOTHING",
                       (fid, other, time.time()))
            contra += 1
    db.commit()
    return {"transitive_supersedes": trans, "contradiction_edges": contra}


# --------------------------------------------------------------------------- cli

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--hard", action="store_true",
                    help="actually delete pruned facts (default: report only)")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--explain", metavar="FACT_ID")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = connect()

    if args.explain:
        row = db.execute("SELECT text,hits,created_at,last_hit FROM fact WHERE id=?",
                         (args.explain,)).fetchone()
        if not row:
            print("no such fact"); return 1
        cands = {c["id"]: c for c in prune_candidates(db)}
        c = cands.get(int(args.explain))
        print(f"  text   : {row[0][:70]}")
        print(f"  hits   : {row[1]}")
        print(f"  prune  : {'YES — ' + c['reason'] if c else 'no'}")
        nb = list(db.execute("SELECT rel,COUNT(*) FROM edge WHERE src=? OR dst=?"
                             " GROUP BY rel", (args.explain, args.explain)))
        print(f"  edges  : " + (", ".join(f"{r}×{n}" for r, n in nb) or "none"))
        return 0

    if args.stats:
        d = {
            "facts": db.execute("SELECT COUNT(*) FROM fact").fetchone()[0],
            "edges": db.execute("SELECT COUNT(*) FROM edge").fetchone()[0],
            "entities": db.execute("SELECT COUNT(*) FROM entity").fetchone()[0],
            "coaccess_pairs": db.execute("SELECT COUNT(*) FROM coaccess").fetchone()[0],
            "prune_candidates": len(prune_candidates(db)),
        }
        print(json.dumps(d, indent=2) if args.json else
              "\n".join(f"  {k:<18} {v}" for k, v in d.items()))
        return 0

    if args.run:
        r = {"prune": prune(db, hard=args.hard),
             "reweight": reweight(db), "derive": derive(db)}
        if args.json:
            print(json.dumps(r, indent=2)); return 0
        p = r["prune"]
        print(f"prune    : {p['candidates']} candidate(s), {p['deleted']} deleted, "
              f"{p['orphan_edges']} orphan edge(s) removed"
              + ("" if args.hard else "   (use --hard to delete)"))
        for c in p["detail"]:
            print(f"           [{c['id']}] {c['reason']}: {c['text']}")
        print(f"reweight : {r['reweight']['strengthened']} strengthened, "
              f"{r['reweight']['created_from_coaccess']} new from co-access")
        print(f"derive   : {r['derive']['transitive_supersedes']} transitive, "
              f"{r['derive']['contradiction_edges']} contradiction edge(s)")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
