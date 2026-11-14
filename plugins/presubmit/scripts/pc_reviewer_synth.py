"""Reviewer-anticipation rules, cohorts 10-13 and two later rounds.

Built from referee and editor reports that were not yet in the rules. Every
earlier cohort was a review, an opinion piece, a survey or a simulated model; these are the first where the authors ran their own pooling,
so most rules here sit behind `_own_meta_analysis`. Codes:

  L-R1.M<n>, L-R1.m<n>, L-R2.<n>, L2-R1.<n>  cohort 10, evidence synthesis with
                                              pooled estimates, 2 rounds
  N-R1.<n>, N-R2.<n>, N-Ed.<n>               cohort 11, a re-analysis with pooled
                                              estimates
  W-R1.<n>, W-R2.<n>, W-R3.<n>               cohort 12, narrative review with an
                                              embedded pooled analysis
  E-R1.<n>, E-Ed.<n>                         cohort 13, a second referee and the
                                              editor on the cohort 9 model paper
  M2-R2.<n>                                  cohort 3, second round

The reports are confidential. Provenance is by neutral code only; no referee
wording, manuscript identifier or title belongs in this file.

Self-contained, like cohorts 8 and 9: imports nothing from the other reviewer
modules. All patterns are English; a Hungarian manuscript stays silent here,
which is silence, not a pass. None of these rules has been blind-tested on the
reports it came from; see `references/reviewer-patterns.md`.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from pc_lib import F, ERROR, WARN, INFO, word_count

CAT = "reviewer"

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ſ\d\[\(\"“])")


def sentences(text):
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            out.extend([s.strip() for s in _SENT_SPLIT.split(line) if s.strip()] or [line])
    return out


def sec(doc, *keys):
    for k in keys:
        v = doc.sections.get(k)
        if v:
            return v
    return ""


def body_of(doc):
    ref = doc.sections.get("references", "")
    if ref and ref in doc.text:
        return doc.text.split(ref)[0]
    return doc.text


def title_of(doc):
    for line in doc.sections.get("_preamble", "").splitlines():
        if len(line.strip()) > 25:
            return line.strip()
    return ""


def abstract_of(doc):
    """The Abstract section, or a run-in 'Abstract:' paragraph as journal-formatted
    files have it, or the first long paragraph of the preamble."""
    a = sec(doc, "abstract")
    if a:
        return a
    pre = doc.sections.get("_preamble", "")
    for line in pre.splitlines():
        if re.match(r"\s*Abstract\b", line, re.I) and len(line.split()) > 30:
            return line
    for line in pre.splitlines():
        if len(line.split()) >= 100:
            return line
    return ""


def has(text, *patterns):
    return any(re.search(p, text or "", re.I) for p in patterns)


def cited(s):
    return bool(re.search(r"\[\s*\d|\(\s*\d{4}\s*\)|\bet al\b|\(\s*[A-Z][a-z]+,"
                          r"|\(\s*\d{1,3}(\s*[,–-]\s*\d{1,3})*\s*\)", s))


def _q(s, n=130):
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def is_review(doc):
    head = title_of(doc) + " " + abstract_of(doc) + " " + doc.text[:600]
    return bool(re.search(r"\breview\b|\bscoping\b|\boverview\b|\bsynthesis\b", head, re.I))


# ── the gate most rules lean on ────────────────────────────────────────

# Named machinery, because "pooled" alone is what every narrative review says
# when it reports someone else's meta-analysis.
_OWN_POOLING = (r"\bmetafor\b|\bRevMan\b|\bmeta(?:for)?::|\bREML\b|restricted maximum likelihood|"
                r"DerSimonian|Mantel[- ]Haenszel|inverse[- ]variance|Hartung|"
                r"\b(?:we|was|were) (?:then )?pooled\b|exploratory meta-analysis|"
                r"random[- ]effects? (?:meta-analys\w+|models?) (?:was|were)\b|"
                r"(?:was|were) (?:fitted|pooled|combined) (?:using|with|by|in) (?:a )?random")


def _own_meta_analysis(doc):
    """The authors ran the pooling themselves, as opposed to reporting pooled
    estimates from other people's papers."""
    body = body_of(doc)
    if not has(body, r"meta-?analy"):
        return False
    return bool(re.search(_OWN_POOLING, sec(doc, "methods") or body, re.I)
                or re.search(r"exploratory meta-analysis|\bwe pooled\b", body, re.I))


_NARRATIVE = r"\bnarrative review\b|\bnon-?systematic\b|\brapid (?:review|synthesis)\b"
_EXPLORATORY = (r"\bexplorator\w+|\bdirectional\b|\bunstable\b|\bcaution\w*|\bimprecise\b|"
                r"\binsufficient\b|\bshould not be\b|\bpreliminary\b|\bhypothesis-generating\b|"
                r"\bfragile\b|\bnot enough\b|\bunderpowered\b")


# ── pooled estimates ───────────────────────────────────────────────────

_MIXED_MEASURE = (
    r"\brisk/odds ratio|\bodds/risk ratio|\bRR/OR\b|\bOR/RR\b|"
    r"\b(?:RRs?|risk ratios?|relative risks?)\s+(?:and|or|with)\s+(?:ORs?|odds ratios?)\b[^.]{0,60}"
    r"\b(?:pooled|combined|together|same|single|one)\b|"
    r"\b(?:ORs?|odds ratios?)\s+(?:and|or|with)\s+(?:RRs?|risk ratios?|relative risks?)\b[^.]{0,60}"
    r"\b(?:pooled|combined|together|same|single|one)\b|"
    r"\b(?:pooled|combined)\b[^.]{0,60}\b(?:ORs?|odds ratios?)\s+(?:and|or|with)\s+"
    r"(?:RRs?|risk ratios?|relative risks?)\b|"
    r"\b(?:pooled|combined)\b[^.]{0,60}\b(?:RRs?|risk ratios?|relative risks?)\s+(?:and|or|with)\s+"
    r"(?:ORs?|odds ratios?)\b")


def _effect_measures_mixed(doc):
    """N-R1.4, N-R2.4, L-R1.m1: odds ratios and risk ratios entered into one
    pool. Two referees independently, and the first also objected to the
    absolute effect worked out from it. Conversion to one measure is the guard;
    RR-only and OR-only sensitivity pools did not satisfy the referee."""
    if not _own_meta_analysis(doc):
        return []
    body = body_of(doc)
    if has(body, r"convert\w*[^.]{0,50}(?:ORs?|odds ratios?)[^.]{0,30}(?:to|into)[^.]{0,20}"
                 r"(?:RRs?|risk ratios?|relative risks?)", r"\bZhang\s*(?:and|[–-])\s*Yu\b",
           r"(?:ORs?|odds ratios?)\)?[^.]{0,40}\b(?:were|was) converted\b"):
        return []
    for s in sentences(body):
        m = re.search(_MIXED_MEASURE, s, re.I)
        if m and not has(s, r"\bnever\b", r"\bnot\b", r"\bseparately\b"):
            return [F(CAT, WARN, "effect-measures-mixed",
                      f"Risk ratios and odds ratios appear to share one pool: “{_q(s)}”. "
                      "They diverge when the outcome is common.",
                      where="methods",
                      fix="Name one effect measure for the principal analysis, convert the others, "
                          "and report the alternatives as sensitivity analyses. Any absolute effect "
                          "or number needed to treat should come from the single measure.")]
    return []


def _heterogeneity(doc):
    """L-R1.M2: a substantial I² put down to study size rather than explored.
    The guard is a named exploration; the trigger is a high I² with none, or an
    explicit attribution to precision."""
    if not _own_meta_analysis(doc):
        return []
    body = body_of(doc)
    for s in sentences(body):
        if (has(s, r"\bI[²2]\b", r"heterogeneity")
                and has(s, r"reflect\w*\s+(?:\w+\s+){0,3}precision", r"precision rather than",
                        r"(?:due|owing|attributable) to (?:the )?(?:\w+\s+){0,2}(?:large|larger|big) "
                        r"(?:studies|cohorts)")):
            return [F(CAT, WARN, "heterogeneity-unexplored",
                      f"Heterogeneity is attributed to study size or precision: “{_q(s)}”.",
                      where="results",
                      fix="Explore it formally (population, exposure measure, follow-up, adjustment, "
                          "outcome ascertainment) before explaining it.")]
    highs = [int(m) for m in re.findall(r"\bI[²2]\s*(?:=|of|was|:)\s*(\d{2,3})(?:\.\d+)?\s*%", body)]
    if highs and max(highs) >= 50 and not has(
            body, r"subgroup", r"meta-regression", r"moderator", r"leave-one-out",
            r"sensitivity analys", r"influence (?:analysis|diagnostics)"):
        return [F(CAT, WARN, "heterogeneity-unexplored",
                  f"I² reaches {max(highs)}% and no subgroup, moderator or sensitivity analysis "
                  "is reported.", where="results",
                  fix="State how the between-study variation was explored.")]
    return []


def _egger_null(doc):
    """L-R1.m6: a non-significant small-study test read as no publication bias."""
    if not has(body_of(doc), r"meta-?analy"):
        return []
    ss = sentences(body_of(doc))
    for i, s in enumerate(ss):
        if not has(s, r"\bEgger", r"funnel"):
            continue
        if not has(s, r"\bno (?:evidence|sign|indication)\b", r"\babsence of\b",
                   r"\bnon-?significant\b", r"\bnot significant\b", r"\bdid not (?:suggest|indicate|show)\b"):
            continue
        near = " ".join(ss[i:i + 2])
        if has(near, r"\bpower", r"\bfew\b", r"\bfewer than\b", r"cannot (?:be )?exclud",
                r"does not (?:exclude|rule out)", r"\blimited\b", r"\binsensitive\b", r"should not be"):
            continue
        return [F(CAT, INFO, "egger-null-as-absence",
                  f"A non-significant small-study test, with no word on its power: “{_q(s)}”.",
                  where="results",
                  fix="Say that the test has low power at this number of studies and that a "
                      "non-significant result does not show publication bias is absent.")]
    return []


_FEW = (r"\bk\s*=\s*[234]\b|\b(?:only\s+)?(?:two|three|four|2|3|4)\s+(?:\w+\s+){0,2}"
        r"(?:trials|RCTs|studies|cohorts)\b")


def _few_studies(doc):
    """W-R1.1, W-R1.4, W-R3.4, L-R2.7, L-R1.M4: a pooled figure from two to
    four studies presented as an estimate. Three of three referees on one
    paper, and both on another, asked for it to be labelled."""
    if not _own_meta_analysis(doc):
        return []
    ss = sentences(body_of(doc))
    for i, s in enumerate(ss):
        if not re.search(_FEW, s, re.I):
            continue
        if not has(s, r"\bpool\w*", r"\bmeta-analys", r"\bcombin\w+", r"random[- ]effects"):
            continue
        if not has(s, r"\b(?:RR|OR|HR|MD|SMD)\b\s*[=:,]?\s*\d", r"\d\.\d+\s*\(?\s*95"):
            continue
        near = " ".join(ss[max(0, i - 1):i + 2])
        if has(near, _EXPLORATORY):
            continue
        return [F(CAT, WARN, "few-studies-pooled-unqualified",
                  f"A pooled estimate from very few studies with no qualifier: “{_q(s)}”.",
                  where="results",
                  fix="Label it exploratory, or lead with the separate study results.")]
    return []


def _dl_estimator(doc):
    """W-R3.4: DerSimonian-Laird with a handful of studies, where it estimates
    between-study variance badly."""
    if not _own_meta_analysis(doc):
        return []
    body = body_of(doc)
    if not has(body, r"DerSimonian"):
        return []
    if has(body, r"Hartung", r"\bHKSJ\b", r"\bREML\b", r"Paule", r"restricted maximum"):
        return []
    if not re.search(_FEW, body, re.I):
        return []
    return [F(CAT, INFO, "dl-estimator-few-studies",
              "DerSimonian-Laird pooling of very few studies, with no adjusted interval or "
              "alternative estimator.", where="methods",
              fix="Add a Hartung-Knapp interval or a REML fit as a sensitivity analysis, "
                  "or discuss the imprecision.")]


def _meta_in_narrative(doc):
    """W-R1.3: a formal pooled analysis inside a self-described narrative review
    needs its own justification, and the referee asked for code and
    prespecified outcome definitions."""
    if not _own_meta_analysis(doc):
        return []
    head = title_of(doc) + " " + abstract_of(doc) + " " + sec(doc, "methods")
    if not has(head, _NARRATIVE):
        return []
    missing = []
    body = body_of(doc)
    if not has(body, r"eligibility|inclusion criteria|included if"):
        missing.append("eligibility criteria")
    if not has(body, r"pre-?specified|a priori"):
        missing.append("prespecified outcome definitions")
    if not has(body, r"\b(?:analysis|statistical|R|source) (?:code|script)", r"\bGitHub\b",
               r"\bZenodo\b", r"osf\.io"):
        missing.append("the analysis code")
    if not missing:
        return []
    return [F(CAT, WARN, "meta-in-narrative-unjustified",
              "A meta-analysis inside a narrative review, with no statement of "
              + ", ".join(missing) + ".", where="methods",
              fix="Justify why a pooled estimate belongs in a narrative review, and give what a "
                  "reader needs to reproduce it.")]


def _outcome_definition(doc):
    """N-R1.5, W-R1.4, W-R2.5, W-R3.4: outcomes pooled under different
    definitions. Three referees on one paper named the same pair of endpoints."""
    if not _own_meta_analysis(doc):
        return []
    body = body_of(doc)
    pat = (r"\bas defined by (?:the |each )?(?:individual )?(?:study|studies|trial|trials|authors)\b|"
           r"\bas (?:each|the) (?:study|trial) defined\b|"
           r"\bidentical\b[^.]{0,50}\b(?:end ?points?|outcomes?)\b")
    for s in sentences(body):
        if re.search(pat, s, re.I):
            if has(body, r"(?:subgroup|stratif\w+|sensitivity)[^.]{0,60}(?:definition|criteria)",
                   r"(?:definition|criteria)[^.]{0,60}(?:subgroup|stratif\w+|sensitivity)"):
                return []
            return [F(CAT, WARN, "outcome-definition-not-harmonised",
                      f"Outcome definitions are taken as they come: “{_q(s)}”.",
                      where="methods",
                      fix="Analyse by definition, or say what mixing them does to the pooled "
                          "estimate. Endpoints that are only similar should not be called identical.")]
    return []


def _pooling_minimum(doc):
    """L-R1.m3: a minimum number of studies for pooling, asserted with no source."""
    if not _own_meta_analysis(doc):
        return []
    for s in sentences(sec(doc, "methods") or body_of(doc)):
        if (has(s, r"\b(?:at least|minimum of|fewer than|≥)\s*(?:two|three|2|3)\b", r"\bk\s*≥\s*[23]\b")
                and has(s, r"\bpool") and has(s, r"stud|trial|cohort|\bk\b") and not cited(s)):
            return [F(CAT, INFO, "pooling-minimum-unsupported",
                      f"A minimum study count for pooling with no source: “{_q(s)}”.",
                      where="methods",
                      fix="Give the reason and a methodological reference; no such threshold "
                          "is universally accepted.")]
    return []


# ── sensitivity of the headline ────────────────────────────────────────

_FRAGILE = (r"\bno longer (?:statistically )?significant\b|"
            r"\b(?:interval|CI)s?\s+(?:then\s+)?(?:cross\w*|includ\w+|span\w*)\s+(?:the\s+)?(?:null|one|1(?:\.0+)?)\b|"
            r"\bcross(?:es|ed|ing)? the null\b|\blost (?:statistical )?significance\b|"
            r"\beffect (?:disappear|vanish)\w*\b|\bbecomes? (?:non-?significant|unpoolable)\b|"
            r"\bmoderator (?:effect )?disappear\w*\b")


def _intervals(s):
    """(low, high) pairs printed as 0.51–1.22, 0.51 to 1.22 or 0.51-1.22."""
    return [(float(a), float(b)) for a, b in
            re.findall(r"\b(\d{1,2}\.\d{1,3})\s*(?:[–—-]|to)\s*(\d{1,2}\.\d{1,3})\b", s)]


def _fragile_not_in_abstract(doc):
    """N-R1.8, N-R2.5, L-R1.M4, L-R1.M5: a sensitivity analysis undoes the
    result, the body says so, and the abstract does not."""
    if not _own_meta_analysis(doc):
        return []
    abstract = abstract_of(doc)
    if not abstract or has(abstract, r"sensitiv", r"\bfragile\b", r"\bnot robust\b", r"no longer",
                           r"cross\w* the null", r"\bexcluding\b", r"\bwithout\b", r"\bwhen \w+ (?:was|were) removed\b"):
        return []
    ss = sentences(sec(doc, "results") + "\n" + sec(doc, "discussion")) or sentences(body_of(doc))
    for i, s in enumerate(ss):
        # a named sensitivity step: a bare "without" also matched "women without
        # cancer" in a cited cohort
        if not has(s, r"sensitivity analys", r"leave-one-out", r"\bafter (?:removing|excluding|omitting)\b",
                   r"\bexcluding\b", r"\bwithout (?:them|these|those|the (?:\w+ ){0,2}(?:trials?|stud\w+|cohorts?))\b"):
            continue
        flipped = any(lo < 1 < hi for lo, hi in _intervals(s)) and any(
            not lo <= 1 <= hi for lo, hi in _intervals(" ".join(ss[max(0, i - 2):i + 1])))
        if re.search(_FRAGILE, s, re.I) or flipped:
            return [F(CAT, WARN, "fragile-result-not-in-abstract",
                      f"The result does not survive a sensitivity analysis, and the abstract does "
                      f"not say so: “{_q(s)}”.", where="abstract",
                      fix="Carry the sensitivity result into the Abstract and the Conclusions.")]
    return []


def _ci_false_precision(doc):
    """N-R1.8: a third decimal whose only work is to keep the interval off 1. The
    two limits printed to different precision is the tell: a per-unit odds ratio
    legitimately needs three decimals, and then has them on both limits."""
    for s in sentences(body_of(doc)):
        m = (re.search(r"\b\d\.\d{2}\s*(?:[–—-]|to)\s*(0\.99\d)\b", s)
             or re.search(r"\b(1\.00[1-9])\s*(?:[–—-]|to)\s*\d\.\d{2}\b(?!\d)", s))
        if m:
            return [F(CAT, WARN, "ci-bound-false-precision",
                      f"A confidence limit at {m.group(1)} is printed to a third decimal, next to "
                      f"the null: “{_q(s)}”.", where="results",
                      fix="Report estimates and limits to two decimals throughout, and describe "
                          "an interval that touches 1 as compatible with no effect.")]
    return []


def _post_hoc(doc):
    """N-R1.9, N-R2.m1, N-R1.7, L-R1.m8: many analyses defined after the data
    were in, and an abstract that does not separate them; or a post hoc rule
    behind the principal estimate."""
    out = []
    body = body_of(doc)
    n = len(re.findall(r"\bpost[- ]hoc\b", body, re.I))
    for s in sentences(body):
        if (has(s, r"\bpost[- ]hoc\b") and not has(s, r"\bnot\b", r"\bsensitivity\b")
                and has(s, r"\b(?:primary|principal|main) (?:analysis|estimate|result)\b[^.]{0,30}\bpost[- ]hoc\b",
                        r"\bpost[- ]hoc\b[^.]{0,30}\b(?:primary|principal|main) (?:analysis|estimate|result)\b",
                        r"\bwas (?:used|chosen|selected) \(post[- ]hoc\)")):
            out.append(F(CAT, WARN, "post-hoc-as-primary",
                         f"A post hoc choice behind the principal analysis: “{_q(s)}”.",
                         where="methods",
                         fix="Make the prespecified analysis primary, or give the alternatives "
                             "equal status."))
            break
    abstract = abstract_of(doc)
    if n >= 3 and abstract and not has(abstract, r"\bpost[- ]hoc\b", r"pre-?specified",
                                       r"\bexplorator", r"pre-?registered"):
        out.append(F(CAT, WARN, "post-hoc-unseparated-in-abstract",
                     f"'Post hoc' appears {n} times in the text and the abstract does not separate "
                     "prespecified from exploratory analyses.", where="abstract",
                     fix="Mark in the Abstract which results are prespecified."))
    return out


# ── review design, methods and automation ──────────────────────────────

_DESIGN = [
    (r"\bnon-?systematic\b|\brapid (?:review|synthesis)\b", "non-systematic or rapid"),
    (r"\bre-?analys[ie]s\b", "re-analysis"),
    (r"\bscoping review\b", "scoping"),
    (r"\bnarrative review\b", "narrative"),
    (r"\bumbrella review\b", "umbrella"),
]


def _design_label(doc):
    """L-R2.1, L-R2.9, N-R1.1: the Methods say what the review is, and the
    title and abstract do not. The label belongs where a reader meets it first."""
    methods = sec(doc, "methods")
    title, abstract = title_of(doc), abstract_of(doc)
    if not methods or not abstract or not title:
        return []
    if (has(abstract, r"\b(?:non-?systematic|narrative|rapid|scoping|umbrella) (?:review|synthesis)\b")
            and not has(title, r"\breview\b", r"\bsynthesis\b", r"\bmeta-?analys", r"\boverview\b")):
        return [F(CAT, WARN, "review-design-label-missing",
                  "The abstract says this is a review, and the title does not.", where="title",
                  fix="Say in the title that this is a review or evidence synthesis.")]
    for pat, label in _DESIGN:
        ms = [s for s in sentences(methods)
              if re.search(pat, s, re.I) and has(s, r"\bthis\b|\bwe\b|\bour\b|\bthe present\b|\bis a\b|\bwas\b")
              and not cited(s)]
        if ms and not has(title + " " + abstract, pat):
            return [F(CAT, WARN, "review-design-label-missing",
                      f"The Methods describe a {label} design and the title and abstract do not "
                      f"name it: “{_q(ms[0])}”.", where="abstract",
                      fix="Name the design in the title or abstract, and keep it consistent "
                          "through the Conclusions.")]
    return []


# The machine has to be doing the work. A disclosure sentence saying a named author
# verified AI-assisted output is the guard, and it read as the trigger on four files.
_AUTOMATED = (r"\b(?:extraction|screening) pipeline\b|"
              r"\b(?:screened|extracted|classified|appraised)\b[^.]{0,40}\b(?:by|with|using)\b[^.]{0,40}"
              r"\b(?:LLM|large language models?|language models?|generative AI|scripts?|algorithm)\b|"
              r"\b(?:LLM|large language models?|generative AI)\b[^.]{0,40}\b(?:screened|extracted|"
              r"screening of|extraction of)\b")


def _automated_pipeline(doc):
    """L-R2.5, N-R1.10, N-R2.2: screening or extraction by machine. Referees
    want the check on it measured, and want to know whether a human decided
    independently or only read the machine's answer."""
    if not is_review(doc):
        return []
    methods = sec(doc, "methods") or body_of(doc)
    hit = next((s for s in sentences(methods) if re.search(_AUTOMATED, s, re.I)), None)
    if not hit:
        return []
    out = []
    if not has(methods, r"(?:verified|checked|validated)\s+(?:all|every|each)\b",
               r"(?:manual|hand|independent)\w*[- ]?(?:\w+\s+){0,2}(?:verif|check|validat|re-?extract)\w*[^.]{0,80}\d",
               r"\d[^.]{0,80}(?:manual|hand|independent)\w*[- ]?(?:\w+\s+){0,2}(?:verif|check|validat)\w*",
               r"\bkappa\b", r"\bpercent agreement\b", r"\berror rate\b"):
        out.append(F(CAT, WARN, "extraction-pipeline-unvalidated",
                     f"Automated screening or extraction with no measured check: “{_q(hit)}”.",
                     where="methods",
                     fix="Say how many items were verified by hand, what errors were found, and "
                         "whether a missed item could change a conclusion."))
    if not has(methods, r"\bblind\w*\b", r"independently (?:of|from|before)", r"without (?:seeing|access to)",
               r"\bbefore (?:seeing|viewing|reading)\b"):
        out.append(F(CAT, INFO, "ai-screening-independence-unstated",
                     "Nothing says whether human reviewers decided independently or reviewed the "
                     "automated decision.", where="methods",
                     fix="State which, because the two carry different risks of automation bias, "
                         "and describe adjudication."))
    return out


def _rob_inherited(doc):
    """N-R1.6, N-R2.3: risk-of-bias judgments carried over from earlier reviews
    alongside ones made fresh."""
    if not has(body_of(doc), r"meta-?analy|systematic review"):
        return []
    for s in sentences(sec(doc, "methods") or body_of(doc)):
        if (has(s, r"risk[- ]of[- ]bias|\bRoB\b|Newcastle") and not re.match(r"\s*(?:Table|Figure)\b", s)
                and has(s, r"\bmapped\b", r"\btransferred\b", r"\binherited\b", r"\bcarried over\b",
                        r"\bderived from published\b", r"\btaken from (?:the )?(?:source|published|original)\b",
                        r"\bas published\b", r"\bfrom (?:the )?source (?:review|meta)")):
            return [F(CAT, WARN, "rob-inherited-from-sources",
                      f"Risk-of-bias judgments taken over from earlier reviews: “{_q(s)}”.",
                      where="methods",
                      fix="Reassess the studies behind the main findings with one tool, or lower "
                          "and qualify the certainty rating where the assessment is incomplete.")]
    return []


_METHOD_WEAKNESS = [
    (r"\bsingle[- ]reviewer\b|\bone reviewer\b",
     r"\bsingle[- ]reviewer|\bone reviewer|\bdual review|\bsecond reviewer|\bindependent review",
     "single-reviewer screening"),
    (r"\bretrospectively registered\b|\bregistered retrospectively\b|\bnot (?:prospectively )?registered\b|\bwithout (?:a )?prospective regist",
     r"regist", "absent or retrospective registration"),
]


def _weakness_not_carried(doc):
    """L-R2.2, N-R2.m5: a weakness stated once in the Methods and absent where
    the results are interpreted."""
    methods = sec(doc, "methods")
    later = sec(doc, "discussion") + "\n" + sec(doc, "limitations") + "\n" + sec(doc, "conclusions")
    if not methods or len(later.strip()) < 200 or not is_review(doc):
        return []
    for pat, carry, label in _METHOD_WEAKNESS:
        if has(methods, pat) and not has(later, carry):
            return [F(CAT, WARN, "methods-limitation-not-carried",
                      f"The Methods mention {label}, and the Discussion and Conclusions do not.",
                      where="discussion",
                      fix="Carry the limitation into the interpretation.")]
    return []


def _narrative_standard(doc):
    """W-R3.1: a narrative review reporting against no quality standard. The
    gate is a declared narrative review with no search string, because the
    objection was opacity, not the missing acronym."""
    head = title_of(doc) + " " + abstract_of(doc)
    if not has(head, r"\bnarrative review\b"):
        return []
    body = body_of(doc)
    if has(body, r"\bSANRA\b", r"search (?:string|strateg)[^.]{0,80}(?:supplement|appendix|table|box)"):
        return []
    return [F(CAT, INFO, "narrative-standard-absent",
              "A narrative review with no reporting standard and no search string shown.",
              where="methods",
              fix="Report against SANRA and give the descriptor combinations and selection criteria.")]


def _impact_factor_eligibility(doc):
    """M2-R2.2: impact factor as an inclusion criterion."""
    for s in sentences(sec(doc, "methods") or body_of(doc)):
        if (has(s, r"\bimpact factor\b", r"\bjournal quartile\b", r"\bQ1 journals?\b")
                and has(s, r"\binclu\w+", r"\beligib\w+", r"\bretained\b", r"\brestricted\b", r"\bselected\b")):
            return [F(CAT, WARN, "impact-factor-eligibility",
                      f"Journal metrics used to select studies: “{_q(s)}”.", where="methods",
                      fix="Justify the criterion or remove it; a journal's metric says nothing "
                          "about the study.")]
    return []


def _dedup_arithmetic(doc):
    """M2-R2.1: more unique records after de-duplication than records found.
    The one count check here, because it needs a single sentence and no reading."""
    def num(x):
        return int(re.sub(r"[,\s]", "", x))
    pat = re.compile(r"(\d[\d,]*)\s+(?:\w+\s+){0,3}?(?:records?|items?|results?|hits|citations)\b[^.\d]{0,60}?"
                     r"(\d[\d,]*)\s+(?:\w+\s+){0,2}?(?:unique|after (?:de-?duplication|removing duplicates))", re.I)
    for s in sentences(body_of(doc)):
        if has(s, r"de-?duplicat|duplicates? (?:were )?removed|unique records"):
            m = pat.search(s)
            if m and num(m.group(2)) > num(m.group(1)):
                return [F(CAT, WARN, "dedup-count-impossible",
                          f"More records after de-duplication ({m.group(2)}) than before "
                          f"({m.group(1)}): “{_q(s)}”.", where="methods",
                          fix="Check the flow counts against the search log.")]
    return []


# ── claims ─────────────────────────────────────────────────────────────

def _threshold_underived(doc):
    """L-R1.M12: a dose-response threshold quoted as a biological cut-point."""
    body = body_of(doc)
    if not has(body, r"dose[-–– ]response"):
        return []
    if has(body, r"\bspline", r"reference (?:category|group|level)[^.]{0,60}(?:threshold|plateau)"):
        return []
    for s in sentences(sec(doc, "results") + "\n" + sec(doc, "discussion") + "\n" + abstract_of(doc)):
        if (has(s, r"\bplateau\w*\b", r"\bdetectable (?:from|at)\b", r"\bbecom\w+ detectable\b", r"\bthreshold of\b",
                r"\bbenefit (?:begins|starts)\b", r"\bflatten\w* beyond\b")
                and re.search(r"\b\d[\d,.]*\s*(?:min|minutes|steps|g/kg|mg|MET|kcal|kg)\b", s)):
            return [F(CAT, INFO, "dose-response-threshold-underived",
                      f"A dose-response threshold with no word on how it was derived: “{_q(s)}”.",
                      where="results",
                      fix="Say how it was derived; thresholds move with model, exposure measure and "
                          "reference category, and are not universal cut-points.")]
    return []


_OBS_SENT = r"\b(?:cohorts?|observational|prospective(?:ly)?|cross-sectional|hazard ratio|\bHR\b)\b"


def _evaluative_words(doc):
    """L-R1.m2, L2-R1.2, W-R3.6: 'protective', 'benefit', 'harm' on observational
    data. It came back in the second round after a first-round edit, so it is
    counted, not sampled. The existing causal rule needs a fixed phrase and
    stays as it is."""
    hits = []
    for s in sentences(sec(doc, "results") + "\n" + sec(doc, "discussion") + "\n" + sec(doc, "conclusions")
                       + "\n" + abstract_of(doc)):
        if (re.search(_OBS_SENT, s, re.I)
                and re.search(r"\bprotective\b|\bwas (?:beneficial|harmful)\b|\bwere (?:beneficial|harmful)\b|"
                              r"\bmortality benefit\b|\bsurvival benefit\b", s, re.I)
                and not has(s, r"\bassociated with\b", r"\bassociation\b", r"\bnot\b", r"\bmay\b", r"\bmight\b",
                            r"\bcould\b", r"\brandomi[sz]ed\b")):
            hits.append(s)
    if len(hits) >= 2:
        return [F(CAT, INFO, "evaluative-word-on-observational",
                  f"{len(hits)} sentences use evaluative wording on observational evidence, e.g. "
                  f"“{_q(hits[0])}”.", where="discussion",
                  fix="Prefer lower or higher observed risk, or 'associated with'.")]
    return []


def _economic_model(doc):
    """W-R1.7: a long-horizon model quoted with its result and not its structure."""
    body = body_of(doc)
    terms = [t for t in (r"\bbreak-?even\b", r"\bQALYs?\b", r"\bICERs?\b", r"\b(?:avoided|averted) (?:\w+\s+)?events?\b",
                         r"\baverts? (?:\w+\s+){0,3}events?\b", r"\bsocietal savings\b", r"\bnet cost\b",
                         r"\bcost[- ]effective\w*\b", r"\bMarkov\b", r"\bdecision[- ]analytic\b")
             if re.search(t, body, re.I)]
    if len(terms) < 2:
        return []
    own = next((s for s in sentences(body)
                if re.search(r"\b(?:our|this|the present|illustrative|reported|proposed) model\b|"
                             r"\bmodel following\b", s, re.I)
                and has(s, r"\bevents?\b", r"\bbreak-?even\b", r"\bQALY", r"\bICER", r"\bcost")), None)
    if not own:
        return []
    missing = [lab for lab, pat in (("transition probabilities", r"transition probabilit"),
                                    ("uncertainty analysis", r"probabilistic sensitivity|one-way sensitivity|deterministic sensitivity|uncertainty analysis"),
                                    ("a reporting standard", r"\bCHEERS\b"))
               if not has(body, pat)]
    if len(missing) < 2:
        return []
    return [F(CAT, WARN, "economic-model-unspecified",
              f"A model result with no {', '.join(missing)}: “{_q(own)}”.", where="results",
              fix="Give the structure, parameters and their sources, and the uncertainty analysis, "
                  "or remove the quantitative claim.")]


def _conclusion_mandate(doc):
    """W-R3.9, W-R1.5: a conclusion that mandates monitoring or care, in a paper
    that calls the evidence limited."""
    conc = sec(doc, "conclusions")
    if not conc or not is_review(doc):
        return []
    if not has(body_of(doc), r"\blimited evidence\b", r"\bevidence (?:is|remains|are) limited\b",
               r"\bextrapolat\w+", r"\buncertain\b"):
        return []
    for s in sentences(conc):
        if (has(s, r"\b(?:is|are|remains?) mandatory\b", r"\bmust be (?:monitored|performed|offered|screened|given)\b",
                r"\bis (?:an )?absolute requirement\b")
                and not has(s, r"\bproposed?\b", r"\bexpert\b", r"\bwe suggest\b")):
            return [F(CAT, WARN, "conclusion-mandate-language",
                      f"A mandate in the Conclusions, where the text calls the evidence limited: "
                      f"“{_q(s)}”.", where="conclusions",
                      fix="Mark it as an expert proposal, or soften it.")]
    return []


_RHETORIC = (r"\bthe wrong question\b", r"\bthe real question\b", r"\bmake no mistake\b", r"\bit is time to\b",
             r"\bthe uncomfortable truth\b", r"\bsimply put\b", r"\bnothing less than\b", r"\bplain and simple\b",
             r"\bbeyond (?:any )?doubt\b", r"\bthe elephant in the room\b", r"\bsilver bullet\b")


def _rhetoric(doc):
    """L-R1.m7, L-R2.13: argumentative phrasing. A fixed list of stock phrases;
    the rule cannot see an original turn of phrase, which is what the referees
    actually quoted."""
    body = body_of(doc)
    found = [re.search(p, body, re.I).group(0) for p in _RHETORIC if re.search(p, body, re.I)]
    n = sum(len(re.findall(p, body, re.I)) for p in _RHETORIC)
    if n >= 2:
        return [F(CAT, INFO, "rhetorical-register",
                  f"Argumentative stock phrases ({n}: {', '.join(found[:4])}).", where="discussion",
                  fix="Use a neutral register, or separate commentary from evidence-based conclusions.")]
    return []


# ── references ─────────────────────────────────────────────────────────

def _placeholder_link(doc):
    """L-R1.m9, L2-R1.1: template DOIs and unassigned URLs. Raised in the first
    round, still there in the second."""
    hits = re.findall(r"10\.\d{4,9}/[A-Za-z.\-]*x{3,}\b|\[URL to be assigned\]|\[DOI\]|doi\.org/x{3,}|"
                      r"https?://doi\.org/10\.\d{4,9}/\s*$", doc.text, re.I | re.M)
    if hits:
        return [F(CAT, ERROR, "placeholder-doi-or-url",
                  f"{len(hits)} placeholder DOI or URL left in the file (e.g. {hits[0].strip()}).",
                  fix="Replace with the real identifier or remove it, in the supplements as well.")]
    return []


def _intro_citations(doc):
    """L-R2.3: an Introduction whose citation support is thin for what it opens."""
    if not is_review(doc):
        return []
    intro = sec(doc, "introduction")
    wc = word_count(intro)
    refs = sec(doc, "references")
    n_refs = len([l for l in refs.splitlines() if len(l.strip()) > 25])
    if wc < 200 or n_refs < 40:
        return []
    nums = set()
    for m in re.finditer(r"[\[(]\s*(\d{1,3}(?:\s*[,–-]\s*\d{1,3})*)\s*[\])]", intro):
        for part in re.split(r"\s*,\s*", m.group(1)):
            b = re.split(r"\s*[–-]\s*", part)
            nums.update(range(int(b[0]), int(b[-1]) + 1) if len(b) == 2 and int(b[-1]) - int(b[0]) < 60 else [int(b[0])])
    if getattr(doc, "sup_citations", None) and not nums:
        return []                                    # superscripts cannot be placed in a section
    if wc / max(len(nums), 1) > 120:
        return [F(CAT, WARN, "introduction-citation-sparse",
                  f"The Introduction runs to {wc} words on {len(nums)} cited reference(s), in a "
                  f"review with {n_refs}.", where="introduction",
                  fix="Support each major opening claim with a primary study, guideline or review.")]
    return []


# ── layout ─────────────────────────────────────────────────────────────

def _display_order(doc):
    """W-R2.6, W-R3.8, E-R1.7: figures or tables cited out of numerical order.
    Three referees across two papers, and a further table cited and not
    embedded in a later round of cohort 2."""
    body = body_of(doc)
    out = []
    for base, pat in (("Figure", r"\b(?:Figures?|Figs?\.?)\s+(\d{1,2})\b"), ("Table", r"\bTables?\s+(\d{1,2})\b")):
        seq = []
        for line, styled in doc.paragraphs:
            if re.match(rf"\s*{base[:3]}\w*\.?\s+\d+\s*[.:|–-]", line, re.I):
                continue                             # a caption, not a citation
            for m in re.finditer(pat, line):
                seq.append(int(m.group(1)))
            if has(line, r"^\s*(?:\d+\.?\s+)?(?:references|irodalom)\s*$"):
                break
        # a skipped number that is never cited at all is display-item-uncited's finding
        high, bad = 0, None
        for i, n in enumerate(seq):
            missing = [k for k in range(high + 1, n) if k not in seq[:i] and k in seq[i:]]
            if missing and bad is None:
                bad = (n, missing[0])
            high = max(high, n)
        if bad and word_count(body) > 800:
            out.append(F(CAT, INFO, "display-items-out-of-order",
                         f"{base} {bad[0]} is cited before {base} {bad[1]}.",
                         fix=f"Number {base.lower()}s in the order they are first cited."))
    return out


def _raw_docx(doc):
    p = getattr(doc, "path", None)
    if not p or Path(str(p)).suffix.lower() != ".docx":
        return ""
    try:
        with zipfile.ZipFile(str(p)) as z:
            return z.read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return ""


def _bold_emphasis(doc):
    """L-R2.13, W-R3.7: bold used for emphasis inside running text, in two
    papers by two referees. Only a word processor file can show it. Run-in
    headings (bold at the start of a paragraph) are not counted, nor are
    headings, tables, or anything after the reference list."""
    xml = _raw_docx(doc)
    if not xml:
        return []
    body = re.sub(r"<w:tbl[ >].*?</w:tbl>", "", xml, flags=re.S)
    n, sample, started = 0, "", False
    for para in re.findall(r"<w:p[ >].*?</w:p>", body, flags=re.S):
        runs = re.findall(r"<w:r[ >].*?</w:r>", para, flags=re.S)
        text = "".join("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", r)) for r in runs)
        if re.match(r"\s*(?:\d+\.?\s+)?(?:References|Irodalom\w*)\s*:?\s*$", text, re.I):
            break
        if re.match(r"\s*(?:\d+\.?\s+)?(?:Introduction|Background|Bevezet\w*)\s*$", text, re.I):
            started = True
        if len(text) < 120 or not started:
            continue
        if re.search(r'<w:pStyle w:val="[^"]*(?:Head|Title|Caption|Cim|cím)', para, re.I):
            continue
        pos, hit = 0, None
        for r in runs:
            t = "".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", r))
            rpr = re.search(r"<w:rPr>.*?</w:rPr>", r, flags=re.S)
            bold = bool(rpr and re.search(r'<w:b(?:\s*/>|\s+w:val="(?:1|true|on)"\s*/>)', rpr.group(0)))
            if (bold and pos >= 40 and pos < len(text) - len(t) and re.search(r"[A-Za-zÀ-ſ]{4}", t)
                    and not t.rstrip().endswith(":")):
                hit = t
                break
            pos += len(t)
        if hit:
            n += 1
            sample = sample or hit.strip()
    if n >= 5:
        return [F(CAT, INFO, "bold-emphasis-in-body",
                  f"Bold emphasis inside running text in {n} paragraphs (e.g. “{_q(sample, 60)}”).",
                  fix="Keep bold for headings, table labels and journal-required elements.")]
    return []


def _equation_density(doc):
    """E-Ed.1: a clinical readership and a main text full of equations."""
    xml = _raw_docx(doc)
    n = len(re.findall(r"<m:oMath[ >]", xml))
    mentions = len(re.findall(r"\b(?:Equations?|Eqs?\.)\s*\(?\d", body_of(doc)))
    # equations typed as text, in files built from Markdown or LaTeX
    typed = sum(1 for p, _ in doc.paragraphs
                if p.count("=") >= 2 and re.search(r"\blog|\bexp\b|\blogit\b|[Σ∑×λ√]", p))
    if n >= 15 or mentions >= 8 or typed >= 8:
        return [F(CAT, INFO, "equation-dense-main-text",
                  f"{max(n, mentions, typed)} equations or equation-bearing paragraphs in the main text.",
                  fix="Consider moving derivations and parameter tables to a supplement if the "
                      "readership is clinical.")]
    return []


def _abbreviation_order(doc):
    """E-R1.12: an abbreviation used in the main text before it is expanded.
    The abstract is its own text, so counting starts after it. Only tokens the
    file itself defines are read, and only when the use comes well before the
    definition, because a token inside a title or a heading proves nothing."""
    text = "\n".join(s for k in ("introduction", "methods", "results", "discussion")
                     for s in [sec(doc, k)] if s)
    if len(text) < 1500:
        return []
    late = []
    for m in re.finditer(r"\(([A-Z][A-Z0-9]{1,6})s?\)", text):
        ab = m.group(1)
        first = re.search(rf"(?<![\w-]){ab}(?![\w-])", text)
        if first and first.start() < m.start() - 40 and ab not in late:
            before = text[max(0, first.start() - 2):first.start()]
            if "(" not in before:
                late.append(ab)
    if len(late) >= 2:
        return [F(CAT, INFO, "abbreviation-before-definition",
                  f"{len(late)} abbreviations are used before they are expanded ({', '.join(late[:6])}).",
                  fix="Expand each at its first occurrence in the main text.")]
    return []


RULES_SYNTH = [
    _effect_measures_mixed, _heterogeneity, _egger_null, _few_studies, _dl_estimator,
    _meta_in_narrative, _outcome_definition, _pooling_minimum,
    _fragile_not_in_abstract, _ci_false_precision, _post_hoc,
    _design_label, _automated_pipeline, _rob_inherited, _weakness_not_carried,
    _narrative_standard, _impact_factor_eligibility, _dedup_arithmetic,
    _threshold_underived, _evaluative_words, _economic_model,
    _conclusion_mandate, _rhetoric,
    _placeholder_link, _intro_citations,
    _display_order, _bold_emphasis, _equation_density, _abbreviation_order,
]


def check_synth(doc, profile):
    out = []
    for rule in RULES_SYNTH:
        try:
            out.extend(rule(doc))
        except Exception as exc:                      # a rule must never take the run down
            out.append(F(CAT, INFO, "rule-error",
                         f"{rule.__name__} could not run ({exc.__class__.__name__}).",
                         fix="Report this; the other rules are unaffected."))
    return out
