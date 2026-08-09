#!/usr/bin/env python3
"""Self test: plant ten known mistakes in a manuscript and assert every one is
caught (and that a clean manuscript passes). Exit 0 = pass.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pc_lib
import pc_checks as C
import pc_extract

# A manuscript missing Methods, missing email, missing COI + funding, with a
# duplicate reference (same DOI), a reference with no year, an out-of-range
# citation, an uncited reference, and a repeated word.
BAD = """A Study of Hearts in Mice
John Smith, Jane Doe
Department of Cardiology, Example University

Abstract
This is a short abstract about hearts.

Keywords
heart, mice, cardiology, study

Introduction
The the study begins here. We cite the first work [1] and the second [2].
We also cite a reference that does not exist [99].

Results
Hearts were observed.

Discussion
This matters.

Conclusions
Done.

References
1. Smith J, Doe A. A study of hearts. Cardiology Journal. 2019;10:1-5. doi:10.1000/abc123
2. Brown B. Another paper without a year. Some Journal. doi:10.1000/xyz789
3. Smith J, Doe A. A study of hearts. Cardiology Journal. 2019;10:1-5. doi:10.1000/abc123
"""

# A clean-enough manuscript that should produce no ERRORs.
GOOD = """Cardiac Outcomes After Intervention
John Smith, Jane Doe
Department of Cardiology, Example University. Corresponding: js@example.edu

Abstract
""" + ("This study evaluates cardiac outcomes in a controlled cohort. " * 20) + """

Keywords
heart, outcomes, cardiology, intervention

Introduction
We cite the first work [1] and the second [2].

Methods
We did methods.

Results
We found results.

Discussion
We discuss.

Conclusions
We conclude.

Conflict of Interest
The authors declare no conflicts of interest.

Funding
This research received no specific funding.

References
1. Smith J, Doe A. A study of hearts. Cardiology Journal. 2019;10:1-5. doi:10.1000/abc123
2. Brown B. Vessels and flow. Vascular Reports. 2020;5:22-30. doi:10.1000/xyz789
"""


def _codes(text, profile_name="generic"):
    tmp = Path(tempfile.mktemp(suffix=".txt"))
    tmp.write_text(text)
    doc = pc_extract.load(tmp)
    prof = pc_lib.load_profile(profile_name)
    findings = []
    for fn in C.ALL_CHECKS.values():
        findings.extend(fn(doc, prof))
    return findings


def _ok(name, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    return cond


def run():
    print("presubmit selftest")
    passed = True

    findings = _codes(BAD)
    codes = {f.code for f in findings}
    expect = [
        ("missing Methods section", "missing-section"),
        ("no corresponding email", "no-corresponding-email"),
        ("duplicate DOI", "ref-dup-doi"),
        ("duplicate reference text", "ref-duplicate"),
        ("reference without a year", "ref-no-year"),
        ("citation out of range [99]", "cite-out-of-range"),
        ("uncited reference", "ref-uncited"),
        ("repeated word", "repeated-word"),
        ("missing conflict-of-interest", "missing-conflict-of-interest"),
        ("missing funding", "missing-funding"),
    ]
    for label, code in expect:
        passed &= _ok(f"caught: {label}", code in codes)

    # sections detected correctly (title/authors NOT treated as sections)
    tmp = Path(tempfile.mktemp(suffix=".txt")); tmp.write_text(BAD)
    doc = pc_extract.load(tmp)
    order = doc.sections.get("_order", [])
    passed &= _ok(f"sections parsed = {order}",
                  "abstract" in order and "references" in order
                  and "a study of hearts in mice" not in order)
    passed &= _ok("author block kept in preamble (email check meaningful)",
                  "Example University" in doc.sections.get("_preamble", ""))

    # GOOD manuscript: zero ERRORs
    gf = _codes(GOOD)
    errs = [f for f in gf if f.severity == pc_lib.ERROR]
    passed &= _ok(f"clean manuscript has no ERRORs (got {len(errs)}: "
                  f"{[f.code for f in errs]})", len(errs) == 0)

    print(f"\n{'ALL PASSED' if passed else 'FAILURES PRESENT'}")
    return passed


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
