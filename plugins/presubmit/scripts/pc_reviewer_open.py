"""Reviewer-anticipation rules, cohort 8 — open peer review.

Built 2026-09-13 from 38 manuscripts whose referee reports are public together
with the version the referees read: 18 from F1000Research (v1 + reports),
20 from PeerJ (v0.1 submission PDF + reports). 608 referee objections were
extracted into a fixed taxonomy; a rule below exists only where the same objection was raised on two or more
manuscripts, or where one referee's objection is a pure string check. Codes
are cited as O-<pair>:<reviewer>, e.g. O-peerj.17409:R1.

Self-contained on purpose: it imports nothing from pc_reviewer, so it can be
tested while that module is being edited, and it is wired in from pc_checks.
"""
from __future__ import annotations

import re

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


def is_review(doc):
    head = title_of(doc) + " " + sec(doc, "abstract") + " " + doc.text[:600]
    return bool(re.search(r"\breview\b|\b[aá]ttekint[eé]s|\bscoping\b|\boverview\b", head, re.I))


def is_hungarian(doc):
    return len(re.findall(r"\b(és|hogy|nem|vagy|mint|amely|ezért)\b", doc.text)) >= 40


def is_empirical(doc):
    """Participants, patients, samples or animals were studied here."""
    if is_review(doc):
        return False
    body = body_of(doc)
    return bool(re.search(r"\b(participants?|patients?|respondents?|subjects?|"
                          r"samples? were (collected|obtained)|mice|rats|volunteers?|"
                          r"r[eé]sztvev[oő]|betegek|v[aá]laszad[oó])\b", body, re.I))


def has(text, *pats):
    return any(re.search(p, text or "", re.I) for p in pats)


def _q(s, n=100):
    s = s.strip()
    return s[:n] + ("…" if len(s) > n else "")


def cited(s):
    return bool(re.search(r"\[\s*\d|\(\s*\d{4}\s*\)|\bet al\b|\(\s*[A-Z][a-z]+,|\b[A-Z][a-z]+ (and|&) [A-Z][a-z]+ \(?\d{4}", s))


P_VALUE = r"\bp\s*[<=>≤≥]\s*0?[.,]\d+"


# ─────────────────────────────────────────────────────────── statistics ──
def _multiplicity(doc):
    """O-f1000research.130700.2:R1, O-f1000research.53257.3:R1, O-peerj.18835:R1
    — many p-values, no correction."""
    body = body_of(doc)
    n = len(re.findall(P_VALUE, body, re.I))
    if n < 10:
        return []
    if has(body, r"Bonferroni|Holm|false discovery|\bFDR\b|Benjamini|multiple (testing|comparisons?)|adjusted p"):
        return []
    return [F(CAT, WARN, "multiplicity-uncorrected",
              f"{n} p-values are reported and no correction for multiple testing is mentioned.",
              where="methods",
              fix="Name the correction (Bonferroni, Holm, FDR) or say why none was applied; "
                  "three referees in three manuscripts asked.")]


def _test_named_not_reported(doc):
    """O-f1000research.130700.2:R1 — Kruskal-Wallis in the Methods, never in the Results."""
    methods, results = sec(doc, "methods"), sec(doc, "results")
    if not methods or not results:
        return []
    tests = ("Kruskal", "Mann-Whitney", "ANOVA", "chi-square", "χ2", "t-test", "Fisher",
             "Wilcoxon", "Spearman", "Pearson", "logistic regression", "linear regression",
             "Cox", "Kaplan")
    missing = [t for t in tests if re.search(re.escape(t), methods, re.I)
               and not re.search(re.escape(t), results + sec(doc, "discussion"), re.I)]
    if not missing:
        return []
    return [F(CAT, INFO, "test-named-not-reported",
              f"Named in the Methods and never reported in the Results: {', '.join(missing)}.",
              where="results",
              fix="Report each test where its result appears (statistic, df, p), or drop it.")]


def _significance_level(doc):
    """O-peerj.18835:R1, O-peerj.17409:R1 — p-values with no stated alpha or sidedness."""
    body = body_of(doc)
    if len(re.findall(P_VALUE, body, re.I)) < 3:
        return []
    out = []
    if not has(body, r"p\s*[<≤]\s*0?[.,]05\b", r"\balpha\b|α\s*=", r"significance level",
               r"considered (statistically )?significant", r"szignifikancia"):
        out.append(F(CAT, INFO, "significance-level-unstated",
                     "p-values are reported and no significance level is stated.",
                     where="methods", fix="One sentence: 'p < 0.05 (two-sided) was considered significant.'"))
    elif not has(body, r"two-(sided|tailed)|one-(sided|tailed)|k[eé]toldal"):
        out.append(F(CAT, INFO, "test-sidedness-unstated",
                     "Neither 'two-sided' nor 'one-sided' appears.",
                     where="methods", fix="Say which, once."))
    return out


def _marginal_p(doc):
    """O-peerj.18881:R1 — p between 0.05 and 0.10 called significant or a trend."""
    out = []
    for s in sentences(body_of(doc)):
        for m in re.finditer(r"\bp\s*[=<>≤]\s*0?[.,](0[5-9]\d*|10?)\b", s, re.I):
            val = float("0." + m.group(1))
            if 0.05 <= val <= 0.10 and re.search(r"significant|\btrend\b|marginal|borderline", s, re.I) \
                    and not re.search(r"not (statistically )?significant|non-?significant|no significant", s, re.I):
                out.append(F(CAT, WARN, "marginal-p-called-significant",
                             f"A p-value of {m.group(0).strip()} described as significant or a trend: \"{_q(s)}\"",
                             where="results",
                             fix="Report it as not significant at the stated level; 'trend' is not a result."))
                break
        if len(out) >= 2:
            break
    return out


def _normality(doc):
    """O-peerj.18835:R1, O-peerj.14744:Ed — parametric tests with no distribution check."""
    body = body_of(doc)
    if not has(body, r"\bt-?test\b", r"\bANOVA\b", r"mean\s*±|mean \(SD\)|\bmean and standard deviation"):
        return []
    if has(body, r"normal(ly)? distribut|normality|Shapiro|Kolmogorov|Anderson-Darling|skew|Q-Q plot|"
                 r"non-?parametric|norm[aá]l(is)? eloszl"):
        return []
    return [F(CAT, INFO, "normality-unassessed",
              "Parametric statistics are used and no sentence says how normality was assessed.",
              where="methods",
              fix="Name the test or plot, and the fallback for non-normal variables.")]


def _decimal_hygiene(doc):
    """O-peerj.17409:R1 (twice), O-peerj.19505:R1 — decimal commas in p-values, and
    three or more decimals outside p-values."""
    body = body_of(doc)
    out = []
    if not is_hungarian(doc):
        m = re.search(r"\bp\s*[<=>]\s*0,\d", body, re.I)
        if m:
            out.append(F(CAT, INFO, "p-decimal-comma",
                         f"A p-value with a decimal comma: '{m.group(0)}'.",
                         where="results", fix="Use the decimal point throughout an English manuscript."))
    stripped = re.sub(P_VALUE, "", body, flags=re.I)
    stripped = re.sub(r"\bp\s*[<=>]\s*0?[.,]\d+", "", stripped)
    stripped = re.sub(r"10\.\d{4,9}/\S+", "", stripped)          # DOIs
    over = re.findall(r"(?<![\d.])\d+\.\d{3,}(?!\d)", stripped)
    if len(over) >= 5:
        out.append(F(CAT, INFO, "over-precise-decimals",
                     f"{len(over)} numbers carry three or more decimals (e.g. {', '.join(over[:3])}).",
                     where="results",
                     fix="Two decimals for estimates, one for percentages; precision beyond the "
                         "measurement is read as false precision."))
    return out


def _logistic_diagnostics(doc):
    """O-f1000research.129799.3:R1 — a logistic model with no diagnostics."""
    body = body_of(doc)
    if not has(body, r"logistic regression|logisztikus regresszi"):
        return []
    if has(body, r"multicollinear|\bVIF\b|Hosmer|goodness[- ]of[- ]fit|calibrat|Nagelkerke|pseudo-?R"):
        return []
    return [F(CAT, INFO, "logistic-diagnostics-absent",
              "A logistic regression is reported with no goodness-of-fit or collinearity check.",
              where="methods",
              fix="Hosmer–Lemeshow or calibration, VIF for collinearity, and the events-per-variable count.")]


def _fold_claim(doc):
    """O-peerj.20076:R1 — 'N-fold higher' with nothing behind it in the sentence."""
    out = []
    for s in sentences(body_of(doc)):
        if re.search(r"\b\d+(\.\d+)?[- ](fold|times) (higher|lower|more|greater|less)", s, re.I) \
                and not re.search(P_VALUE + r"|95\s*%|\bCI\b|confidence", s, re.I):
            out.append(F(CAT, INFO, "fold-claim-without-interval",
                         f"A fold-change claim with no p-value or interval: \"{_q(s)}\"",
                         where="results", fix="Give the interval or the test beside the ratio."))
            break
    return out


def _ci_spans_null(doc):
    """O-peerj.14744:Ed — an estimate whose interval includes 1 described as an association."""
    out = []
    for s in sentences(body_of(doc)):
        m = re.search(r"\b(a?OR|RR|HR|PR|IRR)\s*(?:was|of|=|:)?\s*(\d+\.\d+)\s*[\(\[,;]?\s*(?:95\s*%\s*CI|CI)[:=]?\s*[\(\[]?\s*(\d+\.\d+)\s*(?:–|-|to|,)\s*(\d+\.\d+)", s, re.I)
        if not m:
            continue
        lo, hi = float(m.group(3)), float(m.group(4))
        if lo < 1.0 < hi and re.search(r"\b(associated|higher|lower|increased|decreased|greater|risk factor|predict)", s, re.I) \
                and not re.search(r"not (significant|associated)|no (significant )?(association|difference)|non-?significant", s, re.I):
            out.append(F(CAT, WARN, "ci-spans-null-called-association",
                         f"The interval {lo}–{hi} includes 1 and the sentence still asserts an association: \"{_q(s)}\"",
                         where="results",
                         fix="Report it as compatible with no association; the interval is the finding."))
            if len(out) >= 2:
                break
    return out


def _prediction_validation(doc):
    """O-f1000research.129799.3:R1, O-peerj.19298:R2 — a predictive claim with no validation."""
    body = body_of(doc)
    if not has(body, r"predict(ive|ion) model|risk (model|score)|prognostic model|nomogram|classifier"):
        return []
    # NOTE: this exit is why cohort 9 exists. A model evaluated only in
    # simulation prints AUCs and proposes a validation, so it satisfies every
    # string here while being exactly what a referee objects to. See
    # pc_reviewer_sim._development_cohort_absent.
    if has(body, r"validat|cross-?validation|bootstrap|\bAUC\b|calibrat|discriminat|independent cohort"):
        return []
    return [F(CAT, WARN, "prediction-without-validation",
              "A predictive model or score is presented and no validation of any kind is reported.",
              where="methods",
              fix="Internal validation at least (bootstrap or cross-validation), discrimination and "
                  "calibration; say that external validation is pending.")]


def _cross_sectional_causal(doc):
    """O-peerj.14744:Ed, O-f1000research.146998.2:R1, O-peerj.18835:R1 — cross-sectional
    design, causal or 'strong' language in the conclusions."""
    body = body_of(doc)
    if not has(body, r"cross-?sectional|keresztmetszeti"):
        return []
    tail = sec(doc, "conclusions") + " " + sec(doc, "discussion")[-1500:] + " " + sec(doc, "abstract")
    out = []
    for s in sentences(tail):
        if re.search(r"\b(effect of|leads? to|causes?|caused|impact of|results? in|determin(es|ed)|"
                     r"strong(ly)? associat|significantly (increased|decreased|improved|reduced))\b", s, re.I) \
                and not re.search(r"\b(may|might|could|cannot|associated with|hypothes|potential|"
                                  r"cross-sectional|causal(ity)? cannot)\b", s, re.I):
            out.append(F(CAT, WARN, "cross-sectional-causal-language",
                         f"Causal or 'strong' language in a cross-sectional study: \"{_q(s)}\"",
                         where="conclusions",
                         fix="'Associated with' is what the design supports; say once that causality "
                             "cannot be inferred."))
            break
    return out


# ────────────────────────────────────────────────────── reproducibility ──
_SOFTWARE = (r"\b(SPSS|Stata|STATA|SAS|GraphPad|Prism|QIIME2?|MEGAHIT|SPAdes|MATLAB|JASP|jamovi|"
             r"Mplus|AMOS|RevMan|MedCalc|NVivo|Bowtie2?|BLAST|Trimmomatic|DADA2|mothur|LEfSe|"
             r"PICRUSt2?|MetaPhlAn|Kraken2?|STAR|DESeq2|edgeR|limma|SciPy|scikit-learn|"
             r"Python|G\*Power|Epi ?Info|OpenEpi|R Studio|RStudio)\b")


def _software_versions(doc):
    """O-peerj.17486:R1, O-peerj.18835:R1, O-peerj.15245:R3 — software with no version."""
    methods = sec(doc, "methods") or body_of(doc)
    missing = []
    for m in re.finditer(_SOFTWARE, methods):
        window = methods[m.end():m.end() + 60]
        if not re.search(r"\b(v|ver\.?|version)\s*\.?\s*\d|\d+\.\d+|\(\d{4}\)|R \d\.\d", window, re.I):
            missing.append(m.group(1))
    missing = sorted(set(missing))
    if not missing:
        return []
    return [F(CAT, INFO, "software-without-version",
              f"Software named without a version: {', '.join(missing[:6])}.",
              where="methods",
              fix="Version and, for packages, the citation. Three referees in three manuscripts asked.")]


def _date_range(doc):
    """O-peerj.18835:R1, O-peerj.14744:Ed — no data-collection period."""
    if not is_empirical(doc):
        return []
    methods = sec(doc, "methods")
    if not methods:
        return []
    if re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December|"
                 r"janu[aá]r|febru[aá]r|m[aá]rcius|[aá]prilis|m[aá]jus|j[uú]nius|j[uú]lius|augusztus|"
                 r"szeptember|okt[oó]ber|november|december)\s*\d{0,2},?\s*\d{4}", methods, re.I) \
            or re.search(r"\b(between|from)\s+\w*\s*\d{4}\s+(and|to|until|through)\s+\w*\s*\d{4}", methods, re.I) \
            or re.search(r"\b\d{4}\.\s*\d{2}\.\s*\d{2}\.?|\b\d{4}[–-]\d{4}\b", methods):
        return []
    return [F(CAT, WARN, "collection-period-unstated",
              "The Methods give no data-collection period.",
              where="methods", fix="Month and year, start and end.")]


def _sample_size(doc):
    """O-peerj.15662:R1, O-peerj.19298:R1, O-peerj.20009:R2, O-peerj.18881:R1,
    O-peerj.19506:R1, O-f1000research.134328.2:R2 — six manuscripts, no
    sample-size justification anywhere."""
    if not is_empirical(doc):
        return []
    body = body_of(doc)
    if has(body, r"sample size|power (calculation|analysis)|\bpowered\b|underpowered|margin of error|"
                 r"G\*Power|mintanagys[aá]g|mintaelemsz[aá]m|statisztikai er[oő]"):
        return []
    return [F(CAT, WARN, "sample-size-unjustified",
              "No sample-size or power statement anywhere in the manuscript.",
              where="methods",
              fix="Either the calculation (effect, alpha, power) or, for a convenience sample, a sentence "
                  "in the Limitations saying so. Six of 38 open-review manuscripts drew this comment.")]


def _eligibility(doc):
    """O-peerj.18835:R1, O-peerj.17525:R1 — no inclusion or exclusion criteria."""
    if not is_empirical(doc):
        return []
    methods = sec(doc, "methods")
    if not methods:
        return []
    if has(methods, r"inclusion|exclusion|eligib|were included if|were excluded|excluded if|"
                    r"bev[aá]laszt[aá]si|kiz[aá]r[aá]si|felt[eé]tel"):
        return []
    return [F(CAT, WARN, "eligibility-criteria-absent",
              "The Methods state neither inclusion nor exclusion criteria.",
              where="methods", fix="Who was eligible, who was excluded, and how that was checked.")]


def _accession(doc):
    """O-peerj.18881:R1, O-peerj.15245:R3, O-peerj.17486:R1 — sequencing data with no accession."""
    body = body_of(doc)
    if not has(body, r"\b16S\b|metagenom|RNA-?seq|whole[- ]genome|amplicon sequenc|shotgun sequenc|transcriptom"):
        return []
    if re.search(r"\b(PRJ[NED][A-Z]\d+|SR[APRXS]\d+|GSE\d+|ERP\d+|E-MTAB-\d+|SAMN\d+)\b", doc.text) \
            or has(doc.text, r"deposited (in|at|to)|accession (number|code)|BioProject|Sequence Read Archive"):
        return []
    return [F(CAT, WARN, "sequence-data-accession-absent",
              "Sequencing data are analysed and no repository accession is given.",
              where="data availability",
              fix="Deposit the reads (SRA/ENA/GEO) and cite the accession; referees now look for the "
                  "identifier before the results.")]


def _either_or_methods(doc):
    """O-peerj.19528:R1 — 'either DADA2 or Deblur': a method that was not decided."""
    methods = sec(doc, "methods")
    m = re.search(r"\beither\b[^.]{1,60}\bor\b[^.]{0,40}\.", methods or "", re.I)
    if not m:
        return []
    return [F(CAT, INFO, "either-or-in-methods",
              f"A Methods sentence offers alternatives rather than what was done: \"{_q(m.group(0))}\"",
              where="methods", fix="Say which one was used.")]


def _age_sex(doc):
    """O-peerj.15662:R1, O-peerj.15245:R3 — human participants with no age or sex reported."""
    if not is_empirical(doc) or not has(body_of(doc), r"participants?|patients?|respondents?|volunteers?|betegek|r[eé]sztvev"):
        return []
    text = sec(doc, "methods") + sec(doc, "results")
    if not text:
        return []
    if not (has(text, r"\bage\b|\bages\b|\baged\b|[eé]letkor") and has(text, r"\bsex\b|\bgender\b|\bfemale|\bmale\b|\bwomen|\bmen\b|\bn[oő]k?\b|f[eé]rfi")):
        return [F(CAT, INFO, "participant-age-sex-absent",
                  "Age and sex of the participants are not both reported.",
                  where="results", fix="A baseline table, or one sentence with both.")]
    return []


def _primary_outcome(doc):
    """O-peerj.19506:R1 — a trial with no named primary outcome."""
    body = body_of(doc)
    methods = sec(doc, "methods") or body
    if not has(methods, r"were randomi[sz]ed|randomly (assigned|allocated)|randomi[sz]ation (was|were|sequence|list)|"
                        r"randomi[sz]ed (controlled )?trial (was|is) (conducted|performed|designed)|we randomi[sz]ed|"
                        r"randomiz[aá]lt"):
        return []
    if has(body, r"primary (outcome|endpoint|end-point)|els[oő]dleges (kimenet|v[eé]gpont)"):
        return []
    return [F(CAT, WARN, "primary-outcome-unnamed",
              "A trial is reported and no primary outcome is named.",
              where="methods", fix="Name it, with its time point, and match the sample-size calculation to it.")]


# ─────────────────────────────────────────────────── claims and framing ──
def _implications(doc):
    """O-f1000research.130700.2:R1, O-peerj.17486:R1, O-peerj.18835:R1, O-peerj.19505:R1,
    O-peerj.14744:Ed, O-peerj.17525:R1 — no implication for practice or policy anywhere."""
    tail = sec(doc, "discussion") + " " + sec(doc, "conclusions")
    if word_count(tail) < 200:
        return []
    if has(tail, r"implication|clinical practice|clinician|practitioner|policy|recommend|\bshould\b|"
                 r"gyakorlat|aj[aá]nl|javasol"):
        return []
    return [F(CAT, INFO, "implications-absent",
              "Neither the Discussion nor the Conclusions say what the findings mean for practice or policy.",
              where="discussion",
              fix="One paragraph: who should do what differently, and what should not change yet. "
                  "Six of 38 open-review manuscripts drew this comment.")]


def _confounding(doc):
    """O-peerj.14744:Ed, O-f1000research.146998.2:R1, O-peerj.18835:R1 — observational
    human data with no word about confounding or alternative explanations."""
    if not is_empirical(doc):
        return []
    body = body_of(doc)
    if not has(body, r"cross-?sectional|case-?control|observational|retrospective|keresztmetszeti") \
            or not has(body, r"participants?|patients?|respondents?|betegek|r[eé]sztvev"):
        return []
    if has(body, r"confound|adjust(ed|ing) for|covariate|alternative explanation|cannot (exclude|rule out)|"
                 r"reverse causa|zavar[oó] (t[eé]nyez|v[aá]ltoz)|korrig[aá]l"):
        return []
    return [F(CAT, INFO, "confounding-unaddressed",
              "An observational design, and neither adjustment nor confounding nor an alternative "
              "explanation is mentioned anywhere.",
              where="discussion",
              fix="Say what was adjusted for, what could not be, and which way the residual bias runs.")]


def _self_report_bias(doc):
    """O-peerj.17409:R1, O-f1000research.134328.2:R1, O-f1000research.146998.2:R1 —
    self-reported data with no recall or social-desirability caveat."""
    body = body_of(doc)
    if not has(body, r"self-?report|questionnaire|interview|k[eé]rd[oő][ií]v|[oö]nbevall"):
        return []
    tail = sec(doc, "discussion") + " " + sec(doc, "limitations") + " " + sec(doc, "conclusions")
    if not tail:
        return []
    if has(tail, r"recall bias|social desirability|self-?report(ing)? bias|reporting bias|"
                 r"felid[eé]z[eé]si torz|t[aá]rsadalmi k[ií]v[aá]natoss[aá]g"):
        return []
    return [F(CAT, INFO, "self-report-bias-unmentioned",
              "Self-reported data, and the Discussion never names recall or social-desirability bias.",
              where="discussion", fix="Name the bias and the direction it most likely pushes the estimates.")]


def _hypothesis(doc):
    """O-f1000research.53257.3:R1, O-peerj.18835:R1, O-peerj.19528:R1, O-peerj.17520:R1 —
    an empirical study whose Introduction states no aim or hypothesis."""
    if not is_empirical(doc):
        return []
    intro = sec(doc, "introduction")
    if not intro:
        return []
    if has(intro, r"hypothes|\baim(ed|s)?\b|objective|purpose of (this|the present)|we (investigated|examined|sought|tested|asked)|"
                  r"c[eé]lkit[uű]z|c[eé]lunk|hipot[eé]zis|arra kerest"):
        return []
    return [F(CAT, WARN, "aim-or-hypothesis-absent",
              "The Introduction ends without an aim, objective or hypothesis.",
              where="introduction",
              fix="Last paragraph of the Introduction: the question, the hypothesis, the design in one sentence. "
                  "Four of 38 open-review manuscripts drew this comment.")]


def _discussion_comparison(doc):
    """O-peerj.17409:R1, O-f1000research.134328.2:R1 — a Discussion that never compares
    the findings with anyone else's."""
    disc = sec(doc, "discussion")
    if word_count(disc) < 300:
        return []
    if has(disc, r"consistent with|in line with|similar to|in contrast|contrary to|compared (with|to)|"
                 r"previous(ly)? (stud|report|work)|earlier (stud|report)|agree[sd]? with|"
                 r"[oö]sszhangban|hasonl[oó]an|ellent[eé]tben|kor[aá]bbi (vizsg|tanulm)"):
        return []
    return [F(CAT, WARN, "discussion-without-comparison",
              "The Discussion never places the findings beside previous work.",
              where="discussion",
              fix="For each main finding: who found the same, who found otherwise, and why the difference.")]


def _intro_shape(doc):
    """O-f1000research.139258.2:R1, O-peerj.17525:R1, O-peerj.15245:R3, O-peerj.18881:R1 —
    an Introduction that is too short, or whose paragraphs cite nothing."""
    intro = sec(doc, "introduction")
    if not intro or is_hungarian(doc):
        return []
    out = []
    wc = word_count(intro)
    if is_empirical(doc) and wc < 250:
        out.append(F(CAT, INFO, "introduction-short",
                     f"The Introduction is {wc} words.",
                     where="introduction",
                     fix="Three moves at least: the problem with its size, what is known, what is not."))
    paras = [p for p in intro.split("\n") if word_count(p) >= 60]
    uncited = [p for p in paras if not cited(p)]
    if paras and len(uncited) >= 3:
        out.append(F(CAT, INFO, "introduction-paragraphs-uncited",
                     f"{len(uncited)} of {len(paras)} Introduction paragraphs carry no citation: "
                     f"\"{_q(uncited[0], 80)}\"",
                     where="introduction", fix="A factual paragraph without a citation reads as opinion."))
    return out


def _vague_conclusion(doc):
    """O-peerj.18835:R1 — 'provide insights', 'pave the way'."""
    con = sec(doc, "conclusions") or sec(doc, "abstract")[-600:]
    m = re.search(r"provide[sd]? (new |novel |valuable |important )?insights?|shed[s]? (new )?light|pave[sd]? the way|"
                  r"lay[s]? the (foundation|groundwork)|open[s]? (new )?avenues", con or "", re.I)
    if not m:
        return []
    return [F(CAT, INFO, "conclusion-boilerplate",
              f"A conclusion phrase that says nothing: '{m.group(0)}'.",
              where="conclusions", fix="Replace with the finding, its number, and what follows from it.")]


def _single_centre(doc):
    """O-f1000research.172953.1:R1, O-f1000research.146998.2:R1 — one site, no word on generalisability."""
    body = body_of(doc)
    if not has(body, r"single[- ](cent(re|er)|institution|site|hospital)|one (hospital|college|university|clinic|centre|center)|"
                     r"egy (k[oó]rh[aá]z|int[eé]zm[eé]ny|centrum)"):
        return []
    tail = sec(doc, "discussion") + " " + sec(doc, "limitations") + " " + sec(doc, "conclusions")
    if has(tail, r"generali[sz]|representativ|extrapolat|[aá]ltal[aá]nos[ií]t|reprezentat"):
        return []
    return [F(CAT, INFO, "single-centre-generalisability",
              "A single-site study, and the Discussion says nothing about generalisability.",
              where="discussion", fix="One sentence on whom the findings can and cannot be extended to.")]


def _knowledge_labels(doc):
    """O-f1000research.134328.2:R2, O-f1000research.172953.1:R1 — 'good knowledge' with no cut-off."""
    body = body_of(doc)
    if not re.search(r"\b(good|poor|adequate|inadequate|high|low|sufficient) (level of )?(knowledge|attitude|practice|awareness)", body, re.I) \
            or not has(body, r"questionnaire|survey|k[eé]rd[oő][ií]v") or len(re.findall(r"\bscor", body, re.I)) < 2:
        return []
    if has(body, r"cut-?off|threshold|Bloom|scored?\b[^.]{0,40}(points?|%)|\d+\s*%[^.]{0,30}(or (more|above)|and above|or higher)|median split"):
        return []
    return [F(CAT, WARN, "knowledge-label-without-cutoff",
              "'Good' or 'poor' knowledge/attitude/practice is used and no scoring cut-off is stated.",
              where="methods", fix="The score range, the cut-off, and where it came from (Bloom's or a citation).")]


def _pre_post_followup(doc):
    """O-f1000research.130700.2:R1 — a before-after design with no follow-up."""
    body = body_of(doc)
    if not has(body, r"pre-?post|before[- ]and[- ]after|pre-?intervention|post-?intervention|pre-?test.{0,20}post-?test"):
        return []
    if has(body, r"follow-?up|long-?term|sustain|retention|months later|weeks later"):
        return []
    return [F(CAT, INFO, "pre-post-without-followup",
              "A pre/post design with no follow-up measurement or any word on durability.",
              where="discussion", fix="State when the post measurement was taken and that persistence is untested.")]


# ────────────────────────────────────────── abbreviations and wording ──
_ABBR_STOP = {"USA", "UK", "EU", "CI", "OR", "RR", "HR", "SD", "SE", "IQR", "BMI", "PCR", "WHO", "NIH",
              "FDA", "COVID", "SARS", "HIV", "DNA", "RNA", "II", "III", "IV", "AND", "THE", "NOT", "MeSH",
              "USD", "EUR", "GBP", "AI", "ML", "IT", "US", "AM", "PM", "ID", "NA", "NS", "IRB", "UNICEF", "UN"}


def _abstract_abbreviations(doc):
    """O-peerj.17486:R1, O-peerj.17520:R1, O-peerj.17525:R5, O-peerj.14744:Ed, O-peerj.17805:R1 —
    an abbreviation in the abstract with no expansion in the abstract."""
    ab = sec(doc, "abstract")
    if not ab:
        return []
    toks = {t for t in re.findall(r"\b[A-Z][A-Z0-9]{2,7}\b", ab) if t not in _ABBR_STOP and not re.fullmatch(r"[IVX]+", t)}
    undefined = sorted(t for t in toks if not re.search(rf"\({re.escape(t)}s?[;,)]|{re.escape(t)}\s*\(", ab))
    if not undefined:
        return []
    return [F(CAT, WARN, "abstract-abbreviation-undefined",
              f"Abbreviations used in the abstract without expansion there: {', '.join(undefined[:6])}.",
              where="abstract",
              fix="The abstract is read alone; expand at first use inside it. Five of 38 open-review "
                  "manuscripts drew this comment.")]


def _abbreviation_economy(doc):
    """O-peerj.17520:R1 (defined, used once more), O-peerj.14744:Ed (defined twice)."""
    body = body_of(doc)
    defs = re.findall(r"\(([A-Z][A-Za-z0-9-]{1,8})\)", body)
    out = []
    from collections import Counter
    counts = Counter(defs)
    twice = sorted(t for t, n in counts.items() if n >= 2 and re.search(r"[A-Z]{3}", t) and t not in _ABBR_STOP)
    if len(twice) >= 2:
        out.append(F(CAT, INFO, "abbreviation-defined-twice",
                     f"Defined more than once: {', '.join(twice[:6])}.",
                     where="text", fix="Define once, at first use."))
    rare = []
    for t in sorted(set(defs)):
        if t in _ABBR_STOP or not re.search(r"[A-Z]{2}", t):
            continue
        uses = len(re.findall(rf"\b{re.escape(t)}\b", body)) - counts[t]
        if uses < 2:
            rare.append(t)
    if len(rare) >= 4:
        out.append(F(CAT, INFO, "abbreviation-defined-rarely-used",
                     f"Defined and then used fewer than twice: {', '.join(rare[:6])}.",
                     where="text",
                     fix="An abbreviation that is not reused is a cost with no return; write the words."))
    return out


_VARIANTS = [("analyse", "analyze"), ("behaviour", "behavior"), ("colour", "color"), ("tumour", "tumor"),
             ("haemo", "hemo"), ("centre", "center"), ("anaemia", "anemia"), ("diarrhoea", "diarrhea"),
             ("oestrogen", "estrogen"), ("paediatric", "pediatric"), ("randomised", "randomized"),
             ("organisation", "organization"), ("programme", "program "), ("favour", "favor"),
             ("labelled", "labeled"), ("modelling", "modeling"), ("oedema", "edema"), ("foetal", "fetal")]


def _spelling_variants(doc):
    """O-f1000research.125549.4:R2 — 'diarrhea' and 'diarrhoea' in one manuscript."""
    if is_hungarian(doc):
        return []
    body = body_of(doc).lower()
    mixed = [f"{a}/{b.strip()}" for a, b in _VARIANTS
             if re.search(rf"\b{a}", body) and re.search(rf"\b{b}", body)]
    if not mixed:
        return []
    return [F(CAT, INFO, "spelling-variants-mixed",
              f"British and American spellings of the same word: {', '.join(mixed[:5])}.",
              where="text", fix="Pick the journal's variety and apply it throughout.")]


def _taxon_placeholders(doc):
    """O-peerj.15245:R3, O-peerj.17520:R1 — database placeholder labels in prose."""
    body = body_of(doc)
    hits = sorted(set(re.findall(r"\b(?:[A-Z][a-z]+_\d+|uncultured_\w+|unclassified_\w+|[pcofgs]__[A-Z]\w*)\b", body)))
    if not hits:
        return []
    return [F(CAT, INFO, "taxon-placeholder-labels",
              f"Database placeholder taxon labels in the text: {', '.join(hits[:5])}.",
              where="results", fix="Write the taxon at the rank it was resolved to, and say how unresolved taxa were handled.")]


def _preposition_ending(doc):
    """O-peerj.15662:R1 — sentences ending on a preposition."""
    if is_hungarian(doc):
        return []
    out = []
    for s in sentences(body_of(doc)):
        if re.search(r"\b(by|of|to|with|for|from|in|on|at)\.$", s):
            out.append(F(CAT, INFO, "sentence-ends-on-preposition",
                         f"\"{_q(s)}\"", where="text", fix="The object of the preposition is missing."))
            if len(out) >= 2:
                break
    return out


def _present_tense_methods(doc):
    """O-peerj.18835:R1 — procedures in the present tense."""
    methods = sec(doc, "methods")
    if not methods or is_hungarian(doc):
        return []
    hits = re.findall(r"\b(?:is|are) (?:performed|collected|measured|analy[sz]ed|extracted|conducted|"
                      r"recorded|administered|calculated|obtained)\b", methods)
    if len(hits) < 3:
        return []
    return [F(CAT, INFO, "methods-present-tense",
              f"{len(hits)} procedural verbs in the present tense in the Methods (e.g. '{hits[0]}').",
              where="methods", fix="What was done is reported in the past tense.")]


# ─────────────────────────────────────────────────── display items ──
def _display_items(doc):
    """O-peerj.17525:R1 (figure cited once or never), O-peerj.17486:R1 (caption of
    four words), O-f1000research.142586.2:R2 (a review with no table)."""
    text = doc.text
    out = []
    caps = {}
    for m in re.finditer(r"(?m)^\s*(Figure|Fig\.|Table)\s+(\d{1,2})\b[.:]?\s*(.*)$", text):
        kind = "Figure" if m.group(1).startswith("Fig") else "Table"
        caps.setdefault((kind, int(m.group(2))), m.group(3))
    uncited, short = [], []
    for (kind, n), cap in caps.items():
        cites = len(re.findall(rf"\b{kind[:3]}\w*\.?\s*{n}\b", text)) - 1
        if cites <= 0:
            uncited.append(f"{kind} {n}")
        if 0 < word_count(cap) < 4 and not cap.rstrip().endswith((":", "-", "–")):
            short.append(f"{kind} {n}")
    if uncited:
        out.append(F(CAT, INFO, "display-item-uncited",
                     f"Captioned but never cited in the text: {', '.join(uncited[:6])}.",
                     where="text", fix="Every figure and table is called from the sentence it supports."))
    if short:
        out.append(F(CAT, INFO, "caption-too-short",
                     f"Captions under six words: {', '.join(short[:6])}.",
                     where="figures", fix="A caption states what is shown, in whom, and what the marks mean."))
    return out


RULES_COHORT_8 = [
    _multiplicity, _test_named_not_reported, _significance_level, _marginal_p, _normality,
    _decimal_hygiene, _logistic_diagnostics, _fold_claim, _ci_spans_null, _prediction_validation,
    _cross_sectional_causal, _software_versions, _date_range, _sample_size, _eligibility,
    _accession, _either_or_methods, _age_sex, _primary_outcome, _implications, _confounding,
    _self_report_bias, _hypothesis, _discussion_comparison, _intro_shape, _vague_conclusion,
    _single_centre, _knowledge_labels, _pre_post_followup, _abstract_abbreviations,
    _abbreviation_economy, _spelling_variants, _taxon_placeholders, _preposition_ending,
    _present_tense_methods, _display_items,
]


def check_open(doc, profile):
    out = []
    for rule in RULES_COHORT_8:
        try:
            out.extend(rule(doc))
        except Exception as exc:                      # a rule must never take the run down
            out.append(F(CAT, INFO, "rule-error",
                         f"{rule.__name__} could not run ({exc.__class__.__name__}).",
                         fix="Report this; the other rules are unaffected."))
    return out
