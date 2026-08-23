#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One engine for every risk-of-bias / quality / certainty instrument.

    appraise.py --list
    appraise.py --route "randomised controlled trial"
    appraise.py --skeleton rob2
    appraise.py --skeleton robins-i --scope all
    appraise.py --verify draft.md --tool rob2
    appraise.py --rollup  draft.md --tool rob2
    appraise.py --counts

Three jobs, and the split matters
---------------------------------
**skeleton** prints every slot that must be filled. **verify** reads a finished
appraisal back and names what was left blank. **rollup** applies the instrument's
own published algorithm to the recorded answers and computes the domain and
overall judgements.

The characteristic failure of a 22- or 34-item instrument is not a wrong answer;
it is a silently missing one. A domain assessed on two of its four questions
still produces a confident-looking rating, and nothing in the output says which
question was never asked. So the model can be wrong about an answer; it should
not be able to be wrong about *whether it answered*.

And where the instrument publishes an algorithm — RoB 2, ROBINS-I, ROBINS-E,
AMSTAR 2, the Newcastle-Ottawa star count, GRADE's start-and-adjust — the domain
verdict is arithmetic, not judgement. Computing it here means the judgement can
be checked against the answers, and a rating that does not follow from them is
visible instead of plausible.

Item lists are PARSED FROM references/*.md, never duplicated in this file. A
second copy drifts from the reference the moment either is edited, and two
sources disagreeing silently is worse than having no script at all.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REF = Path(__file__).resolve().parent.parent / "skills" / "validator" / "references"

#: `**1.1 (all) — question**`, `**3c (D;E)** — question`, `**1.1 — question**`.
#: One pattern for every reference file: a second pattern is a second source of
#: truth about what an item looks like.
#: The id must contain a digit somewhere. Without that, any bold line of the
#: shape `**Note — something**` parses as an item and the instrument silently
#: grows slots the published tool does not have. The lookahead goes BEFORE the
#: first character, not after it: placed after, it demanded a digit in position
#: two, so AMSTAR 2's single-digit items 1-9 and ROBIS's phase-3 items 3A-3C
#: vanished — 7 of 16 and 21 of 24 parsed, and only the --counts check made that
#: visible.
ITEM_RE = re.compile(
    r"^\*\*(?P<id>(?=[\w.\-]*\d)[A-Za-z0-9][\w.\-]*)\s*"
    r"(?:\((?P<scope>[^)]*)\))?\s*"
    r"(?:\*\*)?\s*[—–-]\s*"
    r"(?P<text>.+?)\s*$")
DOMAIN_RE = re.compile(r"^##+\s*(?:Domain|Phase|Section|Item group)\s*(?P<num>[\w.]+)\s*[—–-]\s*(?P<name>.+?)\s*$", re.I)
META_RE = re.compile(r"^\s*(\w[\w\-]*)\s*:\s*(.+?)\s*$")


# --------------------------------------------------------------------------- model


class Instrument:
    def __init__(self, path: Path):
        self.path = path
        self.meta: dict[str, str] = {}
        self.items: list[dict] = []
        self.domains: dict[str, str] = {}
        self._parse()

    def _parse(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        block = re.search(r"<!--(.*?)-->", text, re.S)
        if block:
            for line in block.group(1).splitlines():
                m = META_RE.match(line)
                if m:
                    self.meta[m.group(1)] = m.group(2)
        domain = ""
        heading = ""
        for line in text.splitlines():
            d = DOMAIN_RE.match(line)
            if d:
                domain = d.group("num")
                self.domains[domain] = d.group("name")
                continue
            if line.startswith("##"):
                # A reference file may group its items under ordinary headings —
                # JBI's are one checklist per design, not "Domain 1". Remember the
                # heading so those items land in a named group instead of one
                # undifferentiated "Items" block.
                heading = re.sub(r"^#+\s*", "", line).split("—")[0].strip()
                domain = ""
            m = ITEM_RE.match(line)
            if m:
                text_ = m.group("text").rstrip("*").strip()
                key = domain or m.group("id").split(".")[0]
                if not domain and heading:
                    self.domains.setdefault(key, heading)
                self.items.append({
                    "id": m.group("id"),
                    "scope": (m.group("scope") or "all").strip(),
                    "text": text_,
                    "domain": key,
                })

    @property
    def key(self) -> str:
        return self.meta.get("tool", self.path.stem)

    @property
    def name(self) -> str:
        return self.meta.get("name", self.key)

    @property
    def answers(self) -> list[str]:
        return [a.strip() for a in self.meta.get("answers", "Yes|No").split("|")]

    @property
    def verdicts(self) -> list[str]:
        return [v.strip() for v in self.meta.get("verdicts", "Low|High|Unclear").split("|")]

    @staticmethod
    def tags(item: dict) -> set[str]:
        return {t.strip().lower() for t in re.split(r"[;,/]", item["scope"])}

    def scoped(self, scope: str) -> list[dict]:
        if scope in ("all", "", None):
            return list(self.items)
        keep = []
        for it in self.items:
            tags = self.tags(it)
            if "all" in tags or scope.lower() in tags:
                keep.append(it)
        return keep


def load_all() -> dict[str, Instrument]:
    if not REF.exists():
        sys.exit(f"nincs referencia könyvtár: {REF}")
    out: dict[str, Instrument] = {}
    for p in sorted(REF.glob("*.md")):
        inst = Instrument(p)
        if inst.items:
            out[inst.key] = inst
    return out


# --------------------------------------------------------------------------- router

#: design keyword -> (tool key, why). The router exists because picking the wrong
#: instrument is the most expensive mistake available here: an appraisal done with
#: the wrong tool is not a weak appraisal, it is an inapplicable one, and reviewers
#: notice. Ordered — the first match wins, so the specific patterns come first.
ROUTES: list[tuple[str, str, str]] = [
    (r"\b(prediction model|prognostic model|risk score|nomogram|machine learning model|"
     r"ai model|algorithm validation|diagnostic model)\b", "probast-ai",
     "prediction-model study — quality and risk of bias"),
    (r"\b(tripod|reporting completeness.*model)\b", "tripod-ai",
     "prediction-model REPORTING completeness"),
    (r"\b(diagnostic (test )?accuracy|sensitivity and specificity|index test|"
     r"reference standard|dta)\b", "quadas2",
     "diagnostic test accuracy study"),
    (r"\b(prognostic factor|prognostic marker|predictor of outcome)\b", "quips",
     "prognostic factor study"),
    (r"\b(umbrella review|overview of reviews|systematic review|meta-analys)\b", "amstar2",
     "systematic review — methodological quality"),
    (r"\b(risk of bias in.*review|robis)\b", "robis",
     "systematic review — risk of bias in the review process"),
    (r"\b(randomi[sz]ed|rct|randomi[sz]ed controlled trial|cluster.?randomi|crossover trial)\b",
     "rob2", "randomised trial"),
    (r"\b(non.?randomi[sz]ed (?:study|trial)|nrsi|quasi.?experimental|"
     r"interrupted time series|before.?after study)\b", "robins-i",
     "non-randomised study of an intervention"),
    (r"\b(exposure|environmental|occupational|nutritional epidemiolog|"
     r"observational study of an exposure)\b", "robins-e",
     "observational study of an exposure"),
    (r"\b(cohort study|case.?control study)\b", "nos",
     "cohort or case-control study (star system)"),
    (r"\b(cross.?sectional|case series|case report|prevalence study|qualitative study)\b",
     "jbi", "JBI checklist family — pick the design-specific list"),
    (r"\b(certainty of evidence|quality of evidence|summary of findings|grade)\b", "grade",
     "certainty of the body of evidence, per outcome"),
]


def route(query: str) -> list[tuple[str, str]]:
    hits = [(tool, why) for pattern, tool, why in ROUTES
            if re.search(pattern, query, re.I)]
    return hits


# --------------------------------------------------------------------------- output


def skeleton(inst: Instrument, scope: str) -> str:
    items = inst.scoped(scope)
    answers = " / ".join(inst.answers)
    L = [f"# {inst.name}", ""]
    if inst.meta.get("unit"):
        L += [f"**Assessed per {inst.meta['unit']}** — repeat the whole table for each.", ""]
    L += [f"{len(items)} slots to fill. Answer vocabulary: **{answers}**.",
          f"Domain verdicts: **{' / '.join(inst.verdicts)}**.", ""]
    if scope != "all":
        L += [f"Scope filter: `{scope}`.", ""]

    by_domain: dict[str, list[dict]] = {}
    for it in items:
        by_domain.setdefault(it["domain"], []).append(it)

    label = inst.meta.get("group_label", "Domain")
    for dom, rows in by_domain.items():
        title = inst.domains.get(dom, dom)
        L += [f"## {label} {dom} — {title}" if dom else "## Items", "",
              "| # | Signalling question | Answer | Evidence (quote or section) |",
              "|---|---|---|---|"]
        for it in rows:
            L.append(f"| {it['id']} | {it['text'][:76]} |  |  |")
        L += ["", f"**{label} {dom} judgement:** {' / '.join(inst.verdicts)} — one-sentence "
                  f"rationale.", ""]
    if inst.meta.get("applicability"):
        L += [f"**Applicability ({inst.meta['applicability']}):** "
              f"{' / '.join(inst.verdicts)} — against the stated review question.", ""]
    L += [f"**OVERALL:** {' / '.join(inst.verdicts)} — a paragraph of rationale.", "",
          f"<!-- {len(items)} slots; run --verify, then --rollup, before calling this done -->"]
    return "\n".join(L)


def _answer_tokens(inst: Instrument) -> list[str]:
    toks = set(inst.answers) | {"N/A", "NA", "Not applicable"}
    # Common shorthands, so an appraisal written as `PY` verifies like `Probably yes`.
    extra = {"Yes": ["Y"], "No": ["N"], "Probably yes": ["PY"], "Probably no": ["PN"],
             "No information": ["NI"], "Partial yes": ["PY"],
             "Some concerns": ["SC"], "Unclear": ["U"]}
    for k, vs in extra.items():
        if k in toks:
            toks.update(vs)
    return sorted(toks, key=len, reverse=True)


def read_answers(path: Path, inst: Instrument, scope: str) -> dict[str, str]:
    """{item id: verdict token}.

    Table rows are parsed as TABLE ROWS, not scanned with a regex over the whole
    line. RoB 2's own question texts contain the strings "N/PN/NI" and "Y/PY" —
    a line-wide search finds those before it reaches the answer column, so a
    correctly answered 2.7 read back as "No" and the rollup rated three domains
    high risk on a trial with no problems. The answer must come from the answer
    cell.
    """
    text = path.read_text(encoding="utf-8")
    toks = _answer_tokens(inst)
    tok_lookup = {t.lower(): t for t in toks}
    found: dict[str, str] = {}
    items = {it["id"]: it for it in inst.scoped(scope)}

    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not cells:
                continue
            iid = cells[0].strip("* ")
            if iid not in items or iid in found:
                continue
            for cell in cells[1:]:
                hit = tok_lookup.get(cell.lower())
                if hit:
                    found[iid] = hit
                    break
            continue

    # Prose appraisals (no table) still have to verify, so fall back to a
    # line-wide search for anything the table pass did not settle.
    escaped = [re.escape(t) for t in toks]
    for iid, it in items.items():
        if iid in found:
            continue
        pat = re.compile(
            rf"^(?![|\s]*\|).*?(?<![\w.]){re.escape(iid)}(?![\w.])"
            rf".*?\b({'|'.join(escaped)})\b", re.M | re.I)
        m = pat.search(text)
        if m:
            found[iid] = m.group(1)
    return found


def verify(path: Path, inst: Instrument, scope: str) -> int:
    items = inst.scoped(scope)
    found = read_answers(path, inst, scope)
    missing = [it["id"] for it in items if it["id"] not in found]
    print(f"  {len(found)}/{len(items)} answered  ({inst.name})")
    if missing:
        print(f"  UNANSWERED ({len(missing)}): {', '.join(missing)}")
        print("  An appraisal with unanswered slots is not finished. "
              f"'{inst.answers[-1]}' is an answer; silence is not.")
        return 1
    print("  complete")
    return 0


# --------------------------------------------------------------------------- rollups


def _norm(tok: str) -> str:
    t = tok.strip().lower()
    return {"y": "yes", "n": "no", "py": "probably yes", "pn": "probably no",
            "ni": "no information", "sc": "some concerns", "u": "unclear",
            "na": "n/a", "not applicable": "n/a"}.get(t, t)


def _yes_ish(tok: str) -> bool:
    return _norm(tok) in ("yes", "probably yes", "partial yes")


def _no_ish(tok: str) -> bool:
    return _norm(tok) in ("no", "probably no")


def _unknown(tok: str) -> bool:
    return _norm(tok) in ("no information", "unclear", "")


def rollup_signalling(inst: Instrument, answers: dict[str, str],
                      items: list[dict]) -> list[str]:
    """The shared shape of RoB 2 / ROBINS-I / ROBINS-E / QUADAS-2 domain logic.

    Deliberately conservative and deliberately NOT the official flowchart. The
    published algorithms branch on specific questions in ways that a generic
    engine cannot reproduce without hard-coding each one — and a generic engine
    that *claimed* to reproduce them would give a wrong verdict that looks
    official. So this reports what the answers force, names the questions that
    forced it, and leaves the final call to the assessor.
    """
    # Polarity is per item, not per instrument. RoB 2's 1.3, 4.1 and 4.2 and
    # QUADAS-2's "avoid a case-control design?" are worded so that YES is the
    # problem. Treating every "No" as bad rated a well-conducted trial as high
    # risk on domain 4 for correctly answering "No, the measurement method was
    # not inappropriate".
    # A third category besides normal and reverse: questions that only ROUTE.
    # RoB 2's 2.1 ("were participants aware of their assigned intervention?") is
    # Yes in every open-label trial ever run, and by itself means nothing — the
    # algorithm uses it to decide whether 2.3 is even asked. Counting it as a
    # problem rated every unblinded trial high risk. Router questions are listed
    # but do not drive the domain verdict.
    by_domain: dict[str, list[tuple[str, str, bool]]] = {}
    routers: dict[str, list[str]] = {}
    for it in items:
        if it["id"] not in answers:
            continue
        tags = inst.tags(it)
        if "router" in tags:
            routers.setdefault(it["domain"], []).append(it["id"])
            continue
        by_domain.setdefault(it["domain"], []).append(
            (it["id"], answers[it["id"]], "reverse" in tags))

    lines = []
    worst = "low"
    for dom, rows in by_domain.items():
        nos = [i for i, a, rev in rows
               if (_yes_ish(a) if rev else _no_ish(a))]
        unk = [i for i, a, rev in rows if _unknown(a)]
        if nos:
            verdict, why = "HIGH / SERIOUS", f"'No' or 'Probably no' at {', '.join(nos)}"
            worst = "high"
        elif unk:
            verdict, why = "SOME CONCERNS / UNCLEAR", f"no information at {', '.join(unk)}"
            worst = "some" if worst == "low" else worst
        else:
            verdict, why = "LOW", "no signalling question flags a problem"
        title = inst.domains.get(dom, dom)
        lines.append(f"  Domain {dom} ({title[:42]}): {verdict}  — {why}")
        if routers.get(dom):
            lines.append(f"  {'':<12}routing questions answered, not scored: "
                         f"{', '.join(routers[dom])}")
    lines.append("")
    lines.append({"low": "  Implied overall: LOW — but only if every domain is genuinely low.",
                  "some": "  Implied overall: SOME CONCERNS — driven by the unresolved domains above.",
                  "high": "  Implied overall: HIGH / SERIOUS — one domain at high risk sets the overall."
                  }[worst])
    lines.append("  This is what the recorded answers force. It is NOT the published "
                 "flowchart: the official algorithms branch on particular questions "
                 "(RoB 2 domain 2 on 2.6/2.7, ROBINS-I on the confounding domain). "
                 "Check the borderline domains against the source algorithm and say "
                 "so if you override this.")
    return lines


def rollup_amstar2(inst: Instrument, answers: dict[str, str],
                   items: list[dict]) -> list[str]:
    """AMSTAR 2's rating IS an algorithm, and this one is reproduced exactly.

    Critical items: 2, 4, 7, 9, 11, 13, 15. One critical flaw -> Low. More than
    one -> Critically low. No critical flaw, up to one non-critical weakness ->
    High. No critical flaw, more than one non-critical weakness -> Moderate.
    """
    critical = {c.strip() for c in inst.meta.get("critical", "").split(",") if c.strip()}
    crit_flaws, noncrit_flaws, unanswered = [], [], []
    for it in items:
        a = answers.get(it["id"])
        if a is None:
            unanswered.append(it["id"])
            continue
        if _yes_ish(a):
            if _norm(a) == "partial yes" and it["id"] in critical:
                # A "Partial Yes" on a critical item is a weakness, not a flaw.
                noncrit_flaws.append(it["id"])
            continue
        (crit_flaws if it["id"] in critical else noncrit_flaws).append(it["id"])

    if len(crit_flaws) > 1:
        rating = "CRITICALLY LOW"
    elif len(crit_flaws) == 1:
        rating = "LOW"
    elif len(noncrit_flaws) > 1:
        rating = "MODERATE"
    else:
        rating = "HIGH"

    L = [f"  Critical flaws ({len(crit_flaws)}): {', '.join(crit_flaws) or 'none'}",
         f"  Non-critical weaknesses ({len(noncrit_flaws)}): "
         f"{', '.join(noncrit_flaws) or 'none'}",
         "",
         f"  OVERALL CONFIDENCE IN THE RESULTS: {rating}"]
    if unanswered:
        L += ["", f"  {len(unanswered)} item(s) unanswered ({', '.join(unanswered)}) — "
                  "the rating above is provisional until they are filled."]
    L += ["", "  AMSTAR 2 rates CONFIDENCE IN THE RESULTS of the review, not the quality "
              "of the included studies and not the certainty of the evidence. Say that "
              "explicitly; readers conflate it with GRADE constantly."]
    return L


def rollup_nos(inst: Instrument, answers: dict[str, str],
               items: list[dict]) -> list[str]:
    """Newcastle-Ottawa: count the stars, and refuse to pretend the thresholds are official."""
    stars = 0
    per_domain: dict[str, int] = {}
    for it in items:
        a = answers.get(it["id"])
        if a is None:
            continue
        m = re.search(r"(\d+)\s*star", it["scope"], re.I)
        max_stars = int(m.group(1)) if m else 1
        got = 0
        if _yes_ish(a):
            got = max_stars if _norm(a) == "yes" else 1
        stars += got
        per_domain[it["domain"]] = per_domain.get(it["domain"], 0) + got
    total_possible = 0
    for it in items:
        m = re.search(r"(\d+)\s*star", it["scope"], re.I)
        total_possible += int(m.group(1)) if m else 1
    L = ["  Stars by domain: " + ", ".join(f"{k}={v}" for k, v in per_domain.items()),
         f"  TOTAL: {stars}/{total_possible} stars", "",
         "  There is NO official threshold. The 7-9 = good / 4-6 = fair / 0-3 = poor "
         "cut-offs come from an AHRQ conversion that the scale's authors never "
         "published, and summing ordinal stars across incomparable domains is the "
         "documented weakness of this instrument. Report the per-domain stars, state "
         "whichever threshold you use and where it came from, and prefer ROBINS-I or "
         "ROBINS-E when the review will be scrutinised."]
    return L


def rollup_grade(inst: Instrument, answers: dict[str, str],
                 items: list[dict]) -> list[str]:
    """Start high or low by design, subtract for the five, add for the three."""
    start = "high"
    downs = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    ups = 0
    detail = []
    for it in items:
        a = answers.get(it["id"])
        if a is None:
            continue
        n = _norm(a)
        if it["domain"] == "0":
            if n.startswith("low") or "observational" in n or "nrsi" in n:
                start = "low"
            continue
        if it["domain"] in downs:
            # "not serious" CONTAINS "serious". A substring test downgraded every
            # domain the assessor had explicitly cleared, and turned a High body
            # of evidence into Very low without a single serious concern in it.
            if n.startswith("very serious"):
                step = 2
            elif n.startswith("serious"):
                step = 1
            else:
                step = 0
            downs[it["domain"]] = step
            if step:
                detail.append(f"-{step} {inst.domains.get(it['domain'], it['domain'])[:34]}")
        elif it["domain"] in ("6", "7", "8") and _yes_ish(a) and n != "no":
            ups += 1
            detail.append(f"+1 {inst.domains.get(it['domain'], it['domain'])[:34]}")

    levels = ["very low", "low", "moderate", "high"]
    idx = levels.index(start)
    idx -= sum(downs.values())
    if sum(downs.values()) == 0:
        idx += ups
    idx = max(0, min(3, idx))
    L = [f"  Start: {start.upper()} ({'RCT' if start == 'high' else 'observational'})",
         f"  Adjustments: {', '.join(detail) or 'none'}",
         "",
         f"  CERTAINTY: {levels[idx].upper()}"]
    if ups and sum(downs.values()):
        L += ["", "  Upgrade factors were recorded alongside downgrades and were NOT "
                  "applied: GRADE only upgrades a body of evidence that has not been "
                  "downgraded. Resolve the downgrades first."]
    L += ["", "  Certainty is rated PER OUTCOME, never per study and never per review. "
              "If more than one outcome matters, this table has to be repeated for each, "
              "and the Summary of Findings reports them separately."]
    return L


ROLLUPS = {
    "amstar2": rollup_amstar2,
    "nos": rollup_nos,
    "grade": rollup_grade,
}


def rollup(path: Path, inst: Instrument, scope: str) -> int:
    answers = read_answers(path, inst, scope)
    if not answers:
        print("  Egyetlen kitöltött tétel sincs a fájlban. A --rollup a rögzített "
              "válaszokból számol; előbb töltsd ki a --skeleton táblát.")
        return 1
    print(f"ROLLUP — {inst.name}   ({len(answers)}/{len(inst.scoped(scope))} answered)")
    print("-" * 70)
    items = inst.scoped(scope)
    fn = ROLLUPS.get(inst.key)
    lines = fn(inst, answers, items) if fn else rollup_signalling(inst, answers, items)
    print("\n".join(lines))
    return 0


# --------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--route", metavar="DESIGN")
    ap.add_argument("--skeleton", metavar="TOOL")
    ap.add_argument("--verify", type=Path)
    ap.add_argument("--rollup", type=Path)
    ap.add_argument("--tool")
    ap.add_argument("--scope", default="all")
    ap.add_argument("--counts", action="store_true")
    args = ap.parse_args(argv)

    tools = load_all()
    if not tools:
        sys.exit(f"nincs egyetlen műszer sem itt: {REF}")

    if args.list:
        print("Elérhető műszerek:\n")
        for key, inst in sorted(tools.items()):
            scopes = inst.meta.get("scopes", "")
            print(f"  {key:<12} {inst.name}")
            if inst.meta.get("engine"):
                print(f"  {'':<12} saját motor: scripts/{inst.meta['engine']}")
            print(f"  {'':<12} {len(inst.items)} tétel · "
                  f"válaszok: {' / '.join(inst.answers)}"
                  + (f" · scope: {scopes}" if scopes else ""))
            if inst.meta.get("use_for"):
                print(f"  {'':<12} → {inst.meta['use_for']}")
            print()
        print("Melyiket? →  appraise.py --route \"<vizsgálati elrendezés>\"")
        return 0

    if args.route:
        hits = route(args.route)
        if not hits:
            print(f"Nem ismertem fel elrendezést ebben: \"{args.route}\"")
            print("A felismert kulcsszavakat lásd: --list, és a SKILL.md "
                  "\"Choosing the instrument\" táblája.")
            return 1
        print(f"\"{args.route}\" →")
        for tool, why in hits:
            inst = tools.get(tool)
            print(f"  {tool:<12} {inst.name if inst else '(hiányzó referencia)'}")
            print(f"  {'':<12} {why}")
        if len(hits) > 1:
            print("\nTöbb műszer illik rá. Ez normális: egy szisztematikus review-t "
                  "AMSTAR 2-vel ÉS ROBIS-szal is lehet nézni, és egy prediktív modell "
                  "vizsgálatához PROBAST (minőség) és TRIPOD (jelentés) is tartozik. "
                  "Mondd meg, melyik kérdésre válaszolsz, és futtasd azt.")
        return 0

    def _redirect(inst: Instrument, action: str, scope: str) -> int:
        """Some instruments cannot be expressed by the generic model. Say so.

        PROBAST+AI answers domains 1-3 TWICE — once judging development quality,
        once judging evaluation risk of bias — and the generic parser has one
        slot per item id. Letting it print a 27-slot skeleton for a 34-slot
        instrument would be exactly the silent under-count this whole script
        exists to prevent, so it refuses and points at the engine that handles it.
        """
        tool = {"probast-ai": "probast", "tripod-ai": "tripod"}.get(inst.key, inst.key)
        print(f"{inst.name} saját motorral fut ({inst.meta['engine']}).")
        print(f"  python3 scripts/{inst.meta['engine']} --{action} "
              f"{'probast' if action == 'skeleton' else '<file> --tool ' + tool}"
              f" --scope {scope if scope != 'all' else 'both'}")
        if inst.meta.get("note"):
            print(f"  Miért: {inst.meta['note']}")
        return 2

    if args.skeleton:
        inst = tools.get(args.skeleton)
        if not inst:
            sys.exit(f"ismeretlen műszer: {args.skeleton}\n  van: {', '.join(sorted(tools))}")
        if inst.meta.get("engine"):
            return _redirect(inst, "skeleton", args.scope)
        print(skeleton(inst, args.scope))
        return 0

    if args.verify or args.rollup:
        if not args.tool:
            sys.exit("--verify / --rollup mellé --tool kell")
        inst = tools.get(args.tool)
        if not inst:
            sys.exit(f"ismeretlen műszer: {args.tool}\n  van: {', '.join(sorted(tools))}")
        if inst.meta.get("engine"):
            return _redirect(inst, "verify" if args.verify else "verify", args.scope)
        path = args.verify or args.rollup
        if not path.exists():
            sys.exit(f"nincs ilyen fájl: {path}")
        return verify(path, inst, args.scope) if args.verify else rollup(path, inst, args.scope)

    if args.counts:
        bad = 0
        for key, inst in sorted(tools.items()):
            if inst.meta.get("engine"):
                print(f"  {key:<12} {'—':>3}        saját motor: "
                      f"{inst.meta['engine']} --counts")
                continue
            expected = inst.meta.get("published_items", "")
            n = len(inst.items)
            note = ""
            if expected:
                try:
                    exp = int(expected)
                    if exp != n:
                        note = f"  MISMATCH — a publikált eszköz {exp} tétel"
                        bad += 1
                    else:
                        note = "  ok"
                except ValueError:
                    note = f"  (várt: {expected})"
            print(f"  {key:<12} {n:>3} tétel{note}")
        if bad:
            print("\n  A referenciafájl és a publikált műszer nem egyezik. Egy hiányzó "
                  "tétel némán csökkenti az értékelést; javítsd, mielőtt használod.")
        return 1 if bad else 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
