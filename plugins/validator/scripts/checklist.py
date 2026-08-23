#!/usr/bin/env python3
"""Emit the appraisal skeleton, and check that nothing was left unanswered.

Why a script for a prose checklist
----------------------------------
PROBAST+AI is 34 assessment slots (16 development + 18 evaluation) and
TRIPOD+AI is 27 items across 52 subitems. The characteristic failure of a
checklist that long is not a wrong answer — it is a silently missing one. A
domain quietly assessed on two of its four questions still produces a
confident-looking judgment, and nothing in the output says which question was
never asked.

So: `--skeleton` prints every slot that must be filled, and `--verify` reads a
finished appraisal back and names what is missing. The model can be wrong about
an answer; it should not be able to be wrong about whether it answered.

The item list is PARSED FROM references/*.md, never duplicated here. A second
copy would drift from the reference the moment either is edited, and the two
disagreeing silently is worse than having no script at all.

  checklist.py --skeleton probast --scope development
  checklist.py --skeleton probast --scope both        # all 34 slots
  checklist.py --skeleton tripod  --scope both
  checklist.py --verify appraisal.md --tool probast --scope both
  checklist.py --counts                               # sanity-check the references

Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REF = Path(__file__).resolve().parent.parent / "skills" / "validator" / "references"

DOMAINS = {
    "1": "Participants & data sources",
    "2": "Predictors",
    "3": "Outcome",
    "4": "Analysis",
}


def _read(name: str) -> str:
    p = REF / name
    if not p.exists():
        sys.exit(f"missing reference file: {p}")
    return p.read_text(encoding="utf-8")


def probast_items() -> dict[str, list[tuple[str, str]]]:
    """{'development': [(id, title)], 'evaluation': [...]}.

    Domains 1-3 are the SAME questions asked twice — once judging development
    quality, once judging evaluation risk of bias. That is why 3+4+4 questions
    plus 5 development and 7 evaluation analysis questions come to 16 and 18,
    not 23. Collapsing them into one pass is the most likely way to under-count
    an appraisal of a study that does both.
    """
    text = _read("probast-ai.md")
    shared: list[tuple[str, str]] = []
    dev: list[tuple[str, str]] = []
    ev: list[tuple[str, str]] = []
    bucket = shared
    for line in text.splitlines():
        h = re.match(r"^###\s+Domain 4\s+—\s+(Development|Evaluation)", line, re.I)
        if h:
            bucket = dev if h.group(1).lower() == "development" else ev
            continue
        m = re.match(r"^\*\*([1-4]\.\d{1,2})\s*[—–-]\s*(.+?)\*\*", line)
        if m:
            bucket.append((m.group(1), m.group(2).strip().rstrip("?") + "?"))
    return {"development": shared + dev, "evaluation": shared + ev}


def tripod_items() -> list[tuple[str, str, str]]:
    """[(id, applies_to, title)] — applies_to is D, E or D;E."""
    text = _read("tripod-ai.md")
    out: list[tuple[str, str, str]] = []
    # The tag lives INSIDE the bold, in parentheses: **3c (D;E)** — text.
    # An earlier pattern looked for it after the title in brackets and matched
    # nothing at all, which --counts caught immediately; a checklist script that
    # silently finds zero items is worse than no script.
    for line in text.splitlines():
        m = re.match(r"^\*\*(\d{1,2}[a-z]?)\s*\((D;E|D|E)\)\*\*\s*[—–-]\s*(.+)", line)
        if m:
            title = re.sub(r"\*.*", "", m.group(3)).strip().rstrip(".")
            out.append((m.group(1), m.group(2), title))
    return out


# --------------------------------------------------------------------------- output

def skeleton_probast(scope: str) -> str:
    items = probast_items()
    passes = (["development", "evaluation"] if scope == "both" else [scope])
    L: list[str] = []
    total = 0
    for p in passes:
        head = ("Quality (development)" if p == "development"
                else "Risk of bias (evaluation)")
        L += [f"### {head} — {len(items[p])} signalling questions", "",
              "| SQ | Question | Answer | Evidence (quote or section) |",
              "|---|---|---|---|"]
        for qid, title in items[p]:
            L.append(f"| {qid} | {title[:64]} |  |  |")
        total += len(items[p])
        L += ["", f"**Domain judgments ({p}):** 1 · 2 · 3 · 4 — Low/High/Unclear "
                  f"+ one-sentence rationale each", ""]
    L += ["**Applicability (domains 1-3, against the stated PICOTS):** "
          "Low/High/Unclear", "",
          "**Overall:** quality and/or risk of bias, plus applicability — "
          "each Low/High/Unclear with a paragraph.", "",
          f"<!-- {total} slots to fill; run --verify before you call this done -->"]
    return "\n".join(L)


def skeleton_tripod(scope: str) -> str:
    items = tripod_items()
    keep = [i for i in items
            if scope == "both" or i[1] == "D;E"
            or (scope == "development" and "D" in i[1])
            or (scope == "evaluation" and "E" in i[1])]
    L = [f"### TRIPOD+AI reporting check — {len(keep)} items in scope", "",
         "| Item | D/E | What it asks | Status | Where / what to add |",
         "|---|---|---|---|---|"]
    for iid, ap, title in keep:
        L.append(f"| {iid} | {ap} | {title[:52]} |  |  |")
    L += ["", "Status is Present / Partial / Missing. Close with a prioritised "
              "gap list, weighting open science (18a-f) and fairness (item 14).",
          "", "This checks REPORTING COMPLETENESS, not whether the methods were "
              "sound — say so explicitly.",
          "", f"<!-- {len(keep)} items; run --verify before you call this done -->"]
    return "\n".join(L)


def verify(path: Path, tool: str, scope: str) -> int:
    text = path.read_text(encoding="utf-8")
    if tool == "probast":
        items = probast_items()
        passes = ["development", "evaluation"] if scope == "both" else [scope]
        missing: list[str] = []
        for p in passes:
            for qid, _ in items[p]:
                # An id is "answered" only if a verdict token shares its line.
                pat = re.compile(
                    rf"^.*\b{re.escape(qid)}\b.*?\b"
                    rf"(Yes|Probably yes|Probably no|No information|NI|PY|PN|N/A|No)\b",
                    re.M | re.I)
                if not pat.search(text):
                    missing.append(f"{p}/{qid}")
        expected = sum(len(items[p]) for p in passes)
    else:
        keep = [i for i in tripod_items()
                if scope == "both" or scope[0].upper() in i[1]]
        missing = [i[0] for i in keep if not re.search(
            rf"^.*\b{re.escape(i[0])}\b.*?\b(Present|Partial|Missing|N/A)\b",
            text, re.M | re.I)]
        expected = len(keep)

    done = expected - len(missing)
    print(f"  {done}/{expected} answered")
    if missing:
        print(f"  UNANSWERED ({len(missing)}): {', '.join(missing)}")
        print("  An appraisal with unanswered slots is not finished. 'No "
              "information' is a valid answer; silence is not.")
        return 1
    print("  complete")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skeleton", choices=("probast", "tripod"))
    ap.add_argument("--verify", type=Path)
    ap.add_argument("--tool", choices=("probast", "tripod"), default="probast")
    ap.add_argument("--scope", choices=("development", "evaluation", "both"),
                    default="both")
    ap.add_argument("--counts", action="store_true")
    args = ap.parse_args()

    if args.counts:
        p = probast_items()
        t = tripod_items()
        print(f"  PROBAST+AI development : {len(p['development'])}  (paper says 16)")
        print(f"  PROBAST+AI evaluation  : {len(p['evaluation'])}  (paper says 18)")
        print(f"  TRIPOD+AI items parsed : {len(t)}")
        bad = (len(p["development"]) != 16) or (len(p["evaluation"]) != 18)
        print("  MISMATCH — the reference file and the published tool disagree"
              if bad else "  matches the published counts")
        return 1 if bad else 0

    if args.skeleton == "probast":
        print(skeleton_probast(args.scope))
        return 0
    if args.skeleton == "tripod":
        print(skeleton_tripod(args.scope))
        return 0
    if args.verify:
        return verify(args.verify, args.tool, args.scope)

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
