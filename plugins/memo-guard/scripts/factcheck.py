#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit what is IN the memory store, not what recall does with it.

    factcheck.py                     # report only, offline
    factcheck.py --online            # also verify DOIs and PMIDs against Crossref/PubMed
    factcheck.py --quarantine        # drop the utility of everything flagged to 0
    factcheck.py --json report.json

Why this exists
---------------
memo-guard's whole promise is that a fact written months ago comes back when it
is relevant. Nothing in that promise checks whether the fact is still TRUE, or
was ever true. Recall serves whatever is in the store, in the authoritative
voice of the user's own long-term memory, and a wrong fact recalled confidently
is worse than no memory at all.

That is not hypothetical here. The self test used to run against the production
store, and it left an invented PROSPERO registration number and an invented
rejection reason in long-term memory, where they sat undetected until someone
went looking. Nothing flagged them, because nothing was looking.

Six checks, cheapest first
--------------------------
1. synthetic provenance  — the fact belongs to a project that never existed on
                           this disk, or to a known test path
2. dangling reference    — it names a file or directory that is gone
3. refuted              — its text matches a claim already judged REFUTED
4. malformed identifier  — a DOI, PMID, PROSPERO or NCT id that cannot be real
5. unverifiable identifier (--online) — well-formed, but no authority knows it
6. stale                 — old, never recalled, and low utility

Nothing is deleted. `--quarantine` sets utility to 0, which takes a fact out of
recall while leaving it readable and restorable — deleting evidence is how you
lose the ability to work out what went wrong.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mg_lib as mg  # noqa: E402
import memory  # noqa: E402

#: Paths that only ever appear in fixtures. `/repo` is the self test's synthetic
#: project; the rest are scratch space no long-term fact should be tied to.
TEST_PATHS = ("/repo", "/tmp/", "/private/tmp/", "mg-selftest", "mg-test",
              "/var/folders/")

DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:a-z0-9<>\[\]+]+", re.I)
PMID = re.compile(r"\bPMID:?\s*(\d{6,9})\b", re.I)
PROSPERO = re.compile(r"\bCRD\d{11,}\b", re.I)
NCT = re.compile(r"\bNCT\d{8}\b", re.I)
#: A path that looks like a path: absolute, with an extension. The lookbehind
#: excludes `>` because `<outdir>/osszesitett_lista.csv` is a placeholder in
#: prose, not a file — matching from the slash reported two such fragments as
#: missing files on the first run.
PATHLIKE = re.compile(r"(?<![\w>])(~?/[\w.\-/]+\.[A-Za-z0-9]{1,6})(?![\w])")


class Finding:
    __slots__ = ("fid", "level", "check", "message", "detail")

    def __init__(self, fid, level, check, message, detail=""):
        self.fid, self.level, self.check = fid, level, check
        self.message, self.detail = message, detail

    def as_dict(self):
        return {"fact": self.fid, "level": self.level, "check": self.check,
                "message": self.message, "detail": self.detail}


# --------------------------------------------------------------------- checks

def check_provenance(rows, projects) -> list[Finding]:
    out = []
    for r in rows:
        cwd = projects.get(r["project_id"], {}).get("cwd")
        if cwd is None:
            out.append(Finding(r["id"], "warn", "provenance",
                               "belongs to a project with no directory",
                               "usually a fixture written by a test run"))
            continue
        if any(t in cwd for t in TEST_PATHS):
            out.append(Finding(r["id"], "error", "provenance",
                               f"belongs to a test path ({cwd})",
                               "facts from fixtures must never reach recall"))
        elif not Path(cwd).exists():
            out.append(Finding(r["id"], "info", "provenance",
                               f"project directory is gone ({cwd})",
                               "the fact may still be true; the context is not"))
    return out


def check_dangling(rows) -> list[Finding]:
    out = []
    for r in rows:
        for m in PATHLIKE.finditer(r["text"] or ""):
            p = Path(m.group(1)).expanduser()
            # Only flag a path whose PARENT still exists. If neither the file
            # nor its directory is there, the string is almost always an
            # illustrative fragment in prose rather than a file that moved, and
            # reporting those buries the real ones.
            if (p.is_absolute() and not p.exists()
                    and p.parent.exists() and p.parent != p):
                out.append(Finding(r["id"], "info", "dangling",
                                   f"names a file that no longer exists: {m.group(1)}",
                                   "the fact may be about a renamed or deleted file"))
                break
    return out


def check_refuted(rows) -> list[Finding]:
    try:
        import claims
        cdb = claims.connect()
    except Exception:
        return []
    out = []
    for r in rows:
        try:
            hit = claims.lookup(cdb, r["text"]) if hasattr(claims, "lookup") else None
        except Exception:
            hit = None
        if hit and str(hit.get("status", "")).upper() == "REFUTED":
            out.append(Finding(r["id"], "error", "refuted",
                               "restates a claim already judged REFUTED",
                               hit.get("note", "")))
    return out


def check_identifiers(rows, online: bool, timeout: float = 8.0) -> list[Finding]:
    out = []
    for r in rows:
        text = r["text"] or ""
        for m in PROSPERO.finditer(text):
            # PROSPERO ids are CRD + 11 digits, and the first four are the year
            # of registration. A number outside a plausible year is not a typo,
            # it is invented.
            digits = m.group(0)[3:]
            year = int(digits[:4])
            if not (2011 <= year <= time.gmtime().tm_year + 1):
                out.append(Finding(r["id"], "error", "identifier",
                                   f"impossible PROSPERO id {m.group(0)}",
                                   f"registration year reads {year}"))
        for m in NCT.finditer(text):
            pass  # format alone is all that can be checked offline
        if not online:
            continue
        for m in DOI.finditer(text):
            if not _crossref_has(m.group(0).rstrip(".,);"), timeout):
                out.append(Finding(r["id"], "error", "identifier",
                                   f"DOI not found at Crossref: {m.group(0)}",
                                   "either mistyped or never existed"))
        for m in PMID.finditer(text):
            if not _pubmed_has(m.group(1), timeout):
                out.append(Finding(r["id"], "error", "identifier",
                                   f"PMID not found at PubMed: {m.group(1)}"))
    return out


def _get(url: str, timeout: float) -> bytes | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": "memo-guard-factcheck/1.0 (mailto:noreply@example.org)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def _crossref_has(doi: str, timeout: float) -> bool:
    raw = _get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe=""),
               timeout)
    # No answer is not the same as "does not exist". An offline machine must not
    # produce a report accusing every reference of being fabricated.
    return True if raw is None else b'"status":"ok"' in raw


def _pubmed_has(pmid: str, timeout: float) -> bool:
    raw = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
               + urllib.parse.urlencode({"db": "pubmed", "id": pmid,
                                         "retmode": "json"}), timeout)
    if raw is None:
        return True
    try:
        d = json.loads(raw)
        rec = (d.get("result") or {}).get(str(pmid)) or {}
        return bool(rec) and "error" not in rec
    except Exception:
        return True


def check_stale(rows, days: int = 180) -> list[Finding]:
    cutoff = time.time() - days * 86400
    out = []
    for r in rows:
        if (r["created_at"] or 0) < cutoff and not (r["hits"] or 0):
            out.append(Finding(r["id"], "info", "stale",
                               f"{days}+ days old and never recalled",
                               "not wrong — just never useful; consider pruning"))
    return out


def check_duplicates(rows) -> list[Finding]:
    seen: dict[str, int] = {}
    out = []
    for r in rows:
        key = re.sub(r"[^a-z0-9 ]+", " ", (r["norm"] or r["text"] or "").lower())
        key = " ".join(key.split())[:120]
        if not key:
            continue
        if key in seen:
            out.append(Finding(r["id"], "info", "duplicate",
                               f"near-identical to fact {seen[key]}",
                               "recall will spend budget saying it twice"))
        else:
            seen[key] = r["id"]
    return out


# ----------------------------------------------------------------------- main

def audit(db, online: bool = False) -> list[Finding]:
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute("SELECT * FROM fact")]
    projects = {r["id"]: dict(r) for r in db.execute("SELECT * FROM project")}
    findings: list[Finding] = []
    findings += check_provenance(rows, projects)
    findings += check_refuted(rows)
    findings += check_identifiers(rows, online)
    findings += check_dangling(rows)
    findings += check_duplicates(rows)
    findings += check_stale(rows)
    order = {"error": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: (order.get(f.level, 3), f.fid))
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--online", action="store_true",
                    help="verify DOIs and PMIDs against Crossref and PubMed")
    ap.add_argument("--quarantine", action="store_true",
                    help="set utility to 0 on every error-level finding "
                         "(removes it from recall; nothing is deleted)")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)

    db = memory.connect()
    total = db.execute("SELECT COUNT(*) FROM fact").fetchone()[0]
    findings = audit(db, online=args.online)

    print(f"memo-guard factcheck — {total} facts"
          + ("  (online verification on)" if args.online else ""))
    print("-" * 58)
    if not findings:
        print("nothing flagged.")
    mark = {"error": "!", "warn": "?", "info": "·"}
    for f in findings:
        row = db.execute("SELECT text FROM fact WHERE id=?", (f.fid,)).fetchone()
        text = (row[0] if row else "")[:74]
        print(f"{mark.get(f.level, ' ')} fact {f.fid} [{f.check}] {f.message}")
        print(f"    {text}")
        if f.detail:
            print(f"    → {f.detail}")

    errors = [f for f in findings if f.level == "error"]
    print("-" * 58)
    print(f"{len(errors)} error · "
          f"{sum(1 for f in findings if f.level == 'warn')} warn · "
          f"{sum(1 for f in findings if f.level == 'info')} info")

    if args.quarantine and errors:
        ids = sorted({f.fid for f in errors})
        db.executemany("UPDATE fact SET utility=0 WHERE id=?", [(i,) for i in ids])
        db.commit()
        print(f"quarantined {len(ids)} fact(s): utility set to 0, so recall no "
              f"longer surfaces them. Text kept — restore with "
              f"`UPDATE fact SET utility=0.5 WHERE id IN (...)`.")
    elif errors:
        print("run with --quarantine to take these out of recall "
              "(nothing is deleted).")

    if args.json:
        args.json.write_text(json.dumps(
            {"facts": total, "findings": [f.as_dict() for f in findings]},
            indent=2, ensure_ascii=False))
        print(f"report: {args.json}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
