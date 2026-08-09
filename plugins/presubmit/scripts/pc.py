#!/usr/bin/env python3
"""Presubmit — catch the common manuscript submission mistakes before a journal
does. Deterministic, offline, no language model.

    pc.py check MANUSCRIPT [--journal cureus] [--json report.json]
    pc.py refs MANUSCRIPT           # references only
    pc.py ethics MANUSCRIPT         # disclosures only
    pc.py format MANUSCRIPT         # language/typography only
    pc.py authors MANUSCRIPT
    pc.py abstract MANUSCRIPT
    pc.py journals                  # list built-in journal profiles
    pc.py selftest

Reads .docx / .pdf / .tex / .txt / .md (and .doc/.odt/.rtf via doctotext).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pc_lib
import pc_checks as C

CATS = ["structure", "authors", "abstract", "references", "ethics", "format"]
SEV_ICON = {pc_lib.ERROR: "✗", pc_lib.WARN: "!", pc_lib.INFO: "·"}
SEV_LABEL = {pc_lib.ERROR: "ERROR", pc_lib.WARN: "WARN", pc_lib.INFO: "INFO"}


def _run(cats, args):
    import pc_extract
    doc = pc_extract.load(args.manuscript)
    profile = pc_lib.load_profile(getattr(args, "journal", "generic"))
    findings = []
    for cat in cats:
        findings.extend(C.ALL_CHECKS[cat](doc, profile))
    report = _report(doc, profile, findings, args.manuscript)
    _print(report)
    if getattr(args, "json", None):
        Path(args.json).write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\n  audit written: {args.json}")
    # exit non-zero if any ERROR, so it can gate a pipeline
    return 1 if report["counts"]["error"] else 0


def _report(doc, profile, findings, path):
    counts = {pc_lib.ERROR: 0, pc_lib.WARN: 0, pc_lib.INFO: 0}
    for f in findings:
        counts[f.severity] += 1
    if counts[pc_lib.ERROR]:
        verdict = "NOT READY — fix the errors below before submitting"
    elif counts[pc_lib.WARN]:
        verdict = "NEARLY READY — clear the warnings to be safe"
    else:
        verdict = "READY — no blocking issues found by the automated checks"
    return {
        "manuscript": str(path), "source": doc.source,
        "journal": profile["name"],
        "words": pc_lib.word_count(doc.text),
        "sections_found": doc.sections.get("_order", []),
        "counts": counts, "verdict": verdict,
        "findings": [f.as_dict() for f in _sorted(findings)],
    }


def _sorted(findings):
    return sorted(findings, key=lambda f: (CATS.index(f.category)
                  if f.category in CATS else 9, pc_lib.SEV_RANK[f.severity]))


def _print(r):
    print("=" * 68)
    print(f"  PRESUBMIT CHECK — {Path(r['manuscript']).name}")
    print(f"  profile: {r['journal']}   |   {r['words']} words   |   "
          f"source: {r['source']}")
    print("=" * 68)
    secs = ", ".join(r["sections_found"]) or "(none detected)"
    print(f"  sections: {secs}")
    c = r["counts"]
    print(f"  totals:  {c['error']} error   {c['warn']} warn   {c['info']} info")
    print(f"  VERDICT: {r['verdict']}")
    print("-" * 68)
    cur = None
    for f in r["findings"]:
        if f["category"] != cur:
            cur = f["category"]
            print(f"\n[{cur.upper()}]")
        icon = SEV_ICON[f["severity"]]
        where = f" ({f['where']})" if f["where"] else ""
        print(f"  {icon} {SEV_LABEL[f['severity']]}: {f['message']}{where}")
        if f["fix"]:
            print(f"      → {f['fix']}")
    if not r["findings"]:
        print("\n  Nothing flagged. 🎉")
    print()


# ---- subcommands -------------------------------------------------------------
def cmd_check(args):
    return _run(CATS, args)


def cmd_one(cat):
    def run(args):
        return _run([cat], args)
    return run


def cmd_journals(args):
    print("Built-in journal profiles:")
    for name in pc_lib.list_profiles():
        p = pc_lib.load_profile(name)
        print(f"  {name:12} — {p['name']}")
        if p.get("notes"):
            print(f"               {p['notes']}")
    print("\nUse:  pc.py check MS.docx --journal <name>")
    return 0


def cmd_selftest(args):
    from selftest import run
    return 0 if run() else 1


def build_parser():
    p = argparse.ArgumentParser(prog="pc.py", description="Presubmit checker")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_ms(sp, journal=True):
        sp.add_argument("manuscript")
        if journal:
            sp.add_argument("--journal", default="generic",
                            help="profile name (see `pc.py journals`)")
        sp.add_argument("--json", default=None, help="write JSON audit here")

    c = sub.add_parser("check", help="run every check")
    add_ms(c); c.set_defaults(func=cmd_check)
    for cat in ("refs", "ethics", "format", "authors", "abstract"):
        key = "references" if cat == "refs" else cat
        sp = sub.add_parser(cat, help=f"{key} check only")
        add_ms(sp); sp.set_defaults(func=cmd_one(key))
    j = sub.add_parser("journals", help="list journal profiles")
    j.set_defaults(func=cmd_journals)
    st = sub.add_parser("selftest", help="run the built-in self test")
    st.set_defaults(func=cmd_selftest)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
