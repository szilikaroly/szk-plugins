#!/usr/bin/env python3
"""Realtime ingestion: what changes in the corpus roots becomes memos, claims and tables.

Two ways in, one worker:
  - PostToolUse (ctx_monitor.py): a Write/Edit/MultiEdit/NotebookEdit on a file inside a
    corpus root appends ONE line to ingest/queue.jsonl and makes sure a worker exists.
    Nothing else happens in the hook - the 34 ms hook budget is the rule (PLAN A4).
  - SessionStart (inject_resume.py): at most every `ingest_scan_every_min` a background
    scan compares the roots with the last known (mtime, size) of every file and queues
    what changed outside Claude (a downloaded PDF, an edit in Word). The FIRST scan of a
    root only records the state: the batch runs already indexed it, and queueing 21k files
    on a session start would be the GPU job nobody asked for.

The worker (single-flight, detached) drains the queue:
  - tables (.csv/.tsv/.xlsx) -> tables.import_file: SQL, exact, no model;
  - documents -> a memo with memo-index's memo_gen on the local GPU, staged exactly like
    the batch runs (same staged names, same 120-char wrapping for tagged/long-line text),
    so a refreshed memo replaces the old one instead of duplicating it; then the anchors
    are verified while the staged text still exists, the staged->original mapping is
    appended to <root>/.memo/_source_map.tsv, and store.sync_root picks the memo up.
  - paused (ingest/paused, `/memo-guard:ingest pause`) or ingest_model=false: documents
    stay queued and the GPU is not touched; tables are still imported (CPU only).

  ingest.py --status | --pause | --resume | --scan | --now | --enqueue PATH | --worker
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mg_lib as mg  # noqa: E402

TEXT_EXT = {".md", ".txt", ".tex", ".py", ".html", ".htm", ".xml", ".csv", ".tsv"}
DOC_EXT = {".pdf", ".docx", ".pptx", ".xlsx"}
TABLE_EXT = {".csv", ".tsv", ".xlsx"}
INDEXABLE = TEXT_EXT | DOC_EXT
TAGGED = {".xml", ".html", ".htm"}
ALWAYS_PREP = TAGGED | {".csv", ".tsv"}
LONG = 300
# An installed R library is R's site-packages: third-party vignettes, help pages and test
# data. 2026-10-04: a project's rlib/ (17 CRAN packages) gave 111 indexed files, and the 8B
# model read lme4's test data as "CPU load increased by 7.93 in h264ref".
# A memo-index staging copy (<name>_pdf-<8 hex>.txt, older <name>_xml.txt) in a staging*/ folder
# is the original document's text a second time. 2026-10-04: 1,698 of them in one project, each
# beside an original with its own memo -- every claim, and every fabrication, twice.
SKIP = re.compile(r"(/\.git/|/node_modules/|/__pycache__/|/\.venv/|/venv/|/site-packages/|"
                  r"/rlib/|/renv/library/|/site-library/|/win-library/|"
                  r"/staging[^/]*/(?:[^/]+/)*[^/]+_(?:pdf|docx?|pptx?|xlsx?|xml|html?|odt|rtf)"
                  r"(?:-[0-9a-f]{8})?\.txt$|"
                  r"/\.cache/|/\.memo/|/_stage[^/]*/|\.memo\.md$)", re.I)
TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
HEARTBEAT_S = 120


def qdir() -> Path:
    d = mg.data_dir() / "ingest"
    d.mkdir(parents=True, exist_ok=True)
    return d


def roots(cfg: dict) -> list[Path]:
    return [Path(os.path.expanduser(str(r))).resolve() for r in (cfg.get("corpus_roots") or [])]


def root_of(path: Path, cfg: dict):
    for r in roots(cfg):
        try:
            rel = path.relative_to(r)
            return r, rel.as_posix()
        except ValueError:
            continue
    return None


def indexable(rel: str) -> bool:
    return (os.path.splitext(rel)[1].lower() in INDEXABLE
            and not SKIP.search("/" + rel.replace("\\", "/")))


# --------------------------------------------------------------------------- hook side

def enqueue(path: Path, reason: str, cfg: dict) -> bool:
    hit = root_of(path, cfg)
    if not hit or not indexable(hit[1]):
        return False
    with open(qdir() / "queue.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"root": str(hit[0]), "rel": hit[1], "reason": reason,
                            "t": time.time()}, ensure_ascii=False) + "\n")
    return True


def enqueue_from_hook(data: dict, cfg: dict) -> None:
    """PostToolUse: one append, maybe one detached spawn. Never prints, never raises."""
    if not cfg.get("ingest", True) or not cfg.get("corpus_roots"):
        return
    if data.get("tool_name") not in TOOLS:
        return
    ti = data.get("tool_input") or {}
    p = ti.get("file_path") or ti.get("notebook_path")
    if not p:
        return
    try:
        path = Path(p).resolve()
        if enqueue(path, "tool:" + data.get("tool_name", ""), cfg):
            ensure_worker()
    except Exception:
        pass


def _alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259                                     # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def worker_alive() -> bool:
    try:
        w = json.loads((qdir() / "worker.json").read_text(encoding="utf-8"))
        return _alive(int(w["pid"])) and time.time() - float(w["hb"]) < HEARTBEAT_S
    except Exception:
        return False


def ensure_worker() -> None:
    if not worker_alive():
        mg.spawn_background(Path(__file__), ["--worker"])


def maybe_scan(cfg: dict) -> None:
    """SessionStart: spawn a scan when the last one is older than the configured interval."""
    if not cfg.get("ingest", True) or not cfg.get("corpus_roots"):
        return
    stamp = qdir() / "scan.json"
    try:
        last = json.loads(stamp.read_text(encoding="utf-8")).get("t", 0)
    except Exception:
        last = 0
    if time.time() - last >= 60 * float(cfg.get("ingest_scan_every_min", 30)):
        stamp.write_text(json.dumps({"t": time.time(), "state": "spawned"}), encoding="utf-8")
        mg.spawn_background(Path(__file__), ["--scan"])


# --------------------------------------------------------------------------- file state

def state_db() -> sqlite3.Connection:
    db = sqlite3.connect(qdir() / "state.db", timeout=5.0)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
CREATE TABLE IF NOT EXISTS filestate (root TEXT, rel TEXT, mtime REAL, size INTEGER,
  done_at REAL, outcome TEXT, PRIMARY KEY (root, rel));
CREATE TABLE IF NOT EXISTS log (t REAL, root TEXT, rel TEXT, outcome TEXT, detail TEXT);
""")
    return db


def scan(cfg: dict, log=print) -> dict:
    db = state_db()
    out = {}
    for root in roots(cfg):
        known = {r[0]: (r[1], r[2]) for r in db.execute(
            "SELECT rel, mtime, size FROM filestate WHERE root=?", (str(root),))}
        bootstrap = not known
        queued = seen = 0
        rows = []
        for dp, dn, fn in os.walk(root):
            dpp = "/" + Path(dp).relative_to(root).as_posix() + "/"
            dn[:] = [d for d in dn if not SKIP.search(dpp + d + "/")]
            for f in fn:
                p = Path(dp) / f
                rel = p.relative_to(root).as_posix()
                if not indexable(rel):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size < 200:
                    continue
                seen += 1
                if bootstrap:
                    rows.append((str(root), rel, st.st_mtime, st.st_size, time.time(), "bootstrap"))
                elif known.get(rel) != (st.st_mtime, st.st_size):
                    enqueue(p, "scan", cfg)
                    queued += 1
        if rows:
            db.executemany("INSERT OR REPLACE INTO filestate VALUES (?,?,?,?,?,?)", rows)
            db.commit()
        out[str(root)] = {"files": seen, "queued": queued, "bootstrap": bootstrap}
    (qdir() / "scan.json").write_text(json.dumps({"t": time.time(), "state": "done", "roots": out}), encoding="utf-8")
    if any(v["queued"] for v in out.values()):
        ensure_worker()
    mg.append_metrics({"ts": time.time(), "roots": out}, event="ingest_scan")
    return out


# --------------------------------------------------------------------------- processing

def staged_stem(ab: str) -> str:
    """Same name doc_ingest and the batch runs give a staged file."""
    return f"{os.path.basename(ab).replace('.', '_')}-{hashlib.sha1(ab.encode()).hexdigest()[:8]}"


def prep_text(src: str, dst: str) -> int:
    """Same staging as recover_gap/prep_stage: tags stripped for XML/HTML, 120-char wrap."""
    raw = open(src, "rb").read().decode("utf-8", errors="replace")
    tagged = src.lower().endswith((".xml", ".html", ".htm"))
    if tagged:
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"&[a-z]+;", " ", raw)
    lines = []
    for ln in raw.splitlines():
        ln = re.sub(r"[ \t]+", " ", ln).rstrip() if tagged else ln.rstrip()
        if len(ln) > 120:
            lines.extend(textwrap.wrap(ln, 120, break_long_words=False, break_on_hyphens=False) or [ln])
        elif ln.strip() or not (lines and not lines[-1].strip()):
            lines.append(ln)
    text = "\n".join(lines)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(text)
    return len(text.strip())


def _max_line(p: str) -> int:
    with open(p, "rb") as f:
        return max((len(l) for l in f), default=0)


def ollama_up(timeout: float = 2.0) -> bool:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    try:
        with urllib.request.urlopen(f"{host}/api/version", timeout=timeout):
            return True
    except Exception:
        return False


def ensure_ollama(cfg: dict) -> bool:
    if ollama_up():
        return True
    exe = shutil.which("ollama")
    if not exe or not cfg.get("ingest_start_ollama", True):
        return False
    env = dict(os.environ, OLLAMA_KV_CACHE_TYPE="q8_0", OLLAMA_FLASH_ATTENTION="1",
               OLLAMA_NUM_PARALLEL=str(cfg.get("ingest_ollama_parallel", 4)))
    log = open(qdir() / "ollama_serve.log", "a", encoding="utf-8")
    subprocess.Popen([exe, "serve"], stdout=log, stderr=log, env=env, **mg.detached_kwargs())
    for _ in range(20):
        time.sleep(1)
        if ollama_up():
            return True
    return False


def _verify(memo_dir: Path, memo_names: list[str], root_for_sources: Path, ms: Path) -> None:
    """verify_anchors on just these memos, while their sources (or staged text) exist."""
    if not memo_names:
        return
    tmp = Path(tempfile.mkdtemp(prefix="mgv_"))
    try:
        for n in memo_names:
            if (memo_dir / n).exists():
                shutil.copy2(memo_dir / n, tmp / n)
        subprocess.run([sys.executable, str(ms / "verify_anchors.py"), "--memo-dir", str(tmp),
                        "--root", str(root_for_sources)], capture_output=True, timeout=600)
        for n in memo_names:
            if (tmp / n).exists():
                shutil.copy2(tmp / n, memo_dir / n)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def memo_name(rel_posix: str) -> str:
    return f"{rel_posix.replace('/', '__')[:100]}-{hashlib.sha1(rel_posix.encode('utf-8')).hexdigest()[:8]}.memo.md"


def process_doc(root: Path, rel: str, cfg: dict) -> tuple[str, str]:
    ms = Path(os.path.expanduser(cfg.get("memo_index_path", ""))) / "scripts"
    memo_dir = root / ".memo"
    memo_dir.mkdir(exist_ok=True)
    ab = str((root / rel).resolve())
    ext = os.path.splitext(rel)[1].lower()
    env = dict(os.environ, PYTHONUTF8="1",
               MEMO_MODEL_PROSE=cfg.get("ingest_prose_model", "qwen3:14b"),
               MEMO_MODEL_BIG=cfg.get("ingest_vision_model", "qwen3-vl:4b"))
    stage = Path(tempfile.mkdtemp(prefix="mgi_"))
    try:
        native = ext in TEXT_EXT and ext not in ALWAYS_PREP and _max_line(ab) <= LONG
        if native:
            # The file was already chosen (inside a root, indexable, not under SKIP); memo_gen's
            # generic "build/*", "dist/*", "vendor/*" excludes would silently drop real source
            # such as a project's build-chain scripts. Older memo-index lacks the flag: retry.
            cmd = [sys.executable, str(ms / "memo_gen.py"), "--root", str(root),
                   "--include", rel, "--memo-dir", str(memo_dir)]
            r = subprocess.run(cmd + ["--no-default-excludes"], capture_output=True, text=True,
                               encoding="utf-8", env=env, timeout=3600)
            if r.returncode != 0 and "unrecognized arguments" in (r.stderr or ""):
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                   env=env, timeout=3600)
            name = memo_name(rel)
            _verify(memo_dir, [name], root, ms)
            return ("memo" if (memo_dir / name).exists() else "no-claims"), r.stderr[-200:]
        name = staged_stem(ab) + ".txt"
        if ext in TEXT_EXT:
            if prep_text(ab, str(stage / name)) < 32:
                return "empty", "under 32 chars of text"
        else:
            r = subprocess.run([sys.executable, str(ms / "doc_ingest.py"), "--outdir", str(stage),
                                "--no-images", ab], capture_output=True, text=True,
                               encoding="utf-8", env=env, timeout=1800)
            try:
                rec = json.loads(r.stdout)[0]
            except Exception:
                return "convert-error", r.stderr[-200:]
            if "error" in rec:
                return "convert-error", str(rec["error"])[:200]
        lim = int(cfg.get("table_card_min_chunks", 100) or 0)
        bib = bool(cfg.get("table_card_bibliographic", True))
        if (lim or bib) and ext in (".csv", ".tsv", ".xlsx") and (stage / name).exists():
            import table_card
            slines = (stage / name).read_bytes().decode("utf-8", errors="replace").splitlines()
            why = table_card.card_reason(ab, lim, bib, slines)
            if why:
                done = table_card.write_cards(root, memo_dir, [rel], ms=ms, log=lambda *a: None)
                return ("table-card" if done else "convert-error"), why
        r = subprocess.run([sys.executable, str(ms / "memo_gen.py"), "--root", str(stage),
                            "--include", "*.txt", "--memo-dir", str(memo_dir)],
                           capture_output=True, text=True, encoding="utf-8", env=env, timeout=3600)
        mname = memo_name(name)
        _verify(memo_dir, [mname], stage, ms)
        with open(memo_dir / "_source_map.tsv", "a", encoding="utf-8") as f:
            f.write(f"{name}\t{rel}\t{'prep' if ext in TEXT_EXT else 'ingest'}\n")
        if not (memo_dir / mname).exists() and lim and ext in (".csv", ".tsv", ".xlsx"):
            # The model found nothing to say about a small table -- measured 2026-10-04 on a
            # meta-analysis's pooled-estimates table and a Monte Carlo summary, retried 3-4
            # times. A computed card still can, every row of a small table a claim.
            import table_card
            if table_card.write_cards(root, memo_dir, [rel], ms=ms, log=lambda *a: None):
                return "table-card", "the model gave no claims; computed card instead"
        return ("memo" if (memo_dir / mname).exists() else "no-claims"), r.stderr[-200:]
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def paused() -> bool:
    return (qdir() / "paused").exists()


def _is_card(p: Path, ext: str, cfg: dict) -> bool:
    """Will this file get a computed table card rather than a model pass? Decided by
    table_card.card_reason, the same call process_doc makes, so the two can never disagree."""
    lim = int(cfg.get("table_card_min_chunks", 100) or 0)
    bib = bool(cfg.get("table_card_bibliographic", True))
    if not (lim or bib) or ext not in (".csv", ".tsv", ".xlsx"):
        return False
    try:
        import table_card
        return bool(table_card.card_reason(str(p.resolve()), lim, bib))
    except Exception:
        return False


def _beat(**extra) -> None:
    (qdir() / "worker.json").write_text(json.dumps({"pid": os.getpid(), "hb": time.time(), **extra}), encoding="utf-8")


def _take_queue() -> list[dict]:
    q = qdir() / "queue.jsonl"
    if not q.exists() or q.stat().st_size == 0:
        return []
    work = qdir() / f"queue.{os.getpid()}.jsonl"
    os.replace(q, work)                       # new appends go to a fresh queue.jsonl
    items, seen = [], set()
    for ln in work.read_text(encoding="utf-8").splitlines():
        try:
            it = json.loads(ln)
        except ValueError:
            continue
        k = (it["root"], it["rel"])
        if k not in seen:
            seen.add(k)
            items.append(it)
    work.unlink()
    return items


def _requeue(items: list[dict]) -> None:
    with open(qdir() / "queue.jsonl", "a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def work(cfg: dict, debounce: float = 8.0, idle_exit: float = 30.0) -> dict:
    if worker_alive():
        return {"skipped": "another worker is running"}
    _beat(state="debounce")
    time.sleep(debounce)                      # a burst of edits becomes one pass
    done = {"tables": 0, "memos": 0, "cards": 0, "no_claims": 0, "errors": 0, "deferred": 0}
    sdb = state_db()
    idle_since = time.time()
    touched_roots = set()
    while True:
        items = _take_queue()
        if not items:
            if time.time() - idle_since > idle_exit:
                break
            _beat(state="idle")
            time.sleep(3)
            continue
        idle_since = time.time()
        deferred = []
        gpu_ok = None
        for i, it in enumerate(items):
            root, rel = Path(it["root"]), it["rel"]
            p = root / rel
            _beat(state="working", current=rel, left=len(items) - i)
            if not p.exists():
                continue
            ext = os.path.splitext(rel)[1].lower()
            outcome, detail = "skipped", ""
            try:
                if ext in TABLE_EXT and cfg.get("corpus_tables", True):
                    import tables
                    tdb = tables.connect()
                    res = tables.import_file(tdb, root, p)
                    tdb.commit(); tdb.close()
                    done["tables"] += len(res)
                    outcome = "table"
                if _is_card(p, ext, cfg):
                    # A table card is computed, not generated: no GPU, so neither the pause
                    # flag nor a missing Ollama holds it back -- same as the SQL import above.
                    outcome, detail = process_doc(root, rel, cfg)
                    done["cards" if outcome == "table-card" else "errors"] += 1
                else:
                    if paused() or not cfg.get("ingest_model", True):
                        deferred.append(it); done["deferred"] += 1
                        continue
                    if gpu_ok is None:
                        gpu_ok = ensure_ollama(cfg)
                    if not gpu_ok:
                        deferred.append(it); done["deferred"] += 1
                        continue
                    outcome, detail = process_doc(root, rel, cfg)
                    if outcome == "memo":
                        done["memos"] += 1
                    elif outcome == "table-card":       # the no-claims fallback
                        done["cards"] += 1
                    elif outcome in ("no-claims", "empty"):
                        done["no_claims"] += 1
                    else:
                        done["errors"] += 1
            except Exception as e:
                outcome, detail = "error", f"{type(e).__name__}: {e}"[:200]
                done["errors"] += 1
            st = p.stat()
            sdb.execute("INSERT OR REPLACE INTO filestate VALUES (?,?,?,?,?,?)",
                        (str(root), rel, st.st_mtime, st.st_size, time.time(), outcome))
            sdb.execute("INSERT INTO log VALUES (?,?,?,?,?)", (time.time(), str(root), rel, outcome, detail))
            sdb.commit()
            touched_roots.add(root)
        if deferred:
            _requeue(deferred)
            break                              # paused / no GPU: leave the rest queued
    for root in touched_roots:
        try:
            import store
            store.sync_root(root, cfg=cfg, log=lambda *a: None)
        except Exception:
            pass
    (qdir() / "worker.json").unlink(missing_ok=True)
    mg.append_metrics({"ts": time.time(), **done}, event="ingest")
    return done


def status() -> dict:
    q = qdir() / "queue.jsonl"
    n = len(q.read_text(encoding="utf-8").splitlines()) if q.exists() else 0
    try:
        last = json.loads((qdir() / "scan.json").read_text(encoding="utf-8"))
    except Exception:
        last = {}
    db = state_db()
    recent = db.execute("SELECT datetime(t,'unixepoch','localtime'), outcome, rel FROM log"
                        " ORDER BY t DESC LIMIT 5").fetchall()
    return {"queued": n, "paused": paused(), "worker_alive": worker_alive(),
            "ollama_up": ollama_up(1.0), "last_scan": last.get("t") and time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(last["t"])), "scan_result": last.get("roots"),
            "known_files": db.execute("SELECT COUNT(*) FROM filestate").fetchone()[0],
            "recent": recent}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    for flag in ("--status", "--pause", "--resume", "--scan", "--now", "--worker"):
        g.add_argument(flag, action="store_true")
    g.add_argument("--enqueue")
    a = ap.parse_args()
    cfg = mg.load_config()
    if a.pause:
        (qdir() / "paused").write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
        print("ingest paused: documents stay queued, the GPU is not touched")
        return 0
    if a.resume:
        (qdir() / "paused").unlink(missing_ok=True)
        ensure_worker()
        print("ingest resumed")
        return 0
    if a.scan:
        print(json.dumps(scan(cfg), ensure_ascii=False))
        return 0
    if a.enqueue:
        ok = enqueue(Path(a.enqueue).resolve(), "manual", cfg)
        print("queued" if ok else "not inside a corpus root, or not an indexable type")
        if ok:
            ensure_worker()
        return 0
    if a.worker or a.now:
        print(json.dumps(work(cfg, debounce=0 if a.now else 8.0), ensure_ascii=False))
        return 0
    print(json.dumps(status(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
