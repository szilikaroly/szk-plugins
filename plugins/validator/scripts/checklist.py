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


# --------------------------------------------------------------------------- reading

PROBAST_TOKENS = {"yes", "probably yes", "probably no", "no", "no information", "ni", "py",
                  "pn", "y", "n", "n/a", "na", "not applicable"}
TRIPOD_TOKENS = {"present", "partial", "missing", "n/a", "na", "not applicable"}

#: "If Y/PY to 4.1:" — a question's conditional prefix is not its answer.
_COND_RE = re.compile(r"\bif\s+(?:(?:Y|PY|N|PN|NI|NA)/)*(?:Y|PY|N|PN|NI|NA)\s+to\b[^:?]*[:?]",
                      re.I)
_SEP_RE = re.compile(r"\s[—–]\s|\s-\s|:\s|\s=>?\s|\s->\s")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_sep(cells: list[str]) -> bool:
    return any(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c)


def _clean(cell: str) -> str:
    c = cell.strip().strip("*_`").strip()
    return "" if c in ("—", "–", "-") else c


def _col(header: list[str] | None, names: tuple[str, ...]) -> int | None:
    for i, h in enumerate(header or []):
        if any(h.strip("*_ ").lower().startswith(n) for n in names):
            return i
    return None


def _prose_answer(rest: str, title: str, tokens: set[str]) -> str | None:
    """The answer in a prose line, after the item's own title and any "If …:" clause
    are cut out. Only an emphasised answer, the text after the last separator,
    or a line that opens with the answer counts — "11 How missing data were
    handled …" is a title that contains a status word, not a status."""
    r = rest
    for t in (title, title[:64], title[:52]):
        t = t.strip()
        if len(t) >= 12 and t.lower() in r.lower():
            j = r.lower().index(t.lower())
            r = r[:j] + " " + r[j + len(t):]
            break
    r = _COND_RE.sub(" ", r)
    alts = "|".join(re.escape(x) for x in sorted(tokens, key=len, reverse=True))
    tok_re = re.compile(rf"(?<![\w/])({alts})(?![\w/])", re.I)
    for b in re.findall(r"\*\*(.+?)\*\*", r):
        if _clean(b).lower() in tokens:
            return _clean(b).lower()
    parts = _SEP_RE.split(r)
    if len(parts) > 1:
        m = tok_re.search(parts[-1])
        if m:
            return m.group(1).lower()
    m = re.match(rf"\s*({alts})(?![\w/])", r, re.I)
    return m.group(1).lower() if m else None


def read_by_pass(text: str, tokens: set[str], answer_cols: tuple[str, ...],
                 titles: dict[str, str]) -> dict[str | None, dict[str, str]]:
    """{pass: {id: answer}} — pass is 'development', 'evaluation' or None.

    The pass is the one named by the nearest heading above (a PROBAST+AI
    skeleton prints "### Quality (development)" and "### Risk of bias
    (evaluation)"). In 1.x the whole file was searched for each id, so the
    development table's 1.1-4.5 also answered the evaluation pass's 1.1-4.5:
    filling one pass verified 32 of 34.

    In a table the answer is read from the column the header names, and nowhere
    else; a table without a header falls back to the first cell that is exactly
    an answer. In 1.x a line-wide search counted the word "Missing" in TRIPOD
    item 11's title ("How missing data were handled") as its status, and a "no"
    in an evidence note ("no mention in methods") as a PROBAST answer.
    Outside tables, a line counts only when it starts with the item id.
    """
    out: dict[str | None, dict[str, str]] = {}
    lines = text.splitlines()
    cur: str | None = None
    header: list[str] | None = None
    for i, line in enumerate(lines):
        s = line.strip()
        h = re.match(r"^#{1,6}\s+(.*)$", s)
        if h:
            low = h.group(1).lower()
            if "development" in low:
                cur = "development"
            elif "evaluation" in low:
                cur = "evaluation"
            header = None
            continue
        if s.startswith("|"):
            cells = _cells(s)
            if _is_sep(cells):
                continue
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt.startswith("|") and _is_sep(_cells(nxt)):
                header = [c.lower() for c in cells]
                continue
            iid = cells[0].strip("*_` ") if cells else ""
            col = _col(header, answer_cols)
            cand = ([cells[col]] if col < len(cells) else []) if col is not None else cells[1:]
            for c in cand:
                tok = _clean(c).lower()
                if tok in tokens:
                    out.setdefault(cur, {}).setdefault(iid, tok)
                    break
            continue
        header = None
        m = re.match(r"^\s*(?:[-*+]\s+)?(?:\*\*)?([0-9]{1,2}(?:\.[0-9]{1,2}|[a-z])?)"
                     r"(?:\*\*|[.):])*\s+(.*)$", s, re.I)
        if m and m.group(1) in titles:
            tok = _prose_answer(m.group(2), titles[m.group(1)], tokens)
            if tok:
                out.setdefault(cur, {}).setdefault(m.group(1), tok)
    return out


def verify(path: Path, tool: str, scope: str) -> int:
    text = path.read_text(encoding="utf-8")
    note = ""
    if tool == "probast":
        items = probast_items()
        passes = ["development", "evaluation"] if scope == "both" else [scope]
        titles = {qid: title for p in items.values() for qid, title in p}
        by_pass = read_by_pass(text, PROBAST_TOKENS, ("answer", "response"), titles)
        named = [p for p in by_pass if p]
        missing: list[str] = []
        for p in passes:
            # A single-pass file needs no pass heading; a two-pass file does,
            # because otherwise nothing says which pass an answer belongs to.
            pool = by_pass.get(p, {})
            if scope != "both" and not named:
                pool = by_pass.get(None, {})
            for qid, _ in items[p]:
                if qid not in pool:
                    missing.append(f"{p}/{qid}")
        if scope == "both" and by_pass.get(None):
            note = (f"  {len(by_pass[None])} answer(s) sit outside a '(development)' / "
                    "'(evaluation)' section and were not counted: in a two-pass appraisal "
                    "every answer has to be under its pass's heading.")
        expected = sum(len(items[p]) for p in passes)
    else:
        keep = [i for i in tripod_items()
                if scope == "both" or scope[0].upper() in i[1]]
        titles = {i[0]: i[2] for i in keep}
        by_pass = read_by_pass(text, TRIPOD_TOKENS, ("status",), titles)
        pool: dict[str, str] = {}
        for answers in by_pass.values():
            for k, v in answers.items():
                pool.setdefault(k, v)
        missing = [i[0] for i in keep if i[0] not in pool]
        expected = len(keep)

    done = expected - len(missing)
    print(f"  {done}/{expected} answered")
    if note:
        print(note)
    if missing:
        print(f"  UNANSWERED ({len(missing)}): {', '.join(missing)}")
        print("  An appraisal with unanswered slots is not finished. 'No "
              "information' is a valid answer; silence is not.")
        return 1
    print("  complete")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skeleton", choices=("probast", "tripod"))
    ap.add_argument("--verify", type=Path)
    ap.add_argument("--tool", choices=("probast", "tripod"), default="probast")
    ap.add_argument("--scope", choices=("development", "evaluation", "both"),
                    default="both")
    ap.add_argument("--counts", action="store_true")
    args = ap.parse_args(argv)

    if args.counts:
        p = probast_items()
        t = tripod_items()
        print(f"  PROBAST+AI development : {len(p['development'])}  (paper says 16)")
        print(f"  PROBAST+AI evaluation  : {len(p['evaluation'])}  (paper says 18)")
        print(f"  TRIPOD+AI items parsed : {len(t)}  (paper says 52)")
        bad = (len(p["development"]) != 16) or (len(p["evaluation"]) != 18) \
            or (len(t) != 52)
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
