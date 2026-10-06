#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self test for the appraisal engine. Offline, deterministic. Exit 0 = pass.

Every assertion below corresponds to a bug that actually occurred while this
engine was being built. They are not illustrative: each one, if it regresses,
produces an appraisal that looks finished and is wrong.
"""
from __future__ import annotations

import contextlib
import io
import itertools
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appraise as A  # noqa: E402
import checklist as C  # noqa: E402

REF_DIR = A.REF


def _ok(label: str, cond: bool) -> bool:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    return bool(cond)


def _write(text: str, name: str = "draft.md") -> Path:
    p = Path(tempfile.mkdtemp()) / name
    p.write_text(text, encoding="utf-8")
    return p


def _draft(inst: A.Instrument, answers: dict[str, str], scope: str = "all",
           default: str = "") -> Path:
    """Render a filled skeleton the way an assessor would hand one back."""
    rows = ["| # | Q | Answer | Evidence |", "|---|---|---|---|"]
    for it in inst.scoped(scope):
        rows.append(f"| {it['id']} | {it['text'][:50]} | "
                    f"{answers.get(it['id'], default)} | p.1 |")
    return _write("\n".join(rows))


def _run(fn, *args) -> tuple[object, str]:
    """(return code, everything printed). A crash is a result, not a pass."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            rc = fn(*args)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
        except Exception as e:  # noqa: BLE001
            rc = f"crash: {type(e).__name__}: {e}"
    return rc, buf.getvalue()


def _cli(*argv: str) -> tuple[object, str]:
    return _run(A.main, list(argv))


def _scopes(inst: A.Instrument) -> list[str]:
    return [s.strip().lower() for s in inst.meta.get("scopes", "").split(",") if s.strip()]


def _fill(skeleton_text: str, answers: dict[str, str], default: str = "") -> str:
    """Write answers into the Answer cells of a printed skeleton."""
    out = []
    for line in skeleton_text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| ") and len(cells) == 4 and cells[0] not in ("#", "SQ"):
            a = answers.get(cells[0], default)
            line = f"| {cells[0]} | {cells[1]} | {a} | {'p.1' if a else ''} |"
        out.append(line)
    return "\n".join(out)


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
    ok &= _ok("RoB 2 parses 22 signalling questions for the effect of assignment",
              len(tools["rob2"].scoped("assignment")) == 22)

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
    # 2.1/2.2 "Yes" is normal for an open-label trial: it only opens 2.3.
    # (rollup_signalling hands RoB 2 to its own algorithm, rollup_rob2.)
    ok &= _ok("a clean open-label trial is not rated high risk anywhere",
              "HIGH / SERIOUS" not in lines)
    ok &= _ok("domain 1 low despite 1.3='No' (reverse-polarity item)",
              "Domain 1" in lines and "Domain 1 (Randomisation process): LOW" in lines)
    ok &= _ok("open-label 2.1/2.2 'Yes' only open 2.3: domain 2 LOW, on the algorithm's path",
              "Domain 2 (Deviations from intended interventions): LOW" in lines
              and "2.1 'Yes' → 2.2 'Yes' → 2.3 'No' → 2.6 'Yes'" in lines)

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

    # =====================================================================
    # Regression tests for the defects found while building the metaANAL
    # workbench on top of validator 1.0.0. Each one failed against 1.0.0.
    # =====================================================================

    print("\n[a blank question is not a LOW — incomplete domains]")
    # 1.x looked only at the answered questions of a domain: RoB 2 with 1.1
    # answered and nothing else read "Domain 1: LOW", left domains 2-5 out,
    # and ended "Implied overall: LOW" with exit 0.
    one = _draft(rob2, {"1.1": "Yes"}, "assignment")
    rc, out = _cli("--rollup", str(one), "--tool", "rob2", "--scope", "assignment")
    ok &= _ok("RoB 2 with only 1.1 answered: domain 1 is INCOMPLETE, not LOW",
              "Domain 1 (Randomisation process): INCOMPLETE" in out
              and "Domain 1 (Randomisation process): LOW" not in out)
    ok &= _ok("... the overall is INCOMPLETE, not LOW",
              "Implied overall: INCOMPLETE" in out and "Implied overall: LOW" not in out)
    ok &= _ok("... every in-scope domain is listed, answered or not",
              all(f"Domain {d} (" in out for d in "12345"))
    ok &= _ok(f"... and the rollup exits 1 (got {rc!r})", rc == 1)
    blank12 = {k: v for k, v in clean.items() if k not in ("1.2", "1.3")}
    lines = "\n".join(A.rollup_signalling(rob2, blank12, rob2.scoped("assignment")))
    ok &= _ok("clean answers with 1.2/1.3 blank: domain 1 INCOMPLETE and names them",
              "Domain 1 (Randomisation process): INCOMPLETE" in lines and "1.2, 1.3" in lines)

    print("\n[GRADE and Newcastle-Ottawa do not ignore blanks]")
    g1 = grade({"0.1": "High"})
    ok &= _ok("GRADE with 1 of 9 answered gives no certainty",
              "CERTAINTY: HIGH" not in g1 and "CERTAINTY: INCOMPLETE" in g1)
    g0 = grade({k: v for k, v in base.items() if k != "0.1"})
    ok &= _ok("GRADE with 0.1 blank does not start High by default",
              "Start: HIGH" not in g0 and "CERTAINTY: HIGH" not in g0)
    n1 = "\n".join(A.rollup_nos(ns, {"S1": "Yes"}, cohort_items))
    ok &= _ok("NOS with only S1 answered names the unanswered items",
              "unanswered" in n1 and "S2" in n1 and "O3" in n1)

    print("\n[polarity — an ideal study is not high risk]")
    q2 = tools["quadas2"]
    qo = "\n".join(A.rollup_signalling(q2, {i["id"]: "Yes" for i in q2.items}, q2.items))
    ok &= _ok("QUADAS-2 all Yes (case-control avoided, no bad exclusions) is LOW",
              "HIGH / SERIOUS" not in qo and "Implied overall: LOW" in qo)
    ri = tools["robins-i"]
    ri_good = {"1.1": "Yes", "1.2": "No", "1.3": "N/A", "1.4": "Yes", "1.5": "Yes",
               "1.6": "No", "1.7": "N/A", "1.8": "N/A",
               "2.1": "No", "2.2": "N/A", "2.3": "N/A", "2.4": "Yes", "2.5": "N/A",
               "3.1": "Yes", "3.2": "Yes", "3.3": "No",
               "4.1": "No", "4.2": "N/A", "4.3": "Yes", "4.4": "Yes", "4.5": "Yes",
               "4.6": "N/A",
               "5.1": "Yes", "5.2": "No", "5.3": "No", "5.4": "N/A", "5.5": "N/A",
               "6.1": "No", "6.2": "No", "6.3": "Yes", "6.4": "No",
               "7.1": "No", "7.2": "No", "7.3": "No"}
    for sc in ("assignment", "adherence"):
        ro = "\n".join(A.rollup_signalling(ri, ri_good, ri.scoped(sc)))
        ok &= _ok(f"ROBINS-I well-conducted study ({sc}) has no high-risk domain",
                  "HIGH / SERIOUS" not in ro and "INCOMPLETE" not in ro)
    ro = "\n".join(A.rollup_signalling(ri, ri_good, ri.scoped("assignment")))
    # Potential for confounding (1.1 Yes) rules out Low; it does not make every
    # observational study Serious — 1.4-1.8 decide that.
    ok &= _ok("ROBINS-I 1.1 Yes with confounding controlled -> middle tier, not serious",
              "Domain 1 (Bias due to confounding): SOME CONCERNS" in ro)
    ro2 = "\n".join(A.rollup_signalling(ri, dict(ri_good, **{"1.4": "No"}),
                                        ri.scoped("assignment")))
    ok &= _ok("... and an uncontrolled important confounder (1.4 No) is still serious",
              "Domain 1 (Bias due to confounding): HIGH / SERIOUS" in ro2)
    re_ = tools["robins-e"]
    re_good = {"1.1": "Yes", "1.2": "Yes", "1.3": "No", "1.4": "No", "1.5": "N/A",
               "2.1": "Yes", "2.2": "No", "2.3": "Yes", "3.1": "No", "3.2": "Yes",
               "3.3": "N/A", "4.1": "No", "4.2": "N/A", "5.1": "Yes", "5.2": "No",
               "5.3": "N/A", "6.1": "No", "6.2": "Yes", "6.3": "Yes",
               "7.1": "No", "7.2": "No", "7.3": "No", "7.4": "No"}
    reo = "\n".join(A.rollup_signalling(re_, re_good, re_.items))
    ok &= _ok("ROBINS-E well-conducted study has no high-risk domain",
              "HIGH / SERIOUS" not in reo)
    rbx = tools["robis"]
    rbx_good = dict({i["id"]: "Yes" for i in rbx.items}, **{"1.4": "Yes", "1.5": "No",
                                                            "2.4": "No"})
    rv = "\n".join(A.rollup_signalling(rbx, rbx_good, rbx.items))
    ok &= _ok("a reverse-worded flag is reported as the Yes it was (ROBIS 1.4)",
              "'Yes' or 'Probably yes' at 1.4" in rv
              and "'No' or 'Probably no' at 1.4" not in rv)

    rb = tools["robis"]
    rb_good = dict({i["id"]: "Yes" for i in rb.items}, **{"1.4": "No", "1.5": "No", "2.4": "No"})
    rbo = "\n".join(A.rollup_signalling(rb, rb_good, rb.items))
    ok &= _ok("ROBIS flawless review (4.6 and 3C Yes) has no high-risk group",
              "HIGH / SERIOUS" not in rbo)

    print("\n[ROBIS phase 3 is its own group]")
    sk = A.skeleton(rb, "all")
    heads = [ln for ln in sk.splitlines() if ln.startswith("## ")]
    ok &= _ok(f"ROBIS skeleton has 5 groups (got {len(heads)})", len(heads) == 5)
    ok &= _ok("domain 3 keeps its own title; phase 3 has its own heading",
              any(h.startswith("## Domain 3 — Data collection") for h in heads)
              and any(h.startswith("## Phase 3 — Risk of bias in the review") for h in heads))

    print("\n[QUIPS 'Partly' is the middle level]")
    qp = tools["quips"]
    qpo = "\n".join(A.rollup_signalling(qp, {i["id"]: "Partly" for i in qp.items}, qp.items))
    ok &= _ok("QUIPS all 'Partly' gives no LOW domain",
              "): LOW" not in qpo and qpo.count("SOME CONCERNS") >= 6)

    print("\n[Newcastle-Ottawa partial stars]")
    n_s1 = "\n".join(A.rollup_nos(ns, dict(perfect, **{"S1": "Partial yes"}), cohort_items))
    ok &= _ok("'Partial yes' on one-star S1 earns no star, and says why",
              "TOTAL: 8/9 stars" in n_s1 and "S1" in n_s1.split("TOTAL")[1])
    rc, out = _run(A.verify, _draft(ns, {}, "cohort", "PY"), ns, "cohort")
    ok &= _ok(f"'PY' is not an answer on the Newcastle-Ottawa scale (rc {rc!r})",
              rc == 1 and "8/8 answered" not in out)

    print("\n[per-instrument shorthands — PY]")
    am_p = _draft(am, dict(all_yes, **{"2": "Partial yes", "4": "Partial yes"}))
    am_py = _draft(am, dict(all_yes, **{"2": "PY", "4": "PY"}))
    _, o1 = _cli("--rollup", str(am_p), "--tool", "amstar2")
    _, o2 = _cli("--rollup", str(am_py), "--tool", "amstar2")
    pick = (lambda s: [ln for ln in s.splitlines() if "weaknesses" in ln or "RESULTS:" in ln])
    ok &= _ok("AMSTAR 2: 'PY' is Partial yes — same rating as writing it out",
              pick(o1) == pick(o2) and "RESULTS: MODERATE" in o2)
    rob_py = A.read_answers(_draft(rob2, dict(clean, **{"1.2": "PY"}), "assignment"),
                            rob2, "assignment")
    ok &= _ok("RoB 2: 'PY' is still read (probably yes)", rob_py.get("1.2") == "PY")

    print("\n[GRADE publication bias]")
    ok &= _ok("'Strongly suspected' downgrades one level",
              "CERTAINTY: MODERATE" in grade(dict(base, **{"5.1": "Strongly suspected"})))
    sus = grade(dict(base, **{"5.1": "Suspected"}))
    ok &= _ok("'Suspected' is UNRESOLVED, not silently High",
              "CERTAINTY: HIGH" not in sus and "UNRESOLVED" in sus)
    gfile = _draft(gr, dict(base, **{"5.1": "Suspected"}))
    rc, _ = _cli("--rollup", str(gfile), "--tool", "grade")
    ok &= _ok(f"... and the rollup exits 1 until it is decided (rc {rc!r})", rc == 1)
    rc, out = _cli("--verify", str(_draft(gr, dict(base, **{"5.1": "Serious"}))),
                   "--tool", "grade")
    ok &= _ok("'Serious' is not a publication-bias answer", rc == 1 and "5.1" in out)

    print("\n[GRADE vocabulary]")
    rc, out = _cli("--verify", str(_draft(gr, dict(base, **{"5.1": "Could not be assessed"}))),
                   "--tool", "grade")
    ok &= _ok("'Could not be assessed' is an answer (verifies complete)",
              rc == 0 and "UNANSWERED" not in out)
    ok &= _ok("... and is UNRESOLVED in the rollup",
              "UNRESOLVED" in grade(dict(base, **{"5.1": "Could not be assessed"})))
    ok &= _ok("a very large effect upgrades two levels (Low -> High)",
              "CERTAINTY: HIGH" in grade(dict(obs, **{"6.1": "Very large"})))
    rc, out = _cli("--verify", str(_draft(gr, {"0.1": "High"})), "--tool", "grade")
    ok &= _ok("the verify hint does not call 'Low' an answer for every slot",
              "'Low' is an answer" not in out)

    print("\n[checklist.py reads the status cell and the pass]")
    rc, out = _run(C.verify, _write(C.skeleton_tripod("both")), "tripod", "both")
    ok &= _ok(f"blank TRIPOD+AI skeleton verifies 0/52 ({out.split(chr(10))[0].strip()})",
              "0/52 answered" in out and rc == 1)
    pb = C.skeleton_probast("both")
    dev_only, cur = [], None
    for ln in pb.splitlines():
        if ln.startswith("### "):
            cur = "development" if "development" in ln else "evaluation"
        c_ = [x.strip() for x in ln.strip().strip("|").split("|")]
        if cur == "development" and ln.startswith("| ") and re.match(r"\d\.\d", c_[0]):
            ln = f"| {c_[0]} | {c_[1]} | Yes | p.1 |"
        dev_only.append(ln)
    rc, out = _run(C.verify, _write("\n".join(dev_only)), "probast", "both")
    ok &= _ok(f"PROBAST+AI development pass only: 16/34 ({out.split(chr(10))[0].strip()})",
              "16/34 answered" in out and "evaluation/1.1" in out)
    ev_no = [f"| {x[0]} | {x[1]} |  | no mention in methods |"
             if (ln.startswith("| ") and re.match(r"\d\.\d", (x := [y.strip() for y in
                 ln.strip().strip("|").split("|")])[0])) else ln for ln in pb.splitlines()]
    rc, out = _run(C.verify, _write("\n".join(ev_no)), "probast", "both")
    ok &= _ok("'no' inside an evidence note is not an answer (0/34, exit 1)",
              "0/34 answered" in out and rc == 1)

    print("\n[a blank skeleton verifies 0/N, for every tool and scope]")
    zero_ok, worst = True, ""
    for key, inst in sorted(tools.items()):
        if inst.meta.get("engine"):
            continue
        for sc in ["all"] + [s for s in _scopes(inst) if s != "all"]:
            n = len(inst.scoped(sc))
            rc, out = _run(A.verify, _write(A.skeleton(inst, sc)), inst, sc)
            if f"0/{n} answered" not in out or rc != 1:
                zero_ok, worst = False, f"{key}/{sc}: {out.split(chr(10))[0].strip()}"
    ok &= _ok(f"every blank skeleton verifies 0/N {worst}", zero_ok)
    am_sk = _fill(A.skeleton(am, "all"), {i["id"]: "Yes" for i in am.items if i["id"] != "16"})
    rc, out = _run(A.verify, _write(am_sk), am, "all")
    ok &= _ok("AMSTAR 2 with item 16 blank is not complete", rc == 1 and "16" in out)

    print("\n[prose appraisals]")
    prose = "\n".join(f"- {it['id']} {it['text']} — **{clean[it['id']]}**"
                      for it in rob2.scoped("assignment"))
    pg = A.read_answers(_write(prose), rob2, "assignment")
    wrong = {k: v for k, v in pg.items() if v != clean[k]}
    ok &= _ok(f"prose RoB 2 reads the answer, not the 'If Y/PY to …' clause "
              f"({len(pg)}/22, wrong: {sorted(wrong)})", len(pg) == 22 and not wrong)

    print("\n[unknown scope]")
    rc, out = _cli("--skeleton", "nos", "--scope", "cohorts")
    ok &= _ok(f"'--scope cohorts' is refused (rc {rc!r})", rc == 2)
    rc, out = _cli("--verify", str(_write("\n")), "--tool", "jbi", "--scope", "case-reports")
    ok &= _ok(f"an empty file with a typo'd scope does not verify complete (rc {rc!r})",
              rc == 2 and "complete" not in out)
    rc, _ = _cli("--skeleton", "jbi", "--scope", "case-report")
    ok &= _ok("valid scopes still work", rc == 0)

    print("\n[RoB 2 effect of adhering]")
    adh = rob2.scoped("adherence")
    ok &= _ok(f"adherence scope has its own domain 2 (21 items, got {len(adh)})",
              len(adh) == 21 and any(i["domain"] == "2" for i in adh))
    covers = True
    for key in ("rob2", "robins-i"):
        inst = tools[key]
        doms = {i["domain"] for i in inst.items}
        for sc in _scopes(inst):
            if {i["domain"] for i in inst.scoped(sc)} != doms:
                covers = False
    ok &= _ok("every effect-of-interest scope covers every domain", covers)

    print("\n[AMSTAR 2 without a meta-analysis]")
    na3 = amstar(dict(all_yes, **{"11": "N/A", "12": "N/A", "15": "N/A"}))
    ok &= _ok("N/A on 11, 12, 15 is neither flaw nor weakness -> High",
              "RESULTS: HIGH" in na3 and "Critical flaws (0)" in na3)
    rc, out = _run(A.verify, _draft(am, dict(all_yes, **{"3": "N/A"})), am, "all")
    ok &= _ok("N/A on an item that does not offer it is rejected", rc == 1 and "3" in out)

    print("\n[published item counts and the renumbering]")
    rc, out = _cli("--counts")
    ok &= _ok("ROBINS-I has the 2016 tool's 34 items",
              re.search(r"robins-i\s+34 tétel\s+ok", out) is not None)
    ok &= _ok("QUIPS has the 31 published prompting items",
              re.search(r"quips\s+31 tétel\s+ok", out) is not None)
    old_ri = {"4.3": "Was the analysis appropriate to estimate the effect of starting and "
                     "adhering to the intervention?",
              "4.4": "Were important co-interventions balanced across intervention groups?",
              "4.5": "Was the intervention implemented successfully for most participants?",
              "4.6": "Did study participants adhere to the assigned intervention regimen?",
              "5.2": "Were participants excluded due to missing data on intervention status, "
                     "or on other variables needed for the analysis?",
              "5.3": "Are the proportion of participants and reasons for missing data "
                     "similar across interventions?"}
    old_ids = ([f"1.{i}" for i in range(1, 9)] + [f"2.{i}" for i in range(1, 6)]
               + ["3.1", "3.2", "3.3"] + [f"4.{i}" for i in range(1, 7)]
               + ["5.1", "5.2", "5.3", "6.1", "6.2", "6.3", "7.1", "7.2", "7.3"])
    cur_text = {i["id"]: i["text"] for i in ri.items}
    old_ans = dict(ri_good, **{"4.3": "Yes", "4.4": "Probably no", "4.5": "Yes",
                               "4.6": "No", "5.2": "No", "5.3": "Yes", "4.1": "N/A"})
    rows = ["| # | Signalling question | Answer | Evidence (quote or section) |",
            "|---|---|---|---|"]
    rows += [f"| {i} | {old_ri.get(i, cur_text.get(i, ''))[:76]} | {old_ans[i]} | p.{n} |"
             for n, i in enumerate(old_ids)]
    old_file = _write("\n".join(rows + ["", "<!-- 31 slots; run --verify -->"]))
    rc, out = _cli("--verify", str(old_file), "--tool", "robins-i", "--scope", "adherence")
    ok &= _ok("a ROBINS-I file in the 1.x numbering is recognised and not scored",
              rc == 1 and "LEGACY NUMBERING" in out)
    rc, out = _cli("--rollup", str(old_file), "--tool", "robins-i", "--scope", "adherence")
    ok &= _ok("... by --rollup either", rc == 1 and "Domain 4" not in out)
    rc, mig = _cli("--migrate", str(old_file), "--tool", "robins-i", "--scope", "adherence")
    new_file = _write(mig.split("MIGRATION —")[0])
    ma = A.read_answers(new_file, ri, "adherence") if rc == 0 else {}
    ok &= _ok("--migrate moves each answer to the question it answered "
              "(1.x 4.4 -> 4.3, 4.3 -> 4.6, 5.3 -> 5.4; 5.2 'No' -> 5.2 and 5.3)",
              rc == 0 and ma.get("4.3") == "Probably no" and ma.get("4.6") == "Yes"
              and ma.get("4.5") == "No" and ma.get("5.4") == "Yes"
              and ma.get("5.2") == "No" and ma.get("5.3") == "No")
    rc, out = _cli("--verify", str(new_file), "--tool", "robins-i", "--scope", "adherence")
    ok &= _ok("... and the migrated file asks only the new questions (5.5, 6.4)",
              rc == 1 and "UNANSWERED (2): 5.5, 6.4" in out)
    rc, _ = _cli("--migrate", str(new_file), "--tool", "robins-i", "--scope", "adherence")
    ok &= _ok("a migrated file is never renumbered a second time", rc == 1)
    old_q = ["| # | Signalling question | Answer | Evidence |", "|---|---|---|---|"]
    old_q += [f"| {d}.{k} | old prompt | {'Partly' if (d, k) == (1, 5) else 'Yes'} | p.1 |"
              for d, n in ((1, 6), (2, 5), (3, 6), (4, 4), (5, 6), (6, 5))
              for k in range(1, n + 1)]
    qfile = _write("\n".join(old_q))
    rc, out = _cli("--verify", str(qfile), "--tool", "quips")
    ok &= _ok("a QUIPS file in the 1.x numbering (1.1-6.5) is recognised",
              rc == 1 and "LEGACY NUMBERING" in out)
    rc, mig = _cli("--migrate", str(qfile), "--tool", "quips")
    mq = A.read_answers(_write(mig.split("MIGRATION —")[0]), qp, "all") if rc == 0 else {}
    ok &= _ok("--migrate carries QUIPS 1.5 'Partly' to 1a and leaves 3c blank",
              mq.get("1a") == "Partly" and "3c" not in mq and len(mq) == 24)

    print("\n[the checklist.py redirect]")
    rc, out = _cli("--skeleton", "tripod-ai")
    ok &= _ok("'--skeleton tripod-ai' points at '--skeleton tripod', not probast",
              "--skeleton tripod" in out and "--skeleton probast" not in out)

    print("\n[routing a non-randomised design]")
    for q in ("non-randomised study of a surgical intervention", "non-randomized trial",
              "a non-randomised controlled study"):
        hits = [t_ for t_, _ in A.route(q)]
        ok &= _ok(f"'{q}' -> robins-i, not rob2 ({hits})",
                  "robins-i" in hits and "rob2" not in hits)

    print("\n[applicability per domain]")
    qsk = A.skeleton(q2, "all")
    ok &= _ok("QUADAS-2 skeleton has an applicability slot for each of domains 1-3",
              all(f"**Domain {d} applicability:**" in qsk for d in "123")
              and "**Domain 4 applicability:**" not in qsk)
    ok &= _ok("RoB 2 skeleton has no applicability slot",
              "applicability" not in A.skeleton(rob2, "assignment").lower())

    print("\n[ids are unique within every scope]")
    uniq = all(len({i["id"] for i in inst.scoped(sc)}) == len(inst.scoped(sc))
               for inst in tools.values() if not inst.meta.get("engine")
               for sc in ["all"] + _scopes(inst))
    ok &= _ok("no scope of any instrument repeats an item id", uniq)

    ok &= methodology_review(tools)
    ok &= gateway_review(tools)
    ok &= agreement_review(tools)

    print(f"\n{'ALL PASSED' if ok else 'FAILURES PRESENT'}")
    return ok


#: An all-low RoB 2 result, answered the way the 2019 template routes it: nobody
#: aware (2.3-2.5 not asked), ITT (2.7 not asked), complete data (3.2-3.4 not
#: asked), assessors unaware (4.4-4.5 not asked).
R2_ASSIGN = {"1.1": "Y", "1.2": "Y", "1.3": "N", "2.1": "N", "2.2": "N", "2.3": "N/A",
             "2.4": "N/A", "2.5": "N/A", "2.6": "Y", "2.7": "N/A", "3.1": "Y", "3.2": "N/A",
             "3.3": "N/A", "3.4": "N/A", "4.1": "N", "4.2": "N", "4.3": "N", "4.4": "N/A",
             "4.5": "N/A", "5.1": "Y", "5.2": "N", "5.3": "N"}
R2_ADHERE = dict({k: v for k, v in R2_ASSIGN.items() if k != "2.7"},
                 **{"2.3": "N/A", "2.4": "N", "2.5": "N", "2.6": "N/A"})
_VERDICT = r"(LOW|SOME CONCERNS / UNCLEAR|HIGH / SERIOUS|INCOMPLETE)"


def _verdict(out: str, group: str) -> str | None:
    m = re.search(rf"{re.escape(group)} \([^)]*\): {_VERDICT}", out)
    return m.group(1) if m else None


def _overall(out: str) -> str | None:
    m = re.search(r"Implied overall: (LOW|SOME CONCERNS|HIGH / SERIOUS|INCOMPLETE)", out)
    return m.group(1) if m else None


def methodology_review(tools: dict) -> bool:
    """Regression tests for the methodology review of 2.0.0 (findings F1-F12).

    Each case is a verdict the published instrument gives and the engine did not:
    run against commit 60e290b (the first 2.0.0 commit), every block below fails.
    """
    ok = True
    rob2 = tools["rob2"]
    LOW, SOME, HIGH = "LOW", "SOME CONCERNS / UNCLEAR", "HIGH / SERIOUS"

    def r2(over: dict, scope: str = "assignment") -> tuple[object, str]:
        base = R2_ASSIGN if scope == "assignment" else R2_ADHERE
        p = _write(_fill(A.skeleton(rob2, scope), dict(base, **over)))
        return _cli("--rollup", str(p), "--tool", "rob2", "--scope", scope)

    def r2_case(label: str, over: dict, domain: str, want: str,
                scope: str = "assignment") -> bool:
        rc, out = r2(over, scope)
        got = _verdict(out, f"Domain {domain}")
        overall = {SOME: "SOME CONCERNS"}.get(want, want)
        return _ok(f"{label}: domain {domain} {want} (got {got}, overall {_overall(out)}, "
                   f"rc {rc!r})", got == want and _overall(out) == overall and rc == 0)

    print("\n[RoB 2 runs the 2019 per-domain algorithm (F1-F4)]")
    rc, out = r2({})
    ok &= _ok(f"an all-low result is LOW in every domain, overall LOW, exit 0 (rc {rc!r})",
              all(_verdict(out, f"Domain {d}") == LOW for d in "12345")
              and _overall(out) == "LOW" and rc == 0)
    # F1 — domain 3: 3.1, 3.2 and 3.3 are gates, not problem answers.
    ok &= r2_case("F1a 3.1 No, 3.2 Yes (evidence of no bias)",
                  {"3.1": "N", "3.2": "Y"}, "3", LOW)
    ok &= r2_case("F1b 3.1/3.2/3.3 No (missingness cannot depend on the value)",
                  {"3.1": "N", "3.2": "N", "3.3": "N"}, "3", LOW)
    ok &= r2_case("F1c 3.3 Yes, 3.4 No", {"3.1": "N", "3.2": "N", "3.3": "Y", "3.4": "N"},
                  "3", SOME)
    ok &= r2_case("F1 3.3 NI, 3.4 NI", {"3.1": "N", "3.2": "N", "3.3": "NI", "3.4": "NI"},
                  "3", HIGH)
    rc, out = r2({"3.1": "N", "3.2": "N/A"})
    ok &= _ok(f"F1 N/A at 3.2 after 3.1 No: INCOMPLETE, names 3.2, exit 1 (rc {rc!r})",
              _verdict(out, "Domain 3") == "INCOMPLETE" and "3.2" in out and rc == 1)
    # F2 — domain 2 (assignment) part 1 and domain 4: 2.3/2.4/4.4 are scored.
    aware = {"2.1": "Y", "2.2": "Y"}
    ok &= r2_case("F2 2.3 NI (no information on deviations)", dict(aware, **{"2.3": "NI"}),
                  "2", SOME)
    ok &= r2_case("F2 2.3 Yes, 2.4 No", dict(aware, **{"2.3": "Y", "2.4": "N"}), "2", SOME)
    ok &= r2_case("F2 2.4 Yes, 2.5 Yes (balanced)",
                  dict(aware, **{"2.3": "Y", "2.4": "Y", "2.5": "Y"}), "2", SOME)
    ok &= r2_case("F2 2.5 NI", dict(aware, **{"2.3": "Y", "2.4": "Y", "2.5": "NI"}), "2", HIGH)
    ok &= r2_case("F2 2.6 NI, 2.7 NI", {"2.6": "NI", "2.7": "NI"}, "2", HIGH)
    ok &= r2_case("F2 4.4 Yes, 4.5 No", {"4.3": "Y", "4.4": "Y", "4.5": "N"}, "4", SOME)
    ok &= r2_case("F2 4.5 NI", {"4.3": "Y", "4.4": "Y", "4.5": "NI"}, "4", HIGH)
    # F3 — 1.1, 1.3 (with 1.2 Yes), 2.6 with 2.7 No, and 5.1 are middle; NI at the
    # gating questions 1.1, 1.3 and 4.1 does not rule out Low.
    ok &= r2_case("F3 1.1 No with concealment (1.2 Yes)", {"1.1": "N"}, "1", SOME)
    ok &= r2_case("F3 1.3 Yes with concealment (1.2 Yes)", {"1.3": "Y"}, "1", SOME)
    ok &= r2_case("F3 1.2 No is High", {"1.2": "N"}, "1", HIGH)
    ok &= r2_case("F3 1.2 NI, 1.3 Yes is High", {"1.2": "NI", "1.3": "Y"}, "1", HIGH)
    ok &= r2_case("F3 1.2 NI, 1.3 No is Some concerns", {"1.2": "NI"}, "1", SOME)
    ok &= r2_case("F3 1.1 NI and 1.3 NI are compatible with Low", {"1.1": "NI", "1.3": "NI"},
                  "1", LOW)
    ok &= r2_case("F3 2.6 No, 2.7 No", {"2.6": "N", "2.7": "N"}, "2", SOME)
    ok &= r2_case("F3 2.6 No, 2.7 Yes", {"2.6": "N", "2.7": "Y"}, "2", HIGH)
    ok &= r2_case("F3 5.1 No, 5.2/5.3 No", {"5.1": "N"}, "5", SOME)
    ok &= r2_case("F3 5.2 NI, neither Yes", {"5.2": "NI"}, "5", SOME)
    ok &= r2_case("F3 5.3 Yes", {"5.3": "Y"}, "5", HIGH)
    ok &= r2_case("F3 4.1 NI follows the No branch", {"4.1": "NI"}, "4", LOW)
    ok &= r2_case("F3 4.2 NI caps an otherwise-low domain 4 at Some concerns",
                  {"4.2": "NI"}, "4", SOME)
    # F4 — effect of adhering: NI at 2.6 is the bad branch.
    ok &= r2_case("F4 adherence baseline", {}, "2", LOW, scope="adherence")
    ok &= r2_case("F4 adherence 2.4 Yes, 2.6 Yes", {"2.4": "Y", "2.6": "Y"}, "2", SOME,
                  scope="adherence")
    ok &= r2_case("F4 adherence 2.4 Yes, 2.6 NI", {"2.4": "Y", "2.6": "NI"}, "2", HIGH,
                  scope="adherence")
    ok &= r2_case("F4 adherence 2.5 NI, 2.6 NI", {"2.5": "NI", "2.6": "NI"}, "2", HIGH,
                  scope="adherence")
    ref = (REF_DIR / "rob2.md").read_text(encoding="utf-8")
    ok &= _ok("F4 rob2.md no longer says adherence domain 2 is High only when 2.6 is No",
              "only when 2.6, the analysis\nquestion, is No" not in ref)
    rc, out = r2({"2.1": "Y", "2.2": "Y", "2.3": "N"})
    ok &= _ok("an open-label trial without trial-context deviations (2.3 No) is LOW",
              _verdict(out, "Domain 2") == LOW and rc == 0)

    print("\n[N/A only where the instrument offers it (F5)]")
    all_na = {it["id"]: "N/A" for it in rob2.scoped("assignment")}
    p = _write(_fill(A.skeleton(rob2, "assignment"), all_na))
    rc, out = _cli("--verify", str(p), "--tool", "rob2", "--scope", "assignment")
    ok &= _ok(f"RoB 2 all N/A does not verify complete (rc {rc!r})",
              rc == 1 and "INVALID" in out and "1.1" in out and "complete" not in out)
    rc, out = _cli("--rollup", str(p), "--tool", "rob2", "--scope", "assignment")
    ok &= _ok(f"... and rolls up INCOMPLETE, not LOW (rc {rc!r})",
              rc == 1 and _overall(out) == "INCOMPLETE")
    rc, out = _cli("--verify", str(_write(_fill(A.skeleton(rob2, "assignment"), R2_ASSIGN))),
                   "--tool", "rob2", "--scope", "assignment")
    ok &= _ok("RoB 2 N/A on the conditional questions still verifies complete", rc == 0)
    rc, out = _cli("--verify", str(_write(_fill(A.skeleton(rob2, "adherence"), R2_ADHERE))),
                   "--tool", "rob2", "--scope", "adherence")
    ok &= _ok("RoB 2 adherence N/A at 2.3 and 2.6 verifies complete", rc == 0)
    rb = tools["robis"]
    p = _write(_fill(A.skeleton(rb, "all"), {i["id"]: "N/A" for i in rb.items}))
    rc, out = _cli("--verify", str(p), "--tool", "robis")
    ok &= _ok(f"ROBIS all N/A does not verify complete (rc {rc!r})",
              rc == 1 and "INVALID" in out)
    pb = C.skeleton_probast("both")

    def probast_fill(answer_for) -> str:
        out_, cur = [], None
        for ln in pb.splitlines():
            if ln.startswith("### "):
                cur = "development" if "development" in ln else "evaluation"
            c_ = [x.strip() for x in ln.strip().strip("|").split("|")]
            if ln.startswith("| ") and re.match(r"\d\.\d", c_[0]):
                ln = f"| {c_[0]} | {c_[1]} | {answer_for(cur, c_[0], c_[1])} | p.1 |"
            out_.append(ln)
        return "\n".join(out_)
    rc, out = _run(C.verify, _write(probast_fill(lambda *_: "N/A")), "probast", "both")
    ok &= _ok(f"PROBAST+AI all N/A does not verify complete (rc {rc!r})",
              rc == 1 and "INVALID" in out and "complete" not in out)
    cond = probast_fill(lambda p_, q, t: "N/A" if t.startswith("If ") else "Yes")
    rc, out = _run(C.verify, _write(cond), "probast", "both")
    ok &= _ok(f"PROBAST+AI N/A on the 'If ...' questions only verifies complete (rc {rc!r})",
              rc == 0 and "34/34 answered" in out)

    print("\n[ROBIS overall is the phase-3 judgement (F6)]")
    rb_good = dict({i["id"]: "Yes" for i in rb.items}, **{"1.4": "No", "1.5": "No", "2.4": "No"})
    p = _write(_fill(A.skeleton(rb, "all"), dict(rb_good, **{"4.5": "No"})))
    rc, out = _cli("--rollup", str(p), "--tool", "robis")
    ok &= _ok(f"4.5 No with the concern addressed (3A Yes): domain 4 flagged, overall LOW "
              f"(got {_overall(out)}, rc {rc!r})",
              _verdict(out, "Domain 4") == HIGH and _verdict(out, "Phase 3") == LOW
              and _overall(out) == "LOW" and rc == 0)
    p = _write(_fill(A.skeleton(rb, "all"), dict(rb_good, **{"4.5": "No", "3A": "No"})))
    rc, out = _cli("--rollup", str(p), "--tool", "robis")
    ok &= _ok(f"... not addressed (3A No): overall HIGH (got {_overall(out)})",
              _overall(out) == "HIGH / SERIOUS")
    p = _write(_fill(A.skeleton(rb, "all"), {k: v for k, v in rb_good.items() if k != "2.1"}))
    rc, out = _cli("--rollup", str(p), "--tool", "robis")
    ok &= _ok("... and a blank in domains 1-4 still makes the overall INCOMPLETE",
              _overall(out) == "INCOMPLETE" and rc == 1)

    print("\n[Newcastle-Ottawa is one form per study (F7, F8)]")
    one_row = str(_write("| # | Q | Answer | Evidence |\n|---|---|---|---|\n| S1 | x | Yes | p |"))
    for argv in (("--skeleton", "nos"), ("--verify", one_row, "--tool", "nos"),
                 ("--rollup", one_row, "--tool", "nos")):
        rc, out = _cli(*argv)
        ok &= _ok(f"'{argv[0]} nos' without --scope is a usage error (rc {rc!r})",
                  rc == 2 and "slots to fill" not in out and "case-control" in out)
    rc, out = _cli("--skeleton", "nos", "--scope", "cohort")
    ok &= _ok("'--skeleton nos --scope cohort' prints the 8 cohort slots",
              rc == 0 and "8 slots to fill" in out)
    ns = tools["nos"]
    p = _write(_fill(A.skeleton(ns, "cohort"), {i["id"]: "N/A" for i in ns.scoped("cohort")}))
    rc, out = _cli("--rollup", str(p), "--tool", "nos", "--scope", "cohort")
    ok &= _ok(f"a cohort record with every item N/A is not a final total (rc {rc!r})",
              rc == 1 and "S1 'N/A'" in out)
    rc, out = _cli("--verify", str(p), "--tool", "nos", "--scope", "cohort")
    ok &= _ok("... and does not verify complete", rc == 1 and "INVALID" in out)
    mixed = "\n".join(A.rollup_nos(ns, {i["id"]: "Yes" for i in ns.items}, ns.items))
    ok &= _ok("rollup_nos never sums the two forms (no '/18')", "/18" not in mixed)

    print("\n[TRIPOD+AI: the abstracts checklist is not the main checklist (F9)]")
    blank_main = {"1", "2", "4", "7", "10", "11", "13"}
    tsk = []
    for ln in C.skeleton_tripod("both").splitlines():
        c_ = [x.strip() for x in ln.strip().strip("|").split("|")]
        if ln.startswith("| ") and len(c_) == 5 and re.match(r"\d", c_[0]) \
                and c_[0] not in blank_main:
            ln = f"| {c_[0]} | {c_[1]} | {c_[2]} | Present | sec |"
        tsk.append(ln)
    abstracts = ["", "## Item 2 — TRIPOD+AI for Abstracts", "", "| Item | Status |",
                 "|---|---|"] + [f"| {n} | Present |" for n in range(1, 14)]
    rc, out = _run(C.verify, _write("\n".join(tsk + abstracts)), "tripod", "both")
    ok &= _ok(f"abstracts table rows 1-13 do not answer main items "
              f"({out.splitlines()[0].strip() if out else ''})",
              rc == 1 and "45/52 answered" in out)
    prose_abs = ["", "## TRIPOD+AI for Abstracts"] + [f"{n}. Present" for n in range(1, 14)]
    rc, out = _run(C.verify, _write("\n".join(tsk + prose_abs)), "tripod", "both")
    ok &= _ok("... nor do numbered prose lines under that heading", rc == 1 and "45/52" in out)
    gaps = ["", "## Prioritised gaps", "", "1. Item 18e (code availability) — Missing",
            "2. Item 14 (fairness) — Partial", "4. Item 9 — Missing"]
    rc, out = _run(C.verify, _write("\n".join(tsk + gaps)), "tripod", "both")
    ok &= _ok("... nor does a numbered gap list that names other items",
              rc == 1 and "45/52" in out)
    gap_tab = ["", "| Priority | Item | Status |", "|---|---|---|", "| 1 | 18e | Missing |",
               "| 2 | 14 | Partial |"]
    rc, out = _run(C.verify, _write("\n".join(tsk + gap_tab)), "tripod", "both")
    ok &= _ok("... nor a gap table whose item column is not the first",
              rc == 1 and "45/52" in out)
    sect = [re.sub(r"\|\s+\|\s+\|$", "| Present | p.1 |", ln) if ln.startswith("| 2 |") else ln
            for ln in tsk]
    rc, out = _run(C.verify, _write("## Abstract\n\n" + "\n".join(sect)), "tripod", "both")
    ok &= _ok("a main-checklist row under a plain '## Abstract' heading still counts",
              "46/52 answered" in out)
    # The same keying bug in appraise.py: AMSTAR 2's ids are 1-16.
    am_ = tools["amstar2"]
    am_txt = "\n".join(["| # | Q | Answer | Evidence |", "|---|---|---|---|"]
                       + [f"| {i} | q | Yes | p |" for i in range(2, 13)]
                       + ["", "## Priorities", "1. Item 7 (excluded studies) — No", "",
                          "| Priority | Item | Answer |", "|---|---|---|", "| 13 | 9 | No |"])
    got_am, _ = A.read_record(am_txt, am_, "all")
    ok &= _ok(f"AMSTAR 2: a gap list and a priority table do not answer items 1 and 13 "
              f"(got {got_am.get('1')!r}, {got_am.get('13')!r})",
              "1" not in got_am and "13" not in got_am and got_am.get("9") == "Yes")

    print("\n[GRADE rating up for opposing residual confounding (F10)]")
    t81 = next(i["text"] for i in tools["grade"].items if i["id"] == "8.1")
    ok &= _ok("8.1 asks about a spurious effect where none was observed, not a 'spurious null'",
              "spurious null" not in t81 and "no effect" in t81)

    print("\n[AMSTAR 2 Partial yes and mixed-design items (F11, F12)]")
    am = tools["amstar2"]
    all_yes = {i["id"]: "Yes" for i in am.items}
    o8 = "\n".join(A.rollup_amstar2(am, dict(all_yes, **{"8": "Partial yes",
                                                         "9": "Partial yes"}), am.items))
    ok &= _ok("Partial yes on item 8 counts like Partial yes on item 9 (2 weaknesses, Moderate)",
              "Non-critical weaknesses (2): 8, 9" in o8 and "RESULTS: MODERATE" in o8)
    ok &= _ok("the rollup states the Partial yes convention and that Box 2 is advisory",
              "convention" in o8.lower() and "Box 2" in o8)
    amref = (REF_DIR / "amstar2.md").read_text(encoding="utf-8")
    ok &= _ok("amstar2.md no longer attributes the convention to 'the AMSTAR 2 guidance'",
              "how the AMSTAR 2 guidance describes" not in amref)
    sk = A.skeleton(am, "all")
    ok &= _ok("the AMSTAR 2 skeleton says items 9 and 11 take the worse of RCT and NRSI",
              re.search(r"9 and 11.*RCT.*NRSI.*worse", sk, re.S) is not None)
    rc, out = _run(A.verify, _write(sk), am, "all")
    ok &= _ok("... and that note is not read as an answer (0/16)", "0/16 answered" in out)
    return ok



#: A ROBINS-I result with every domain at its best, answered the way the 2016
#: tool routes it (1.1 Yes: confounding expected, so domain 1 is Moderate at best).
RI_GOOD = {"1.1": "Y", "1.2": "N", "1.3": "N/A", "1.4": "Y", "1.5": "Y", "1.6": "N",
           "1.7": "N/A", "1.8": "N/A",
           "2.1": "N", "2.2": "N/A", "2.3": "N/A", "2.4": "Y", "2.5": "N/A",
           "3.1": "Y", "3.2": "Y", "3.3": "N",
           "4.1": "N", "4.2": "N/A", "4.3": "Y", "4.4": "Y", "4.5": "Y", "4.6": "N/A",
           "5.1": "Y", "5.2": "N", "5.3": "N", "5.4": "N/A", "5.5": "N/A",
           "6.1": "N", "6.2": "N", "6.3": "Y", "6.4": "N",
           "7.1": "N", "7.2": "N", "7.3": "N"}
RE_GOOD = {"1.1": "Y", "1.2": "Y", "1.3": "N", "1.4": "N", "1.5": "N/A",
           "2.1": "Y", "2.2": "N", "2.3": "Y", "3.1": "N", "3.2": "Y", "3.3": "N/A",
           "4.1": "N", "4.2": "N/A", "5.1": "Y", "5.2": "N", "5.3": "N/A",
           "6.1": "N", "6.2": "Y", "6.3": "Y", "7.1": "N", "7.2": "N", "7.3": "N", "7.4": "N"}


def gateway_review(tools: dict) -> bool:
    """ROBINS-I 2.1 is a gateway; the ROBINS-I/-E, QUADAS-2, QUIPS and --migrate review.

    Each case is a verdict the published instrument gives and the engine at commit
    1b2c906 did not (or an answer it accepted that the instrument does not offer).
    """
    ok = True
    LOW, SOME, HIGH, INC = "LOW", "SOME CONCERNS / UNCLEAR", "HIGH / SERIOUS", "INCOMPLETE"
    ri, re_ = tools["robins-i"], tools["robins-e"]

    def roll(tool: str, base: dict, over: dict, scope: str = "all",
             extra: str = "") -> tuple[object, str]:
        inst = tools[tool]
        p = _write(_fill(A.skeleton(inst, scope), dict(base, **over)) + extra)
        return _cli("--rollup", str(p), "--tool", tool, "--scope", scope)

    def case(label: str, tool: str, base: dict, over: dict, domain: str, want: str,
             scope: str = "all", rc_want: int = 0) -> bool:
        rc, out = roll(tool, base, over, scope)
        got = _verdict(out, f"Domain {domain}")
        return _ok(f"{label}: domain {domain} {want} (got {got}, rc {rc!r})",
                   got == want and rc == rc_want)

    print("\n[ROBINS-I 2.1 gateway — domain 2 per the 2016 Tables A-C]")
    tag21 = A.Instrument.tags(ri.item("2.1"))
    ok &= _ok(f"2.1 is tagged router, not middle ({sorted(tag21)})",
              "router" in tag21 and "middle" not in tag21)
    ok &= _ok("2.2 is a gateway too; 2.3 (selection tied to the outcome) rules out Low",
              "router" in A.Instrument.tags(ri.item("2.2"))
              and "middle" in A.Instrument.tags(ri.item("2.3")))
    for sc in ("assignment", "adherence"):
        ok &= case(f"G1 ({sc}) 2.1 Yes, 2.2 No — can be Low", "robins-i", RI_GOOD,
                   {"2.1": "Y", "2.2": "N"}, "2", LOW, sc)
    ok &= case("G2 2.1 Yes, 2.2 Yes, 2.3 No — no selection bias", "robins-i", RI_GOOD,
               {"2.1": "Y", "2.2": "Y", "2.3": "N"}, "2", LOW, "assignment")
    ok &= case("G3 2.1/2.2/2.3 Yes, corrected (2.5 Yes) — Moderate", "robins-i", RI_GOOD,
               {"2.1": "Y", "2.2": "Y", "2.3": "Y", "2.5": "Y"}, "2", SOME, "assignment")
    ok &= case("G3 2.1/2.2/2.3 Yes, not corrected (2.5 No) — Serious", "robins-i", RI_GOOD,
               {"2.1": "Y", "2.2": "Y", "2.3": "Y", "2.5": "N"}, "2", HIGH, "assignment")
    ok &= case("G3 2.1/2.2/2.3 Yes, 2.5 NI — at least Moderate", "robins-i", RI_GOOD,
               {"2.1": "Y", "2.2": "Y", "2.3": "Y", "2.5": "NI"}, "2", SOME, "assignment")
    rc, out = roll("robins-i", RI_GOOD, {"2.1": "Y", "2.2": "Y", "2.3": "Y"}, "assignment")
    ok &= _ok("G3 ... with 2.5 left N/A: INCOMPLETE, 2.5 named, exit 1",
              _verdict(out, "Domain 2") == INC and "N/A at 2.5" in out and rc == 1)
    ok &= case("G4 2.1 No goes to 2.4: 2.4 Yes — Low", "robins-i", RI_GOOD, {}, "2", LOW,
               "assignment")
    ok &= case("G4 2.1 No, 2.4 No, 2.5 Yes — Moderate", "robins-i", RI_GOOD,
               {"2.4": "N", "2.5": "Y"}, "2", SOME, "assignment")
    ok &= case("G4 2.1 No, 2.4 No, 2.5 No — Serious", "robins-i", RI_GOOD,
               {"2.4": "N", "2.5": "N"}, "2", HIGH, "assignment")
    ok &= case("G5 2.1 No information — unclear, not Low", "robins-i", RI_GOOD,
               {"2.1": "NI"}, "2", SOME, "assignment")
    rc, out = roll("robins-i", RI_GOOD, {"2.5": "N"}, "assignment")
    ok &= _ok("G6 2.1 No and 2.4 Yes with a stray 2.5 No: Low, the 2.5 answer listed "
              "as not reached", _verdict(out, "Domain 2") == LOW
              and "routing does not reach them — not scored: 2.5 'N'" in out and rc == 0)
    ref = (REF_DIR / "robins-i.md").read_text(encoding="utf-8")
    ok &= _ok("robins-i.md no longer says a Yes at 2.1 rules out Low",
              "potential marker of bias but not a\nverdict — it rules out Low" not in ref
              and "2.1 Yes with 2.2 No can be Low" in ref)
    skill = (REF_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
    readme = (REF_DIR.parents[2] / "README.md").read_text(encoding="utf-8")
    ok &= _ok("SKILL.md and README describe 2.1 as a gateway",
              "ROBINS-I 2.1 is the one people get" in skill and "2.1 is a gateway" in readme
              and "it, 2.1–2.4, 3.2" not in readme)

    print("\n[ROBINS-I routing and N/A]")
    rc, out = roll("robins-i", RI_GOOD, {"1.4": "N/A", "1.5": "N/A"}, "assignment")
    ok &= _ok(f"1.2 No reaches 1.4: N/A there is INCOMPLETE, not a verdict (rc {rc!r})",
              _verdict(out, "Domain 1") == INC and "N/A at 1.4" in out and rc == 1)
    p = _write(_fill(A.skeleton(ri, "assignment"), dict(RI_GOOD, **{"1.4": "N/A",
                                                                    "1.5": "N/A"})))
    rc, out = _cli("--verify", str(p), "--tool", "robins-i", "--scope", "assignment")
    ok &= _ok("... and --verify names it", rc == 1 and "N/A WHERE ASKED (1): 1.4" in out)
    ok &= case("1.1 No ends domain 1 (no confounding expected): Low", "robins-i", RI_GOOD,
               {"1.1": "N", "1.2": "N/A", "1.4": "N/A", "1.5": "N/A", "1.6": "N/A"}, "1", LOW,
               "assignment")
    ok &= case("1.2 Yes, 1.3 Yes: the time-varying branch decides (1.7 No — Serious)",
               "robins-i", RI_GOOD, {"1.2": "Y", "1.3": "Y", "1.4": "N/A", "1.5": "N/A",
                                     "1.6": "N/A", "1.7": "N", "1.8": "N/A"}, "1", HIGH,
               "assignment")
    ok &= case("4.1 No with a stray 4.2 Yes: Low", "robins-i", RI_GOOD, {"4.2": "Y"}, "4", LOW,
               "assignment")
    ok &= case("adhering: 4.3 No, appropriate analysis (4.6 Yes) — Moderate", "robins-i",
               RI_GOOD, {"4.3": "N", "4.6": "Y"}, "4", SOME, "adherence")
    ok &= case("adhering: 4.3 No, 4.6 No — Serious", "robins-i", RI_GOOD,
               {"4.3": "N", "4.6": "N"}, "4", HIGH, "adherence")
    all_na = {it["id"]: "N/A" for it in ri.items if it["id"] != "1.1"}
    p = _write(_fill(A.skeleton(ri, "assignment"), dict(all_na, **{"1.1": "N"})))
    rc, out = _cli("--verify", str(p), "--tool", "robins-i", "--scope", "assignment")
    ok &= _ok("an all-N/A ROBINS-I record does not verify complete (3.1 named)",
              rc == 1 and "INVALID" in out and "3.1 'N/A'" in out)
    rc, out = _cli("--rollup", str(p), "--tool", "robins-i", "--scope", "assignment")
    ok &= _ok("... and does not roll up LOW", rc == 1 and _overall(out) == "INCOMPLETE")
    rc, out = _cli("--verify", str(_write(_fill(A.skeleton(ri, "adherence"), RI_GOOD))),
                   "--tool", "robins-i", "--scope", "adherence")
    ok &= _ok("N/A on the conditional questions the routing skips still verifies", rc == 0)

    print("\n[ROBINS-I domains 5 and 6 per Table C]")
    ok &= case("5.1 No, 5.4 Yes (similar across groups) — Low", "robins-i", RI_GOOD,
               {"5.1": "N", "5.4": "Y", "5.5": "N"}, "5", LOW, "assignment")
    ok &= case("5.1 No, 5.5 Yes (robust to missing data) — Low", "robins-i", RI_GOOD,
               {"5.1": "N", "5.4": "N", "5.5": "Y"}, "5", LOW, "assignment")
    rc, out = roll("robins-i", RI_GOOD, {"5.3": "Y", "5.4": "N", "5.5": "N"}, "assignment")
    ok &= _ok("5.3 Yes, 5.4 No, 5.5 No — at least Moderate, the rest left to judgement",
              _verdict(out, "Domain 5") == SOME and "together" in out
              and "judgement the answers do not record" in out)
    ok &= case("5.1 No information — unclear", "robins-i", RI_GOOD, {"5.1": "NI"}, "5", SOME,
               "assignment")
    ok &= case("6.1 Yes, assessors unaware (6.2 No) — Low", "robins-i", RI_GOOD,
               {"6.1": "Y"}, "6", LOW, "assignment")
    ok &= case("6.2 Yes, objective outcome (6.1 No) — Low", "robins-i", RI_GOOD,
               {"6.2": "Y"}, "6", LOW, "assignment")
    ok &= case("6.1 Yes and 6.2 Yes — Serious", "robins-i", RI_GOOD,
               {"6.1": "Y", "6.2": "Y"}, "6", HIGH, "assignment")
    ok &= case("6.1 Yes, 6.2 No information — unclear", "robins-i", RI_GOOD,
               {"6.1": "Y", "6.2": "NI"}, "6", SOME, "assignment")
    ok &= case("6.3 No (assessment not comparable) — Serious on its own", "robins-i", RI_GOOD,
               {"6.3": "N"}, "6", HIGH, "assignment")
    ok &= _ok("ROBINS-I counts unchanged: 34 items, 30 assignment, 32 adherence",
              len(ri.items) == 34 and len(ri.scoped("assignment")) == 30
              and len(ri.scoped("adherence")) == 32)
    conds = {it["id"]: it["cond"]["text"] for it in ri.items if it.get("cond")}
    ok &= _ok(f"every conditional ROBINS-I question has a parsed condition ({len(conds)})",
              set(conds) == {"1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "2.2", "2.3",
                             "2.5", "4.2", "4.6", "5.4", "5.5"})

    print("\n[ROBINS-E: graded No, routing, labels (PMC11098530)]")
    ok &= case("1.1 Weak no — middle tier", "robins-e", RE_GOOD, {"1.1": "WN"}, "1", SOME)
    ok &= case("1.1 Strong no — top tier", "robins-e", RE_GOOD, {"1.1": "Strong no"}, "1", HIGH)
    rc, out = _cli("--verify", str(_write(_fill(A.skeleton(re_, "all"),
                                                dict(RE_GOOD, **{"1.1": "WN"})))),
                   "--tool", "robins-e")
    ok &= _ok(f"'WN' at 1.1 verifies complete (rc {rc!r})", rc == 0)
    rc, out = _cli("--verify", str(_write(_fill(A.skeleton(re_, "all"),
                                                dict(RE_GOOD, **{"2.1": "WN", "1.1": "N"})))),
                   "--tool", "robins-e")
    ok &= _ok("Weak no elsewhere, and a plain No at 1.1, are rejected",
              rc == 1 and "2.1 'WN'" in out and "1.1 'N'" in out)
    ok &= case("3.1 Yes, corrected (3.3 Yes) — not top tier", "robins-e", RE_GOOD,
               {"3.1": "Y", "3.3": "Y"}, "3", SOME)
    ok &= case("3.1 Yes, not corrected (3.3 No) — top tier", "robins-e", RE_GOOD,
               {"3.1": "Y", "3.3": "N"}, "3", HIGH)
    ok &= case("4.1 Yes, analysis corrected (4.2 Yes) — not top tier", "robins-e", RE_GOOD,
               {"4.1": "Y", "4.2": "Y"}, "4", SOME)
    ok &= case("4.1 No information: 4.2 is N/A (the paper's own example)", "robins-e", RE_GOOD,
               {"4.1": "NI"}, "4", SOME)
    ok &= case("5.1 No, evidence of no bias (5.3 Yes) — Low", "robins-e", RE_GOOD,
               {"5.1": "N", "5.3": "Y"}, "5", LOW)
    ok &= case("1.4 No information (variant unknown) — unclear", "robins-e", RE_GOOD,
               {"1.4": "NI"}, "1", SOME)
    rc, out = roll("robins-e", {i["id"]: "N/A" for i in re_.items}, {})
    ok &= _ok("an all-N/A ROBINS-E record is not LOW", rc == 1 and _overall(out) == "INCOMPLETE")
    rc, out = roll("robins-e", RE_GOOD, {})
    ok &= _ok("domain 3 is named for selection into the study or the analysis; a Low domain 1 "
              "carries the uncontrolled-confounding caveat",
              "or into the analysis" in re_.domains["3"]
              and re.search(r"Domain 1 \([^)]*\): LOW .*uncontrolled confounding", out)
              is not None)

    print("\n[QUADAS-2: applicability per domain 1-3, N/A only at 2.2]")
    q2 = tools["quadas2"]
    ok &= _ok("QUADAS-2 signalling questions per domain are 3/2/2/4",
              [len([i for i in q2.items if i["domain"] == d]) for d in "1234"] == [3, 2, 2, 4])
    yes = {i["id"]: "Yes" for i in q2.items}
    sk = _fill(A.skeleton(q2, "all"), yes)
    rc, out = _cli("--verify", str(_write(sk)), "--tool", "quadas2")
    ok &= _ok(f"all Yes without applicability does not verify complete (rc {rc!r})",
              rc == 1 and "APPLICABILITY NOT RECORDED: Domain 1, Domain 2, Domain 3" in out)
    rc, out = _cli("--rollup", str(_write(sk)), "--tool", "quadas2")
    ok &= _ok("... and the rollup says so and exits 1",
              rc == 1 and "domain 1 — Patient selection: NOT RECORDED" in out)
    filled = re.sub(r"(\*\*Domain [123] applicability:\*\*) Low / High / Unclear",
                    r"\1 Low", sk)
    filled = filled.replace("**Domain 1 applicability:** Low", "**Domain 1 applicability:** High")
    rc, out = _cli("--verify", str(_write(filled)), "--tool", "quadas2")
    ok &= _ok("with the three applicability lines filled it verifies", rc == 0)
    rc, out = _cli("--rollup", str(_write(filled)), "--tool", "quadas2")
    ok &= _ok("... and the rollup reports them (overall high concern) with exit 0",
              rc == 0 and "domain 1 — Patient selection: High" in out
              and "overall applicability: high concern" in out)
    table = sk + ("\n\n| Domain | Risk of bias | Applicability concerns |\n|---|---|---|\n"
                  "| 1. Patient selection | Low | Low |\n| Domain 2 | Low | Unclear |\n"
                  "| Reference standard | Low | Low |\n")
    rc, out = _cli("--verify", str(_write(table)), "--tool", "quadas2")
    ok &= _ok("an applicability column in a summary table counts", rc == 0)
    rc, out = _cli("--verify", str(_write(_fill(A.skeleton(q2, "all"),
                                                {i["id"]: "N/A" for i in q2.items}))),
                   "--tool", "quadas2")
    ok &= _ok("all N/A is rejected", rc == 1 and "INVALID" in out and "1.1 'N/A'" in out)
    rc, out = _cli("--verify", str(_write(re.sub(r"(\| 2\.2 \|[^|]*\|) Yes", r"\1 N/A",
                                                 filled))), "--tool", "quadas2")
    ok &= _ok("N/A at 2.2 (no threshold) is accepted", rc == 0)
    ok &= _ok("no QUADAS-2 item is reverse-worded",
              not any("reverse" in A.Instrument.tags(i) for i in q2.items))

    print("\n[QUIPS: 31 prompting items, four levels, N/A only at 3f and 5e]")
    qp = tools["quips"]
    want = [f"{d}{c}" for d, n in ((1, 6), (2, 5), (3, 6), (4, 3), (5, 7), (6, 4))
            for c in "abcdefg"[:n]]
    ok &= _ok("ids are exactly 1a-1f, 2a-2e, 3a-3f, 4a-4c, 5a-5g, 6a-6d",
              [i["id"] for i in qp.items] == want)
    ok &= _ok("answers are Yes / Partly / No / Unclear, Partial and Unsure accepted",
              qp.answers == ["Yes", "Partly", "No", "Unclear"]
              and qp.norm("Partial") == "partly" and qp.norm("Unsure") == "unclear")
    yes = {i["id"]: "Yes" for i in qp.items}
    rc, out = _cli("--verify", str(_write(_fill(A.skeleton(qp, "all"),
                                                {i["id"]: "N/A" for i in qp.items}))),
                   "--tool", "quips")
    ok &= _ok("an all-N/A QUIPS record does not verify", rc == 1 and "INVALID" in out)
    rc, out = roll("quips", {i["id"]: "N/A" for i in qp.items}, {})
    ok &= _ok("... nor roll up LOW", rc == 1 and _overall(out) == "INCOMPLETE")
    rc, out = _cli("--verify", str(_write(_fill(A.skeleton(qp, "all"),
                                                dict(yes, **{"3f": "N/A", "5e": "N/A"})))),
                   "--tool", "quips")
    ok &= _ok("N/A at 3f and 5e (nothing missing, nothing imputed) is accepted", rc == 0)
    rc, out = roll("quips", yes, {"2a": "Partial"})
    ok &= _ok("'Partial' is the middle level; the overall says QUIPS has no combination rule",
              _verdict(out, "Domain 2") == SOME and "publishes no rule" in out and rc == 0)

    print("\n[--migrate carries only what the chosen variant asks]")
    old = ["| # | Signalling question | Answer | Evidence |", "|---|---|---|---|"]
    old_ids = ([f"1.{i}" for i in range(1, 9)] + [f"2.{i}" for i in range(1, 6)]
               + ["3.1", "3.2", "3.3", "4.1", "4.2", "4.3", "5.1", "5.2", "5.3",
                  "6.1", "6.2", "6.3", "7.1", "7.2", "7.3"])
    old += [f"| {i} | {'Was the analysis appropriate to estimate the effect of starting' if i == '4.3' else 'q'} | No | p.1 |"
            for i in old_ids]
    of = _write("\n".join(old))
    rc, out = _cli("--migrate", str(of), "--tool", "robins-i", "--scope", "assignment")
    log = out.split("MIGRATION —")[-1]
    ok &= _ok("assignment scope: 1.x 4.3 (now 4.6, adhering only) is listed as not carried, "
              "not as moved", rc == 0 and "4.3→4.6" not in log and "4.3 'No' (now 4.6)" in log)
    mig = A.read_answers(_write(out.split("MIGRATION —")[0]), ri, "assignment")
    # 28 rows: 4.3 is not carried, 5.3 moves to 5.4, 5.2 'No' splits to 5.2 and 5.3.
    ok &= _ok(f"... and the carried count matches the rows written ({len(mig)} written)",
              len(mig) == 28 and "same id:  25 answer(s)" in log and mig.get("4.1") == "No")
    rc, out = _cli("--migrate", str(of), "--tool", "robins-i", "--scope", "adherence")
    log = out.split("MIGRATION —")[-1]
    ok &= _ok("adherence scope: 1.x 4.1-4.2 are listed as not carried",
              rc == 0 and "4.1 'No', 4.2 'No'" in log and "4.3→4.6" in log)
    return ok


# --------------------------------------------------------------------------- agreement

_Y, _N, _NI, _NA = ("Yes", "Probably yes"), ("No", "Probably no"), "No information", "N/A"


class _Inc(Exception):
    pass


def _ref_rob2(domain: str, a: dict, adherence: bool) -> str:
    """RoB 2 written from the 2019 criteria table (as reproduced in PMC8191126, Table 2) and the
    template routing — independently of rollup_rob2. N/A where the walk needs an answer, or No
    information at 3.2 (not an option of the template), is INCOMPLETE."""
    def need(k: str, na_ok: bool = False) -> str:
        v = a.get(k)
        if v is None or (v == _NA and not na_ok):
            raise _Inc(k)
        return v
    order = ["low", "some", "high"]
    if domain == "1":
        r, c, b = need("1.1"), need("1.2"), need("1.3")
        if c in _N:
            return "high"
        if c == _NI:
            return "high" if b in _Y else "some"
        return "some" if (b in _Y or r in _N) else "low"
    if domain == "2" and adherence:
        aware = not (need("2.1") in _N and need("2.2") in _N)
        problem = (aware and need("2.3", True) in _N + (_NI,)) or need("2.4", True) in _Y + (_NI,) \
            or need("2.5", True) in _Y + (_NI,)
        return ("some" if need("2.6") in _Y else "high") if problem else "low"
    if domain == "2":
        if need("2.1") in _N and need("2.2") in _N or need("2.3") in _N:
            p1 = "low"
        elif a["2.3"] == _NI or need("2.4") in _N:
            p1 = "some"
        else:
            p1 = "some" if need("2.5") in _Y else "high"
        p2 = "low" if need("2.6") in _Y else ("some" if need("2.7") in _N else "high")
        return max(p1, p2, key=order.index)
    if domain == "3":
        if need("3.1") in _Y:
            return "low"
        ev = need("3.2")
        if ev == _NI:
            raise _Inc("3.2")
        if ev in _Y or need("3.3") in _N:
            return "low"
        return "some" if need("3.4") in _N else "high"
    if domain == "4":
        if need("4.1") in _Y or need("4.2") in _Y:
            return "high"
        floor = "some" if a["4.2"] == _NI else "low"
        if need("4.3") in _N or need("4.4") in _N:
            return floor
        return "some" if need("4.5") in _N else "high"
    o, an = need("5.2"), need("5.3")
    if o in _Y or an in _Y:
        return "high"
    if o in _N and an in _N:
        return "low" if need("5.1") in _Y else "some"
    return "some"


def agreement_review(tools: dict) -> bool:
    """Agreement with the metaANAL engine (2026-10), after enumerating every answer combination.

    The enumeration ran this rollup on generated Markdown records against the engine's
    appraisal.check for RoB 2 (both variants), ROBINS-I (both), ROBINS-E, QUADAS-2, QUIPS, AMSTAR 2,
    NOS and GRADE. Two disagreements were this side's: RoB 2 3.2 accepted No information, which
    the 2019 template does not offer there; and No information at a gateway kept the domain at
    the middle tier even when the question that gateway feeds was reached through another answer
    and settled it (ROBINS-E 5.3 Yes, ROBINS-I 5.4/5.5 Yes). The rest are documented
    conventions (N/A where the routing asks: INCOMPLETE here, No information in the engine;
    ROBINS-I/-E Moderate/Serious borderlines: the tier the answers force here, the stricter one
    in the engine's conservative rule; AMSTAR 2: this rollup is the engine's 'weakness'
    convention).
    """
    ok = True
    LOW, SOME, HIGH, INC = "LOW", "SOME CONCERNS / UNCLEAR", "HIGH / SERIOUS", "INCOMPLETE"
    rob2 = tools["rob2"]

    print("\n[agreement: RoB 2 every combination = the 2019 criteria table]")
    vals = ["Yes", "Probably no", _NI, _NA]
    tier = {LOW: "low", SOME: "some", HIGH: "high", INC: "incomplete"}
    for scope in ("assignment", "adherence"):
        for d in "12345":
            its = [it for it in rob2.scoped(scope) if it["domain"] == d]
            # every answer each question offers (Probably yes / No behave as Yes / Probably no)
            offered = [[v for v in vals if rob2.norm(v) in rob2.vocab_of(it)] for it in its]
            bad, n = [], 0
            for combo in itertools.product(*offered):
                a = {it["id"]: v for it, v in zip(its, combo)}
                n += 1
                try:
                    want = _ref_rob2(d, a, scope == "adherence")
                except _Inc:
                    want = "incomplete"
                out = "\n".join(A.rollup_rob2(rob2, a, its))
                m = re.search(rf"Domain {d} \([^)]*\): {_VERDICT}", out)
                got = tier[m.group(1)] if m else None
                if got != want:
                    bad.append((a, want, got))
            ok &= _ok(f"{scope} domain {d}: {n} combinations, {len(bad)} differ from the criteria "
                      f"table{(' — e.g. ' + str(bad[0])) if bad else ''}", not bad)
    ok &= _ok("3.2 offers no 'No information' (the 2019 template has none there)",
              "no information" not in rob2.allowed("3.2", "assignment")
              and rob2.allowed("3.2", "assignment") >= {"yes", "probably yes", "no", "n/a"})
    p = _write(_fill(A.skeleton(rob2, "assignment"), dict(R2_ASSIGN, **{"3.1": "N", "3.2": "NI",
                                                                        "3.3": "N"})))
    rc, out = _cli("--verify", str(p), "--tool", "rob2", "--scope", "assignment")
    ok &= _ok(f"3.2 NI does not verify complete (rc {rc!r})", rc == 1 and "3.2 'NI'" in out)
    rc, out = _cli("--rollup", str(p), "--tool", "rob2", "--scope", "assignment")
    ok &= _ok("... and domain 3 is INCOMPLETE, not a verdict",
              _verdict(out, "Domain 3") == INC and rc == 1)
    ok &= _ok("the skeleton lists 3.2's own answers",
              "3.2: Yes / Probably yes / Probably no / No / N/A" in A.skeleton(rob2, "assignment"))

    print("\n[agreement: No information at a gateway, settled by the question it feeds]")
    ri, re_ = tools["robins-i"], tools["robins-e"]

    def roll(tool, base, over, scope="all"):
        p = _write(_fill(A.skeleton(tools[tool], scope), dict(base, **over)))
        return _cli("--rollup", str(p), "--tool", tool, "--scope", scope)

    def case(label, tool, base, over, domain, want, scope="all"):
        rc, out = roll(tool, base, over, scope)
        got = _verdict(out, f"Domain {domain}")
        return _ok(f"{label}: domain {domain} {want} (got {got}, rc {rc!r})", got == want and rc == 0)

    ok &= case("ROBINS-E 5.1 NI, 5.2 Yes opens 5.3; 5.3 Yes — Low", "robins-e", RE_GOOD,
               {"5.1": "NI", "5.2": "Y", "5.3": "Y"}, "5", LOW)
    ok &= case("ROBINS-E 5.1 NI, 5.2 No — 5.3 not reached, still unclear", "robins-e", RE_GOOD,
               {"5.1": "NI"}, "5", SOME)
    ok &= case("ROBINS-E 5.1 NI, 5.2 Yes, 5.3 No — High", "robins-e", RE_GOOD,
               {"5.1": "NI", "5.2": "Y", "5.3": "N"}, "5", HIGH)
    ok &= case("ROBINS-E 1.4 NI — 1.5 not reached, unclear", "robins-e", RE_GOOD, {"1.4": "NI"},
               "1", SOME)
    ok &= case("ROBINS-I 5.1 NI, 5.2 Yes, 5.4 Yes — Low", "robins-i", RI_GOOD,
               {"5.1": "NI", "5.2": "Y", "5.4": "Y", "5.5": "N"}, "5", LOW, "assignment")
    ok &= case("ROBINS-I 5.1 No, 5.2 NI, 5.5 Yes — Low", "robins-i", RI_GOOD,
               {"5.1": "N", "5.2": "NI", "5.4": "N", "5.5": "Y"}, "5", LOW, "assignment")
    ok &= case("ROBINS-I 5.2 NI with nothing reached — unclear", "robins-i", RI_GOOD,
               {"5.2": "NI"}, "5", SOME, "assignment")
    ok &= case("ROBINS-I 2.1 NI is not settled by 2.5 (2.5 does not depend on 2.1)", "robins-i",
               RI_GOOD, {"2.1": "NI", "2.4": "N", "2.5": "Y"}, "2", SOME, "assignment")
    rc, out = roll("robins-e", RE_GOOD, {"5.1": "NI", "5.2": "Y", "5.3": "Y"})
    ok &= _ok("... the settled gateway is listed as answered, not scored",
              "routing questions answered, not scored: 5.1, 5.2" in out)
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
