#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self test for the appraisal engine. Offline, deterministic. Exit 0 = pass.

Every assertion below corresponds to a bug that actually occurred while this
engine was being built. They are not illustrative: each one, if it regresses,
produces an appraisal that looks finished and is wrong.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appraise as A  # noqa: E402


def _ok(label: str, cond: bool) -> bool:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    return bool(cond)


def _draft(inst: A.Instrument, answers: dict[str, str], scope: str = "all") -> Path:
    """Render a filled skeleton the way an assessor would hand one back."""
    rows = ["| # | Q | Answer | Evidence |", "|---|---|---|---|"]
    for it in inst.scoped(scope):
        rows.append(f"| {it['id']} | {it['text'][:50]} | "
                    f"{answers.get(it['id'], '')} | p.1 |")
    p = Path(tempfile.mkdtemp()) / "draft.md"
    p.write_text("\n".join(rows), encoding="utf-8")
    return p


def run() -> bool:
    ok = True
    tools = A.load_all()

    print("\n[parsing]")
    ok &= _ok(f"12 instruments loaded (got {len(tools)})", len(tools) == 12)

    # --- the id regex. The lookahead was placed AFTER the first character, so it
    # demanded a digit in position two: AMSTAR 2's items 1-9 and ROBIS's 3A-3C
    # silently vanished (7 of 16, 21 of 24 parsed) and only --counts caught it.
    ok &= _ok("AMSTAR 2 parses all 16 items, incl. single-digit 1-9",
              len(tools["amstar2"].items) == 16)
    ok &= _ok("ROBIS parses phase-3 items 3A-3C",
              {"3A", "3B", "3C"} <= {i["id"] for i in tools["robis"].items})
    ok &= _ok("RoB 2 parses 22 signalling questions",
              len(tools["rob2"].items) == 22)

    # --- prose must not become items. Any bold `**Note — text**` line would.
    ok &= _ok("no instrument parsed an id without a digit",
              all(any(c.isdigit() for c in i["id"])
                  for inst in tools.values() for i in inst.items))

    print("\n[scope filtering]")
    nos = tools["nos"]
    ok &= _ok("NOS cohort scope = 8 items (not both checklists)",
              len(nos.scoped("cohort")) == 8)
    ok &= _ok("NOS case-control scope = 8 items",
              len(nos.scoped("case-control")) == 8)
    jbi = tools["jbi"]
    ok &= _ok("JBI case-report scope = 8 items",
              len(jbi.scoped("case-report")) == 8)

    print("\n[answer extraction]")
    # --- RoB 2's own question texts contain "N/PN/NI" and "Y/PY". A line-wide
    # regex found those before the answer column, so a correctly answered 2.7
    # read back as "No" and three domains were rated high risk on a clean trial.
    rob2 = tools["rob2"]
    clean = {"1.1": "Yes", "1.2": "Yes", "1.3": "No",
             "2.1": "Yes", "2.2": "Yes", "2.3": "No", "2.4": "N/A", "2.5": "N/A",
             "2.6": "Yes", "2.7": "N/A",
             "3.1": "Yes", "3.2": "N/A", "3.3": "N/A", "3.4": "N/A",
             "4.1": "No", "4.2": "No", "4.3": "Yes", "4.4": "Probably no", "4.5": "No",
             "5.1": "Yes", "5.2": "No", "5.3": "No"}
    d = _draft(rob2, clean, "assignment")
    got = A.read_answers(d, rob2, "assignment")
    ok &= _ok(f"2.7 reads 'N/A' from the answer cell, not 'N' from the question "
              f"text (got {got.get('2.7')!r})", got.get("2.7") == "N/A")
    ok &= _ok("4.4 reads 'Probably no', not 'No' (longest token wins)",
              got.get("4.4") == "Probably no")
    ok &= _ok(f"all 22 answers extracted (got {len(got)})", len(got) == 22)

    print("\n[polarity]")
    lines = "\n".join(A.rollup_signalling(rob2, got, rob2.scoped("assignment")))
    # 1.3 answered "No" is GOOD (reverse); 4.1/4.2 "No" is GOOD (reverse);
    # 2.1/2.2 "Yes" is normal for an open-label trial (router).
    ok &= _ok("a clean open-label trial is not rated high risk anywhere",
              "HIGH / SERIOUS" not in lines)
    ok &= _ok("domain 1 low despite 1.3='No' (reverse-polarity item)",
              "Domain 1" in lines and "Domain 1 (Randomisation process): LOW" in lines)
    ok &= _ok("router questions listed but not scored",
              "routing questions answered, not scored: 2.1, 2.2, 2.3, 2.4" in lines)

    dirty = dict(clean, **{"1.2": "No"})
    lines2 = "\n".join(A.rollup_signalling(rob2, dirty, rob2.scoped("assignment")))
    ok &= _ok("unconcealed allocation (1.2='No') does raise domain 1",
              "Domain 1 (Randomisation process): HIGH / SERIOUS" in lines2)

    reverse_hit = dict(clean, **{"5.2": "Yes"})
    lines3 = "\n".join(A.rollup_signalling(rob2, reverse_hit, rob2.scoped("assignment")))
    ok &= _ok("selective reporting (5.2='Yes', reverse) raises domain 5",
              "Domain 5" in lines3 and "HIGH / SERIOUS" in lines3)

    print("\n[AMSTAR 2 algorithm]")
    am = tools["amstar2"]
    def amstar(ans):
        return "\n".join(A.rollup_amstar2(am, ans, am.items))
    all_yes = {i["id"]: "Yes" for i in am.items}
    ok &= _ok("no flaws -> High", "OVERALL CONFIDENCE IN THE RESULTS: HIGH"
              in amstar(all_yes))
    ok &= _ok("one non-critical flaw (10) -> still High",
              "RESULTS: HIGH" in amstar(dict(all_yes, **{"10": "No"})))
    ok &= _ok("two non-critical flaws (3,10) -> Moderate",
              "RESULTS: MODERATE" in amstar(dict(all_yes, **{"3": "No", "10": "No"})))
    ok &= _ok("one critical flaw (7) -> Low",
              "RESULTS: LOW" in amstar(dict(all_yes, **{"7": "No"})))
    ok &= _ok("two critical flaws (7,15) -> Critically low",
              "RESULTS: CRITICALLY LOW"
              in amstar(dict(all_yes, **{"7": "No", "15": "No"})))
    ok &= _ok("Partial yes on a critical item counts as a weakness, not a flaw",
              "RESULTS: HIGH" in amstar(dict(all_yes, **{"2": "Partial yes"})))

    print("\n[Newcastle-Ottawa stars]")
    ns = tools["nos"]
    cohort_items = ns.scoped("cohort")
    perfect = {i["id"]: "Yes" for i in cohort_items}
    out = "\n".join(A.rollup_nos(ns, perfect, cohort_items))
    # The denominator summed BOTH checklists before the rollups were scoped:
    # a cohort assessment reported "9/18 stars".
    ok &= _ok(f"cohort denominator is 9, not 18 ({[l for l in out.splitlines() if 'TOTAL' in l]})",
              "TOTAL: 9/9 stars" in out)
    two_star = "\n".join(A.rollup_nos(ns, dict(perfect, **{"C1": "Partial yes"}),
                                      cohort_items))
    ok &= _ok("comparability 'Partial yes' scores 1 of its 2 stars",
              "TOTAL: 8/9 stars" in two_star)
    ok &= _ok("no threshold is asserted", "NO official threshold" in out)

    print("\n[GRADE arithmetic]")
    gr = tools["grade"]
    def grade(ans):
        return "\n".join(A.rollup_grade(gr, ans, gr.items))
    base = {"0.1": "High", "1.1": "Not serious", "2.1": "Not serious",
            "3.1": "Not serious", "4.1": "Not serious", "5.1": "Undetected",
            "6.1": "No", "7.1": "No", "8.1": "No"}
    # "not serious" CONTAINS "serious" — a substring test downgraded every domain
    # the assessor had explicitly cleared, turning High into Very low.
    ok &= _ok("all-clear RCT body stays High", "CERTAINTY: HIGH" in grade(base))
    ok &= _ok("one serious domain -> Moderate",
              "CERTAINTY: MODERATE" in grade(dict(base, **{"1.1": "Serious"})))
    ok &= _ok("one very serious domain -> Low",
              "CERTAINTY: LOW" in grade(dict(base, **{"1.1": "Very serious"})))
    ok &= _ok("two serious domains -> Low",
              "CERTAINTY: LOW" in grade(dict(base, **{"1.1": "Serious",
                                                      "4.1": "Serious"})))
    obs = dict(base, **{"0.1": "Low"})
    ok &= _ok("observational body starts Low", "CERTAINTY: LOW" in grade(obs))
    ok &= _ok("large effect upgrades an undowngraded observational body",
              "CERTAINTY: MODERATE" in grade(dict(obs, **{"6.1": "Yes"})))
    both = grade(dict(base, **{"1.1": "Serious", "6.1": "Yes"}))
    ok &= _ok("upgrade refused alongside a downgrade, and said so",
              "were NOT" in both and "CERTAINTY: MODERATE" in both)
    ok &= _ok("floor at Very low",
              "CERTAINTY: VERY LOW" in grade(dict(base, **{
                  "1.1": "Very serious", "2.1": "Very serious",
                  "3.1": "Very serious"})))

    print("\n[verify]")
    partial = {k: v for k, v in list(clean.items())[:10]}
    dp = _draft(rob2, partial, "assignment")
    rc = A.verify(dp, rob2, "assignment")
    ok &= _ok("an incomplete appraisal exits non-zero", rc == 1)
    ok &= _ok("a complete appraisal exits zero",
              A.verify(d, rob2, "assignment") == 0)

    print("\n[routing]")
    ok &= _ok("randomised trial -> rob2",
              "rob2" in [t for t, _ in A.route("a randomised controlled trial")])
    ok &= _ok("exposure cohort -> robins-e",
              "robins-e" in [t for t, _ in A.route("occupational exposure cohort")])
    ok &= _ok("diagnostic accuracy -> quadas2",
              "quadas2" in [t for t, _ in A.route("diagnostic test accuracy study")])
    ok &= _ok("prediction model -> probast-ai",
              "probast-ai" in [t for t, _ in A.route("a prognostic model for sepsis")])
    ok &= _ok("nonsense routes to nothing", A.route("banana") == [])

    print("\n[dual-engine instruments]")
    ok &= _ok("PROBAST+AI is flagged as running its own engine",
              tools["probast-ai"].meta.get("engine") == "checklist.py")
    ok &= _ok("TRIPOD+AI likewise",
              tools["tripod-ai"].meta.get("engine") == "checklist.py")

    print(f"\n{'ALL PASSED' if ok else 'FAILURES PRESENT'}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
