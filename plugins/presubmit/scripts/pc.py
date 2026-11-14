#!/usr/bin/env python3
"""Presubmit — catch the common manuscript submission mistakes before a journal
does. Deterministic, offline, no language model.

    pc.py check MANUSCRIPT [--journal cureus] [--json report.json]
    pc.py refs MANUSCRIPT           # references only
    pc.py ethics MANUSCRIPT         # disclosures only
    pc.py format MANUSCRIPT         # language/typography only
    pc.py reviewer MANUSCRIPT       # what a referee will write back about
    pc.py style MANUSCRIPT          # AI-draft tells (advisory; not in `check`)
    pc.py invariants ORIG REWRITE   # did a rewrite keep every number and citation?
    pc.py text MANUSCRIPT [--section NAME ...]   # plain text of the body or sections
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

CATS = ["structure", "authors", "abstract", "references", "ethics", "format",
        "submission", "claims", "reviewer"]
SEV_ICON = {pc_lib.ERROR: "✗", pc_lib.WARN: "!", pc_lib.INFO: "·"}
SEV_LABEL = {pc_lib.ERROR: "ERROR", pc_lib.WARN: "WARN", pc_lib.INFO: "INFO"}


def _run(cats, args):
    import pc_extract
    doc = pc_extract.load(args.manuscript)
    profile = pc_lib.load_profile(getattr(args, "journal", "generic"))
    findings = []
    for cat in cats:
        findings.extend(C.ALL_CHECKS[cat](doc, profile))
    if getattr(args, "online", False) and "references" in cats:
        findings.extend(_online_findings(doc))
    report = _report(doc, profile, findings, args.manuscript,
                     advisory=(cats == ["style"]))
    _print(report)
    if getattr(args, "json", None):
        Path(args.json).write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\n  audit written: {args.json}")
    # exit non-zero if any ERROR, so it can gate a pipeline
    return 1 if report["counts"]["error"] else 0


def _online_findings(doc):
    """Opt-in PubMed lookup: has a cited paper been corrected or retracted?"""
    import pc_online
    from pc_lib import F, ERROR, WARN, INFO
    entries = C._reference_entries(doc)
    if not entries:
        return []
    results, err = pc_online.check(entries)
    if err:
        return [F("references", INFO, "online-check-skipped",
                  f"Correction/retraction check could not run: {err}.",
                  fix="Re-run with a working connection, or verify the references by hand.")]
    out = []
    for idx, kind, msg, ident in results:
        where = f"reference {idx}" if idx else ident
        sev = ERROR if kind == "retraction" else WARN
        out.append(F("references", sev, f"reference-{kind}", msg, where=where,
                     fix="Open the notice and check whether it touches the number you "
                         "quote. Many corrections are bibliographic only — but you have "
                         "to look before you can say so."))
    if not out:
        out.append(F("references", INFO, "online-check-clean",
                     "No corrections, retractions or expressions of concern found for the "
                     "references that resolved to a PubMed record."))
    return out


def _report(doc, profile, findings, path, advisory=False):
    counts = {pc_lib.ERROR: 0, pc_lib.WARN: 0, pc_lib.INFO: 0}
    for f in findings:
        counts[f.severity] += 1
    if advisory:
        n = counts[pc_lib.WARN] + counts[pc_lib.INFO]
        verdict = (f"STYLE — {n} kind(s) of AI-draft tell flagged; advisory only, "
                   "readiness is judged by `check`" if n else
                   "STYLE — no AI-draft tells found by the automated rules")
    elif counts[pc_lib.ERROR]:
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


def cmd_invariants(args):
    """A rewrite must change no number, equation, citation or cross-reference."""
    import pc_extract
    import pc_style
    a = pc_extract.load(args.original).text
    b = pc_extract.load(args.rewrite).text
    diffs = pc_style.invariants(a, b)
    print("=" * 68)
    print(f"  REWRITE INVARIANTS — {Path(args.original).name} → {Path(args.rewrite).name}")
    print("=" * 68)
    if not diffs:
        print("  PRESERVED — every number, citation, cite key, DOI, equation and\n"
              "  table/figure cross-reference in the original is in the rewrite.")
    for kind, missing, added in diffs:
        print(f"  ✗ {kind}:")
        if missing:
            print(f"      lost:  {', '.join(map(str, missing[:20]))}"
                  + (" …" if len(missing) > 20 else ""))
        if added:
            print(f"      added: {', '.join(map(str, added[:20]))}"
                  + (" …" if len(added) > 20 else ""))
    print()
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"original": args.original, "rewrite": args.rewrite, "preserved": not diffs,
             "diffs": [{"kind": k, "lost": m, "added": a_} for k, m, a_ in diffs]},
            indent=2, ensure_ascii=False))
        print(f"  audit written: {args.json}")
    return 1 if diffs else 0


def cmd_text(args):
    """Plain text of the body (before the references) or of named sections,
    for a rewrite pass and for `invariants` to compare against."""
    import pc_extract
    doc = pc_extract.load(args.manuscript)
    if not args.section:
        ref = doc.sections.get("references", "")
        body = doc.text.split(ref)[0] if ref and ref in doc.text else doc.text
        sys.stdout.write(body.rstrip() + "\n")
        return 0
    missing = [s for s in args.section if s.lower() not in doc.sections]
    if missing:
        have = ", ".join(doc.sections.get("_order", [])) or "(none detected)"
        print(f"section(s) not found: {', '.join(missing)}. Detected: {have}",
              file=sys.stderr)
        return 2
    for s in args.section:
        sys.stdout.write(f"{s.title()}\n{doc.sections[s.lower()].strip()}\n\n")
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
        sp.add_argument("--online", action="store_true",
                        help="also ask PubMed whether any cited paper has been "
                             "corrected or retracted (the only check that uses the network)")

    c = sub.add_parser("check", help="run every check")
    add_ms(c); c.set_defaults(func=cmd_check)
    for cat in ("refs", "ethics", "format", "authors", "abstract",
                "submission", "claims", "reviewer", "style"):
        key = "references" if cat == "refs" else cat
        sp = sub.add_parser(cat, help=f"{key} check only")
        add_ms(sp); sp.set_defaults(func=cmd_one(key))
    iv = sub.add_parser("invariants", help="check that a rewrite kept every number, "
                        "citation, equation and cross-reference")
    iv.add_argument("original")
    iv.add_argument("rewrite")
    iv.add_argument("--json", default=None, help="write JSON audit here")
    iv.set_defaults(func=cmd_invariants)
    tx = sub.add_parser("text", help="print the body, or named sections, as plain text")
    tx.add_argument("manuscript")
    tx.add_argument("--section", action="append", default=[],
                    help="section name as `check` reports it (repeatable)")
    tx.set_defaults(func=cmd_text)
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
