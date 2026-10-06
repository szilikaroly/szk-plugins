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
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appraise as A  # noqa: E402
import checklist as C  # noqa: E402


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
    rv = "\n".join(A.rollup_signalling(rob2, dict(clean, **{"1.3": "Yes"}),
                                       rob2.scoped("assignment")))
    ok &= _ok("a reverse-worded flag is reported as the Yes it was",
              "'Yes' or 'Probably yes' at 1.3" in rv
              and "'No' or 'Probably no' at 1.3" not in rv)

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

    print(f"\n{'ALL PASSED' if ok else 'FAILURES PRESENT'}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
