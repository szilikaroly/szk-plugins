#!/usr/bin/env python3
"""Cross-session claim verdicts — the memory Claude edits itself.

The problem this exists to solve
-------------------------------
memo-index already marks claims REFUTED rather than deleting them, on purpose:
a visibly refuted claim teaches the next reader that the local model believed
something false. But those marks live in `sessions/<id>/.memo`, and memo-guard
builds a FRESH memo dir every session. So a claim refuted on Monday is
regenerated clean on Tuesday from the same archive, with no memory that anyone
ever checked it. The verdict dies with the session; the wrong claim does not.

This store outlives sessions. It is keyed by a fingerprint of the claim's
meaning, not its wording, because the local model rephrases the same wrong idea
every time it regenerates.

  claims.py --refute "PCOS renamed to PMOS in 2019" --note "no such rename"
  claims.py --supersede "sample n=412" --with "sample n=389" --note "after exclusions"
  claims.py --pin "PROSPERO ID is truncated in the submitted PDF"
  claims.py --check "the 2019 PCOS to PMOS rename"      # would this be blocked?
  claims.py --apply --memo-dir sessions/<id>/.memo      # enforce before RESUME
  claims.py --list
  claims.py --forget <fingerprint>                      # undo a verdict

Why fuzzy matching and not exact hashes: the model writes "n=412 participants"
one day and "412 subjects were enrolled" the next. An exact hash blocks the
first and lets the second through, which is worse than useless — it looks like
the mechanism works. Token-set overlap catches the rephrasing.

`hits` counts how many times a refuted claim tried to come back. If that number
stays at zero the store is doing nothing and should be deleted; if it climbs,
it is the only thing standing between you and a resurrected error.

Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402

# Same shape memo-index writes: - [C3] [SUPPORTED] text @anchor <!-- note -->
CLAIM_RE = re.compile(r"^(\s*-\s*\[)(C\d+)(\]\s*\[)(\w+)(\]\s*)(.*?)(\s*@\S.*?)?(\s*<!--.*-->)?\s*$")

STATUSES = ("REFUTED", "SUPERSEDED", "PINNED")

# Dropped before fingerprinting. Deliberately small: aggressive stopword removal
# makes unrelated claims collide, and a false block is worse than a miss.
_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "of", "in", "on",
    "at", "to", "for", "with", "and", "or", "that", "this", "it", "its", "as",
    "by", "from", "has", "have", "had", "not", "no",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS verdict (
  fp          TEXT PRIMARY KEY,
  text        TEXT NOT NULL,
  norm        TEXT NOT NULL,
  status      TEXT NOT NULL,
  note        TEXT DEFAULT '',
  replacement TEXT DEFAULT '',
  project     TEXT DEFAULT '',
  session_id  TEXT DEFAULT '',
  created_at  REAL,
  hits        INTEGER DEFAULT 0,
  last_hit    REAL
);
CREATE INDEX IF NOT EXISTS verdict_status ON verdict(status);
CREATE TABLE IF NOT EXISTS verdict_vec (
  fp     TEXT NOT NULL,
  model  TEXT NOT NULL,
  dim    INTEGER NOT NULL,
  data   BLOB NOT NULL,
  PRIMARY KEY (fp, model)
);
"""

# Lexical overlap cannot tell meaning from coincidence: "412 participants were
# enrolled" and the recorded "the sample size was n=412" score 0.533, the same
# as the unrelated "endometriosis was renamed in 2019". No threshold separates
# them. Embeddings can — so lexical runs first (free, offline) and semantic only
# adjudicates what lexical was unsure about.
SEMANTIC_THRESHOLD = 0.72


def db_path() -> Path:
    return mg.data_dir() / "claims.db"


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(db_path(), timeout=5.0)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    # The store names things said in private sessions. secure_file() reports
    # whether the OS actually restricted it — on Windows it cannot.
    mg.secure_file(db_path())
    return db


# --------------------------------------------------------------------------- matching

def normalize(text: str) -> str:
    t = text.lower()
    t = re.sub(r"<!--.*?-->", " ", t)          # editor notes
    t = re.sub(r"@\S+", " ", t)                # anchors
    t = re.sub(r"`[^`]*`", " ", t)             # code spans
    t = re.sub(r"[^a-z0-9\s.%<>=-]", " ", t)   # keep numbers/comparators, drop prose punctuation
    words = [w for w in t.split() if w not in _STOP]
    return " ".join(words)


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()[:16]


_SUFFIXES = ("ingly", "edly", "ings", "ing", "edness", "ed", "es", "s", "ly", "ment", "tion", "sion")


def _stem(w: str) -> str:
    """Crude suffix stripping. Not linguistics — just enough that renamed,
    rename and renaming collide, which is how the same wrong claim comes back."""
    if w.replace(".", "").replace("%", "").isdigit():
        return w
    for suf in _SUFFIXES:
        if len(w) > len(suf) + 3 and w.endswith(suf):
            w = w[: -len(suf)]
            break
    # Without this, "references" -> "referenc" but "reference" stays whole, and
    # the singular never matches the plural. That asymmetry silently halves the
    # overlap score and lets a refuted claim back through.
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    return w


def _tokens(norm: str) -> set[str]:
    out = set()
    for w in norm.split():
        # n=412 and 412 are the same fact stated two ways
        for part in re.split(r"[=<>]+", w):
            part = part.strip(".-")
            if len(part) > 2 or part.isdigit():
                out.add(_stem(part))
    return out


def similarity(a: str, b: str) -> float:
    """Blend of Jaccard and overlap coefficient.

    Jaccard alone punishes a rephrasing for being wordier than the original,
    which is exactly what a regenerated claim tends to be. The overlap
    coefficient ignores length and asks the question that actually matters:
    did the shorter claim's content survive into the longer one?
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    jac = inter / len(ta | tb)
    ovl = inter / min(len(ta), len(tb))
    return 0.5 * jac + 0.5 * ovl


def match(db: sqlite3.Connection, text: str, threshold: float = 0.55) -> dict | None:
    """Exact fingerprint first, then nearest rephrasing above the threshold.

    0.55 was calibrated on rephrasings of real claims: it catches 6 of 7 with no
    false positives. The known limit is real and worth stating — "412 participants
    were enrolled" against a recorded "the sample size was n=412" scores 0.533,
    the same score as the unrelated "endometriosis was renamed in 2019". No
    threshold separates those two, because lexical overlap cannot tell meaning
    from coincidence. Claims that say the same thing in different words will slip
    through; ask --check when it matters, or move to embeddings.
    """
    norm = normalize(text)
    fp = hashlib.sha256(norm.encode()).hexdigest()[:16]
    row = db.execute(
        "SELECT fp,text,norm,status,note,replacement,hits FROM verdict WHERE fp=?", (fp,)
    ).fetchone()
    if row:
        return _row(row, 1.0)
    best, best_score = None, 0.0
    for row in db.execute(
        "SELECT fp,text,norm,status,note,replacement,hits FROM verdict"
    ):
        s = similarity(norm, row[2])
        if s > best_score:
            best, best_score = row, s
    if best and best_score >= threshold:
        return _row(best, best_score)

    # Lexical was not convinced. Ask the embedder — but only over the verdict
    # list, which is tens of rows, so this stays one embed call plus a tiny
    # dot-product loop. No embedder available means we simply keep the lexical
    # answer rather than failing.
    sem = _semantic_match(db, text)
    if sem:
        return sem
    return None


def _semantic_match(db: sqlite3.Connection, text: str) -> dict | None:
    # Check this before embedding, not after: with no verdicts on record there is
    # nothing to compare against, and this runs once per claim during compression
    # and once per fact during recall. An unconditional embed there costs ~20 ms
    # each for an answer that is always None.
    if not db.execute("SELECT 1 FROM verdict_vec LIMIT 1").fetchone():
        return None
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import embed as E
    except Exception:
        return None
    r = E.embed(text, profile="bulk")
    if not r:
        return None
    model, qv = r[0], E.normalize(r[1])
    best, best_score = None, 0.0
    for fp, mdl, dim, blob in db.execute(
            "SELECT fp,model,dim,data FROM verdict_vec WHERE model=?", (model,)):
        if dim != len(qv):
            continue                      # different space; never compare
        s = E.cosine(qv, E.unpack(blob))
        if s > best_score:
            best, best_score = fp, s
    if not best or best_score < SEMANTIC_THRESHOLD:
        return None
    row = db.execute(
        "SELECT fp,text,norm,status,note,replacement,hits FROM verdict WHERE fp=?",
        (best,)).fetchone()
    return _row(row, best_score) if row else None


def _row(row, score: float) -> dict:
    return {"fp": row[0], "text": row[1], "status": row[3], "note": row[4],
            "replacement": row[5], "hits": row[6], "score": round(score, 3)}


# --------------------------------------------------------------------------- writes

def record(db: sqlite3.Connection, text: str, status: str, note: str = "",
           replacement: str = "", session_id: str = "", project: str = "") -> dict:
    norm = normalize(text)
    if not norm:
        raise ValueError("claim text is empty after normalization")
    fp = hashlib.sha256(norm.encode()).hexdigest()[:16]
    db.execute(
        "INSERT INTO verdict (fp,text,norm,status,note,replacement,project,session_id,created_at,hits)"
        " VALUES (?,?,?,?,?,?,?,?,?,0)"
        " ON CONFLICT(fp) DO UPDATE SET status=excluded.status, note=excluded.note,"
        " replacement=excluded.replacement",
        (fp, text.strip(), norm, status, note, replacement, project, session_id, time.time()),
    )
    # Store the vector alongside, so the semantic path has something to compare
    # against later. Failure here is not fatal — lexical matching still works.
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import embed as E
        r = E.embed(text, profile="bulk")
        if r:
            v = E.normalize(r[1])
            db.execute("INSERT INTO verdict_vec (fp,model,dim,data) VALUES (?,?,?,?)"
                       " ON CONFLICT(fp,model) DO UPDATE SET data=excluded.data",
                       (fp, r[0], len(v), E.pack(v)))
    except Exception:
        pass
    db.commit()
    return {"fp": fp, "status": status, "text": text.strip()}


def bump(db: sqlite3.Connection, fp: str) -> None:
    db.execute("UPDATE verdict SET hits=hits+1, last_hit=? WHERE fp=?", (time.time(), fp))


# --------------------------------------------------------------------------- enforcement

def apply_to_memo_dir(db: sqlite3.Connection, memo_dir: Path) -> dict:
    """Rewrite regenerated claims that a past session already judged.

    Runs after memo generation and before the RESUME is built, so a resurrected
    claim never reaches a fresh context unlabelled. PINNED claims are left alone
    — pinning protects a claim, it does not assert anything about others.
    """
    changed, scanned, blocked = 0, 0, []
    if not memo_dir.exists():
        return {"scanned": 0, "changed": 0, "blocked": []}
    for f in sorted(memo_dir.rglob("*.md")):
        try:
            lines = f.read_text().splitlines()
        except OSError:
            continue
        out, dirty = [], False
        for ln in lines:
            m = CLAIM_RE.match(ln)
            if not m:
                out.append(ln)
                continue
            scanned += 1
            body = m.group(6) or ""
            v = match(db, body)
            if not v or v["status"] == "PINNED" or m.group(4) == "REFUTED":
                out.append(ln)
                continue
            bump(db, v["fp"])
            note = v["note"] or "previously judged in an earlier session"
            if v["status"] == "SUPERSEDED" and v["replacement"]:
                new_body = v["replacement"]
                tag = "SUPPORTED"
                note = f"superseded earlier wording; {note}"
            else:
                new_body = body
                tag = "REFUTED"
            out.append(f"{m.group(1)}{m.group(2)}{m.group(3)}{tag}{m.group(5)}"
                       f"{new_body}{m.group(7) or ''} <!-- memo-guard: {note} -->")
            blocked.append({"fp": v["fp"], "status": v["status"],
                            "score": v["score"], "text": body[:80]})
            changed, dirty = changed + 1, True
        if dirty:
            f.write_text("\n".join(out) + "\n")
    db.commit()
    return {"scanned": scanned, "changed": changed, "blocked": blocked}


# --------------------------------------------------------------------------- cli

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refute", metavar="TEXT")
    ap.add_argument("--supersede", metavar="OLD")
    ap.add_argument("--with", dest="replacement", metavar="NEW")
    ap.add_argument("--pin", metavar="TEXT")
    ap.add_argument("--note", default="")
    ap.add_argument("--check", metavar="TEXT")
    ap.add_argument("--forget", metavar="FP_OR_TEXT")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--memo-dir", type=Path)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--session", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = connect()

    if args.refute:
        r = record(db, args.refute, "REFUTED", args.note, session_id=args.session)
        print(json.dumps(r) if args.json else f"REFUTED [{r['fp']}] {r['text'][:90]}")
        return 0

    if args.supersede:
        if not args.replacement:
            print("--supersede needs --with <new text>", file=sys.stderr)
            return 2
        r = record(db, args.supersede, "SUPERSEDED", args.note,
                   replacement=args.replacement, session_id=args.session)
        print(json.dumps(r) if args.json else
              f"SUPERSEDED [{r['fp']}] -> {args.replacement[:70]}")
        return 0

    if args.pin:
        r = record(db, args.pin, "PINNED", args.note, session_id=args.session)
        print(json.dumps(r) if args.json else f"PINNED [{r['fp']}] {r['text'][:90]}")
        return 0

    if args.check:
        v = match(db, args.check)
        if args.json:
            print(json.dumps(v or {}, indent=2))
        elif v:
            print(f"{v['status']} [{v['fp']}] similarity={v['score']} "
                  f"hits={v['hits']}\n  recorded: {v['text'][:90]}\n  note: {v['note']}")
        else:
            print("no verdict on record")
        return 0 if v else 1

    if args.forget:
        cur = db.execute("DELETE FROM verdict WHERE fp=?", (args.forget,))
        if cur.rowcount == 0:
            v = match(db, args.forget)
            if v:
                cur = db.execute("DELETE FROM verdict WHERE fp=?", (v["fp"],))
        db.commit()
        print(f"forgotten: {cur.rowcount} verdict(s)")
        return 0 if cur.rowcount else 1

    if args.apply:
        md = args.memo_dir
        if not md:
            print("--apply needs --memo-dir", file=sys.stderr)
            return 2
        res = apply_to_memo_dir(db, md)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"claims scanned={res['scanned']} rewritten={res['changed']}")
            for b in res["blocked"]:
                print(f"  {b['status']} (sim {b['score']}) {b['text']}")
        return 0

    rows = list(db.execute(
        "SELECT fp,status,hits,text,note FROM verdict ORDER BY hits DESC, created_at DESC"))
    if args.json:
        print(json.dumps([{"fp": r[0], "status": r[1], "hits": r[2],
                           "text": r[3], "note": r[4]} for r in rows], indent=2))
        return 0
    if not rows:
        print("no verdicts recorded yet")
        print(f"store: {db_path()}")
        return 0
    print(f"{len(rows)} verdict(s) — 'hits' = times the claim tried to come back\n")
    for fp, status, hits, text, note in rows:
        print(f"  [{fp}] {status:<11} hits={hits:<3} {text[:70]}")
        if note:
            print(f"                             note: {note[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
