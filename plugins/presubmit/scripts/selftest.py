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


# An opinion-format manuscript carrying the mistakes an Annals editorial round
# actually produced: a declared word count over the limit, more references than
# the format allows, an ethics block that belongs on the disclosure form, a
# placeholder, subgroup estimates without confidence intervals, a study named
# only by acronym, the same study described twice, and the authors' own trial
# promoted in the closing. Synthetic throughout — no real manuscript text.
OPINION = """Why Treatment Duration Deserves a Trial
Alex Roe, Kim Lee
Department of Medicine, Example University. Corresponding: ar@example.edu

Word Count: 1400
References: 11
Running head: Treatment duration

Ethics approval: This work was approved by the Example University ethics board and
registered at ClinicalTrials.gov before enrollment.

Consider a patient finishing a long course of therapy. The question is common and, on
present evidence, unanswerable.

In EXAMPLAR, treatment reduced events by a fifth (relative risk, 0.74; 95% CI, 0.61
to 0.89) (1). The relative risk was higher with longer courses (2.13) than with
shorter ones (1.02) (2).

A shorter course was tested in a randomized open-label pilot of 88 adults with chronic
kidney disease, and fewer of them stopped early (3). TBD: add the follow-up numbers
here.

A shorter course was tested in a randomized open-label pilot of 88 adults with chronic
kidney disease, and fewer of them stopped early, which improved adherence (3).

Our own program is enrolling; a randomized comparison is planned, not begun. Future
trials should settle the duration.

References
1. Author A, Author B. A trial of something. Journal of Trials. 2024;1:1-9. doi:10.1000/aaa111
2. Author C. A meta-analysis of harms. Harms Journal. 2023;2:10-20. doi:10.1000/bbb222
3. Author D. A pilot of titration. Pilot Journal. 2025;3:30-40. doi:10.1000/ccc333
4. Author E. Fourth work. Journal Four. 2021;4:1-2. doi:10.1000/ddd444
5. Author F. Fifth work. Journal Five. 2021;5:1-2. doi:10.1000/eee555
6. Author G. Sixth work. Journal Six. 2021;6:1-2. doi:10.1000/fff666
7. Author H. Seventh work. Journal Seven. 2021;7:1-2. doi:10.1000/ggg777
8. Author I. Eighth work. Journal Eight. 2021;8:1-2. doi:10.1000/hhh888
9. Author J. Ninth work. Journal Nine. 2021;9:1-2. doi:10.1000/iii999
10. Author K. Tenth work. Journal Ten. 2021;10:1-2. doi:10.1000/jjj000
11. Author L. Eleventh work. Journal Eleven. 2021;11:1-2. doi:10.1000/kkk111
"""

_DOCX_DOC = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:body><w:p>'
    '<w:commentRangeStart w:id="0"/>'
    '<w:r><w:t>The dose was </w:t></w:r>'
    '<w:ins w:id="1" w:author="An Editor" w:date="2026-01-01T00:00:00Z">'
    '<w:r><w:t>probably </w:t></w:r></w:ins>'
    '<w:del w:id="2" w:author="An Editor" w:date="2026-01-01T00:00:00Z">'
    '<w:r><w:delText>certainly </w:delText></w:r></w:del>'
    '<w:r><w:t>too high.</w:t></w:r>'
    '<w:commentRangeEnd w:id="0"/>'
    '<w:r><w:commentReference w:id="0"/></w:r>'
    '</w:p></w:body></w:document>')

_DOCX_COMMENTS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:comment w:id="0" w:author="An Editor" w:date="2026-01-01T00:00:00Z">'
    '<w:p><w:r><w:t>Please clarify this sentence.</w:t></w:r></w:p>'
    '</w:comment></w:comments>')

_DOCX_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Target="word/document.xml" Type="http://schemas.openxmlformats.'
    'org/officeDocument/2006/relationships/officeDocument"/></Relationships>')


def _docx_with_revisions():
    """A minimal .docx that still carries tracked changes and one comment."""
    import zipfile
    p = Path(tempfile.mktemp(suffix=".docx"))
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("_rels/.rels", _DOCX_RELS)
        z.writestr("word/document.xml", _DOCX_DOC)
        z.writestr("word/comments.xml", _DOCX_COMMENTS)
    return p


def _codes(text, profile_name="generic"):
    tmp = Path(tempfile.mktemp(suffix=".txt"))
    tmp.write_text(text, encoding="utf-8")
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

    # ---- what an editorial round teaches: opinion-format mistakes -----------
    of = _codes(OPINION, "annals")
    ocodes = {f.code for f in of}
    for label, code in [
        ("declared word count over the format limit", "declared-over-limit"),
        ("more references than the format allows", "too-many-references"),
        ("ethics block that belongs on the disclosure form", "discouraged-disclosure"),
        ("trial registration in the manuscript", "registration-in-text"),
        ("placeholder left in the text", "placeholder-left"),
        ("estimate without a confidence interval", "estimate-without-ci"),
        ("study named only by acronym", "acronym-study-undescribed"),
        ("same reference described twice", "duplicate-citation-description"),
        ("authors' own study in the closing", "own-study-in-conclusion"),
    ]:
        passed &= _ok(f"caught: {label}", code in ocodes)

    # the subgroup estimates, not the one that already carries its CI
    naked = {f.message for f in of if f.code == "estimate-without-ci"}
    passed &= _ok("CI check is parenthetical-level, not sentence-level",
                  any("2.13" in m for m in naked) and any("1.02" in m for m in naked)
                  and not any("0.74" in m for m in naked))

    # no abstract and no keywords is correct for this format, not an error
    passed &= _ok("opinion format is not asked for an abstract",
                  "no-abstract" not in ocodes and "no-keywords" not in ocodes)

    # ---- a .docx that still carries revisions and comments ------------------
    dp = _docx_with_revisions()
    import pc_docx
    facts = pc_docx.inspect(dp)
    passed &= _ok(f"docx revisions seen (ins={facts.insertions}, del={facts.deletions}, "
                  f"comments={facts.comments})",
                  facts.insertions == 1 and facts.deletions == 1 and facts.comments == 1
                  and facts.revision_authors == ["An Editor"])

    class _D:
        pass
    d = _D()
    d.path, d.text, d.paragraphs, d.sections = dp, "The dose was too high.", [], {}
    dcodes = {f.code for f in C.check_submission(d, pc_lib.load_profile("annals"))}
    passed &= _ok("caught: tracked changes left in the .docx",
                  "tracked-changes-left" in dcodes)
    passed &= _ok("caught: comments left in the .docx", "comments-left" in dcodes)

    # a title page that declares "References: 10" is not a References heading
    tmp2 = Path(tempfile.mktemp(suffix=".txt"))
    tmp2.write_text("Title Here\nWord Count: 900\nReferences: 3\n\nBody text here.\n\n"
                    "References\n1. Author A. Work. Journal. 2024;1:1-2.\n", encoding="utf-8")
    d2 = pc_extract.load(tmp2)
    passed &= _ok("title-page declaration is not read as a section heading",
                  len(C._reference_entries(d2)) == 1)

    print(f"\n{'ALL PASSED' if passed else 'FAILURES PRESENT'}")
    return passed


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
