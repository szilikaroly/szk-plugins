#!/usr/bin/env python3
"""Sync the knowledge base across machines through a private git repo.

Why not just commit the .db
---------------------------
SQLite is binary and does not merge. Two machines editing it does not produce a
conflict git can show you — it produces silent loss, because one side's file
simply replaces the other's. So the database is exported to deterministic JSON,
one file per project, and git merges *that*. It is the same strategy
science-monitor's repo.py uses, for the same reason: two machines working on
different projects never touch the same file, and a real conflict is readable.

The identifier problem, and why fingerprints
--------------------------------------------
`fact.id` is a local AUTOINCREMENT. Machine A's fact 5 and machine B's fact 5
are different facts. Anything exported by id — edges especially — would attach
itself to whatever happened to hold that number on the other machine, which is
worse than not syncing at all because it looks like it worked. Everything here
is keyed by a content fingerprint instead, and ids are resolved locally on
import.

Merge is union, never replace
-----------------------------
Import adds and updates; it never deletes a local fact because the remote lacks
it. Otherwise the older of two machines would quietly erase the newer one's work
on first sync. Deletion stays a deliberate local act (`memify --hard`).

  sync.py --setup <user>/<repo>   clone or create the private data repo
  sync.py --push                  export, commit, pull --rebase, push
  sync.py --pull                  fetch and merge into the local database
  sync.py --request               coalesced background sync (used by hooks)
  sync.py --status

Stdlib only. Requires git; the GitHub CLI only for --setup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg      # noqa: E402

DEBOUNCE_S = 8.0         # coalesce a burst of writes into one commit


def repo_dir() -> Path:
    return Path(os.environ.get("MEMO_GUARD_SYNC_DIR")
                or mg.data_dir() / "sync")


def _git(*args: str, check: bool = False, timeout: float = 90) -> tuple[int, str]:
    r = subprocess.run(["git", "-C", str(repo_dir()), *args],
                       capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.returncode, (r.stdout + r.stderr).strip()


def fp(text: str) -> str:
    """Portable key. Must match across machines, so it is content-only."""
    import re
    n = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    return hashlib.sha256(n.encode()).hexdigest()[:20]


# --------------------------------------------------------------------------- export

def export(db, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "facts").mkdir(exist_ok=True)
    written = {"projects": 0, "facts": 0, "edges": 0, "claims": 0, "blocks": 0}

    by_project: dict[str, list] = {}
    fp_of: dict[int, str] = {}
    for (fid, slug, text, kind, anchor, source, created, util) in db.execute(
            "SELECT f.id,p.slug,f.text,f.kind,f.anchor,f.source,f.created_at,f.utility"
            " FROM fact f JOIN project p ON p.id=f.project_id"):
        key = fp(text)
        fp_of[fid] = key
        by_project.setdefault(slug, []).append({
            "fp": key, "text": text, "kind": kind, "anchor": anchor or "",
            "source": source or "", "created_at": round(created or 0, 3),
            "utility": round(util or 0, 4)})

    for slug, items in by_project.items():
        items.sort(key=lambda d: d["fp"])          # deterministic: diffs stay minimal
        (out / "facts" / f"{slug}.json").write_text(
            json.dumps({"project": slug, "facts": items}, indent=1,
                       sort_keys=True, ensure_ascii=False) + "\n")
        written["projects"] += 1
        written["facts"] += len(items)

    edges = []
    for src, dst, rel, w in db.execute("SELECT src,dst,rel,weight FROM edge"):
        if src in fp_of and dst in fp_of:
            edges.append({"src": fp_of[src], "dst": fp_of[dst], "rel": rel,
                          "weight": round(w or 1.0, 3)})
    edges.sort(key=lambda d: (d["src"], d["dst"], d["rel"]))
    (out / "edges.json").write_text(
        json.dumps(edges, indent=1, sort_keys=True) + "\n")
    written["edges"] = len(edges)

    try:
        import claims as cl
        cdb = cl.connect()
        vs = [{"fp": r[0], "text": r[1], "status": r[2], "note": r[3] or "",
               "replacement": r[4] or ""}
              for r in cdb.execute(
                  "SELECT fp,text,status,note,replacement FROM verdict")]
        vs.sort(key=lambda d: d["fp"])
        (out / "claims.json").write_text(
            json.dumps(vs, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        written["claims"] = len(vs)
    except Exception:
        pass

    try:
        import blocks as bl
        bdb = bl.connect()
        bs = [{"label": r[0], "scope": r[1], "content": r[2], "char_limit": r[3],
               "updated_at": round(r[4] or 0, 3)}
              for r in bdb.execute(
                  "SELECT label,scope,content,char_limit,updated_at FROM block"
                  " WHERE TRIM(content)<>''")]
        bs.sort(key=lambda d: (d["scope"], d["label"]))
        (out / "blocks.json").write_text(
            json.dumps(bs, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        written["blocks"] = len(bs)
    except Exception:
        pass

    # Tombstones travel with the data. A deletion that stays on one machine is
    # not a deletion — the next pull from any other machine undoes it.
    try:
        ts = [{"fp": r[0], "deleted_at": round(r[1] or 0, 3)}
              for r in db.execute("SELECT fp,deleted_at FROM tombstone")]
        ts.sort(key=lambda d: d["fp"])
        (out / "tombstones.json").write_text(
            json.dumps(ts, indent=1, sort_keys=True) + "\n")
        written["tombstones"] = len(ts)
    except Exception:
        pass

    (out / "sync-meta.json").write_text(json.dumps(
        {"schema": 1, "machine": os.uname().nodename, "written": written},
        indent=1, sort_keys=True) + "\n")
    return written


# --------------------------------------------------------------------------- import

def import_(db, src: Path) -> dict:
    """Union merge. Adds and updates; never deletes what is only local."""
    import memory as mem
    added = {"facts": 0, "edges": 0, "claims": 0, "blocks": 0}
    if not src.exists():
        return added

    # Tombstones are applied FIRST, and are also honoured when adding below.
    # Otherwise the import re-creates exactly what another machine deleted, and
    # a curated knowledge base can never actually shrink.
    # Local tombstones count too. push() runs pull -> import -> export, so on the
    # very first sync after a deletion the remote has no tombstone file yet and
    # the import cheerfully restored exactly what was just deleted.
    dead: set[str] = {r[0] for r in db.execute("SELECT fp FROM tombstone")}
    tf = src / "tombstones.json"
    if tf.exists():
        try:
            for t in json.loads(tf.read_text()):
                dead.add(t["fp"])
                db.execute("INSERT INTO tombstone (fp,deleted_at,machine)"
                           " VALUES (?,?,'remote') ON CONFLICT(fp) DO NOTHING",
                           (t["fp"], t.get("deleted_at", time.time())))
        except Exception:
            pass
    for fid, text in list(db.execute("SELECT id,text FROM fact")):
        if fp(text) in dead:
            db.execute("DELETE FROM fact_fts WHERE rowid=?", (fid,))
            db.execute("DELETE FROM fact WHERE id=?", (fid,))
            added["deleted"] = added.get("deleted", 0) + 1
    db.commit()

    local_fp: dict[str, int] = {}
    for fid, text in db.execute("SELECT id,text FROM fact"):
        local_fp[fp(text)] = fid

    for f in sorted((src / "facts").glob("*.json")) if (src / "facts").exists() else []:
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        slug = data.get("project") or f.stem
        for item in data.get("facts", []):
            if item["fp"] in local_fp or item["fp"] in dead:
                continue
            cwd = f"/{slug.replace('-', '/')}"        # slug is path-derived
            try:
                r = mem.promote(db, item["text"], cwd, item.get("kind", "finding"),
                                source=item.get("source", ""),
                                anchor=item.get("anchor", ""),
                                utility=item.get("utility", 0.0), by="sync")
                local_fp[item["fp"]] = r["id"]
                added["facts"] += 1
            except Exception:
                continue

    ef = src / "edges.json"
    if ef.exists():
        try:
            for e in json.loads(ef.read_text()):
                a, b = local_fp.get(e["src"]), local_fp.get(e["dst"])
                if not a or not b:
                    continue        # an edge to a fact we do not have is not an edge
                db.execute("INSERT INTO edge (src,dst,rel,weight,created_at)"
                           " VALUES (?,?,?,?,?) ON CONFLICT(src,dst,rel)"
                           " DO UPDATE SET weight=MAX(weight,excluded.weight)",
                           (a, b, e["rel"], e.get("weight", 1.0), time.time()))
                added["edges"] += 1
        except Exception:
            pass
        db.commit()

    cf = src / "claims.json"
    if cf.exists():
        try:
            import claims as cl
            cdb = cl.connect()
            for v in json.loads(cf.read_text()):
                cl.record(cdb, v["text"], v["status"], v.get("note", ""),
                          v.get("replacement", ""))
                added["claims"] += 1
        except Exception:
            pass

    bf = src / "blocks.json"
    if bf.exists():
        try:
            import blocks as bl
            bdb = bl.connect()
            for b in json.loads(bf.read_text()):
                row = bdb.execute("SELECT content,updated_at FROM block"
                                  " WHERE label=? AND scope=?",
                                  (b["label"], b["scope"])).fetchone()
                # Last writer wins per block, and only when the remote is newer.
                # Blocks are small and hand-edited; merging their text would
                # produce something neither machine wrote.
                if not row or (b.get("updated_at", 0) > (row[1] or 0)):
                    bdb.execute(
                        "INSERT INTO block (label,scope,content,char_limit,"
                        "created_at,updated_at) VALUES (?,?,?,?,?,?)"
                        " ON CONFLICT(label,scope) DO UPDATE SET"
                        " content=excluded.content, updated_at=excluded.updated_at",
                        (b["label"], b["scope"], b["content"],
                         b.get("char_limit", 1200), time.time(),
                         b.get("updated_at", time.time())))
                    added["blocks"] += 1
            bdb.commit()
        except Exception:
            pass
    return added


# --------------------------------------------------------------------------- git

def setup(slug: str) -> int:
    d = repo_dir()
    if (d / ".git").exists():
        print(f"already set up: {d}")
        return 0
    d.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["gh", "repo", "clone", slug, str(d)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        c = subprocess.run(["gh", "repo", "create", slug, "--private",
                            "--description",
                            "memo-guard knowledge base (private data, not code)"],
                           capture_output=True, text=True)
        if c.returncode != 0 and "already exists" not in (c.stderr or ""):
            print(f"could not create {slug}: {c.stderr.strip()[:200]}", file=sys.stderr)
            return 1
        subprocess.run(["gh", "repo", "clone", slug, str(d)],
                       capture_output=True, text=True)
    if not (d / ".git").exists():
        _git("init", "-q", "-b", "main")
    # The data repo must never accept the raw databases, only the JSON.
    (d / ".gitignore").write_text("*.db\n*.db-wal\n*.db-shm\n*.jsonl*\n")
    (d / "README.md").write_text(
        "# memo-guard knowledge base\n\n"
        "Exported facts, claim verdicts and core-memory blocks. **Private on "
        "purpose** — this contains material from every project the plugin has "
        "seen. The plugin's code lives elsewhere; nothing here is code.\n\n"
        "One JSON file per project so two machines editing different projects "
        "never touch the same file. Everything is keyed by content fingerprint, "
        "not by local row id.\n")
    _git("add", "-A")
    _git("commit", "-q", "-m", "init knowledge base")
    print(f"ready: {d}  ->  {slug}")
    return 0


def push(db) -> dict:
    d = repo_dir()
    if not (d / ".git").exists():
        return {"error": "not set up — run sync.py --setup <user>/<repo>"}
    # The ordering below is what makes concurrent edits merge instead of
    # conflict: pull first, import into the database, then regenerate the JSON
    # from the merged state. The file git ends up committing is the union, so
    # there is nothing left to disagree about.
    # A brand-new remote has no refs/heads/main yet, and pulling from it fails
    # with "no such ref was fetched". Treated as an error that meant the very
    # first push could never happen — the guard below refused to proceed, so
    # setup deadlocked permanently. Ask whether there is anything to pull first.
    rc_ls, remote_head = _git("ls-remote", "--heads", "origin", "main")
    rc, out = (0, "") if (rc_ls == 0 and not remote_head.strip()) \
        else _git("pull", "--rebase", "-q")
    if rc != 0:
        # Never commit on top of a half-finished rebase — that turns a
        # recoverable git state into a corrupted export.
        _git("rebase", "--abort")
        return {"pushed": False, "error": f"pull --rebase failed: {out[:200]}",
                "hint": "resolve in " + str(d)}
    pulled = import_(db, d)
    written = export(db, d)
    _git("add", "-A")
    rc, _ = _git("diff", "--cached", "--quiet")
    if rc == 0:
        return {"pushed": False, "reason": "nothing changed",
                "pulled": pulled, "exported": written}
    _git("commit", "-q", "-m",
         f"knowledge base: {written['facts']} facts, {written['edges']} edges "
         f"({os.uname().nodename})")
    rc, out = _git("push", "-q", "origin", "HEAD:main")
    return {"pushed": rc == 0, "git": out[:200] if rc else "",
            "pulled": pulled, "exported": written}


def pull(db) -> dict:
    d = repo_dir()
    if not (d / ".git").exists():
        return {"error": "not set up"}
    _git("pull", "--rebase", "-q")
    return {"imported": import_(db, d)}


# --------------------------------------------------------------------------- debounce

def request() -> int:
    """Mark dirty and make sure exactly one worker is pending.

    Called after every write. A burst of ten promotes must become one commit,
    not ten, and must never block the caller — so this returns immediately and
    a detached worker does the git work after the coalescing window.
    """
    d = mg.data_dir()
    (d / "sync.dirty").write_text(str(time.time()))
    marker = d / "sync.worker"
    if marker.exists() and time.time() - marker.stat().st_mtime < DEBOUNCE_S * 4:
        return 0                      # a worker is already pending
    marker.write_text(str(time.time()))
    subprocess.Popen([sys.executable, str(Path(__file__)), "--worker"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return 0


def worker() -> int:
    d = mg.data_dir()
    time.sleep(DEBOUNCE_S)
    try:
        (d / "sync.dirty").unlink()
    except OSError:
        pass
    try:
        import memory as mem
        push(mem.connect())
    except Exception:
        pass
    try:
        (d / "sync.worker").unlink()
    except OSError:
        pass
    return 0


# --------------------------------------------------------------------------- cli

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--setup", metavar="USER/REPO")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--request", action="store_true")
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--export-only", metavar="DIR")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.setup:
        return setup(args.setup)
    if args.request:
        return request()
    if args.worker:
        return worker()

    import memory as mem
    db = mem.connect()

    if args.export_only:
        w = export(db, Path(args.export_only))
        print(json.dumps(w, indent=2) if args.json else
              f"exported {w['facts']} facts in {w['projects']} project file(s), "
              f"{w['edges']} edges, {w['claims']} claims, {w['blocks']} blocks")
        return 0
    if args.push:
        r = push(db)
        print(json.dumps(r, indent=2)); return 0 if not r.get("error") else 1
    if args.pull:
        r = pull(db)
        print(json.dumps(r, indent=2)); return 0 if not r.get("error") else 1

    d = repo_dir()
    ok = (d / ".git").exists()
    print(f"repo    : {d}  {'(ready)' if ok else '(NOT set up)'}")
    if ok:
        _, rem = _git("remote", "get-url", "origin")
        _, last = _git("log", "-1", "--format=%h %ad %s", "--date=short")
        print(f"remote  : {rem}")
        print(f"last    : {last}")
    print(f"pending : {'yes' if (mg.data_dir() / 'sync.dirty').exists() else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
