"""Reviewer-anticipation rules, cohort 9 — the simulation-vs-validation gap.

Built from one referee report on a model paper evaluated only in simulation.
Codes are cited as S-R1.<n> and map to `references/reviewer-patterns.md`.

Why a new cohort rather than a patch. Cohort 8 already carries
`prediction-without-validation`, and it stayed silent on the manuscript this
referee wrote at length about — because that rule exits as soon as the
text contains `AUC`, `calibrat` or `validat`. A paper that reports a full set
of simulated AUCs and proposes a future validation satisfies every one of those
string tests while being exactly the thing the referee objected to. The miss is
structural: cohort 8 asks *is validation mentioned*, and the question that
mattered is *where did these numbers come from*.

So the rules here all ask about provenance. A number is literature-derived,
assumed, simulated, or measured in patients, and a referee reading a model
paper wants to know which — in the Abstract, in the Results, in the figures and
in the Conclusion, not once in a limitations paragraph.

Two rules at the end come from cohort 13, a second referee on the same paper
(E-R1.<n>); they need the gates above, so they live here.

Self-contained, like cohort 8: imports nothing from the other reviewer modules.
"""
from __future__ import annotations

import re

from pc_lib import F, ERROR, WARN, INFO

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


def has(text, *patterns):
    return any(re.search(p, text or "", re.I) for p in patterns)


def _q(s, n=150):
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n - 1] + "…"


# ── the two gates every rule below leans on ───────────────────────────────

_MODEL = (r"predict(ion|ive) model|risk (model|score|calculator)|prognostic model|"
          r"diagnostic model|nomogram|classifier|\bframework\b|decision (model|rule)|"
          r"scoring system|algorithm")

_SIMULATED = (r"\bsimulat\w+|in silico|synthetic (cohort|data|patient)|"
              r"hypothetical (cohort|patient|case)|monte[- ]carlo|\bvirtual (patient|cohort)|"
              r"\btest vector|szimul\w+")

_REAL_COHORT = (r"\bwe (enrolled|recruited|included|screened)\b|"
                r"(patients|participants|women|subjects) were (enrolled|recruited|included|screened)|"
                r"consecutive (patients|participants|women)|"
                r"(training|derivation|development) (cohort|set|sample|dataset)|"
                r"(internal|external|independent|temporal) validation (cohort|set|sample|dataset)|"
                r"\btest (cohort|set) \b|held-?out (set|cohort)|"
                r"data were collected from \d|retrospective(ly)? (review|collect|identif)")

_METRIC = (r"\bAUROC\b|\bAUC\b|\bc-?statistic|\bconcordance (index|statistic)|"
           r"\bPPV\b|\bNPV\b|positive predictive value|negative predictive value|"
           r"\bsensitivit(y|ies)\b|\bspecificit(y|ies)\b|likelihood ratio|\bLR\+?\b|"
           r"\bICER\b|cost per (QALY|case|diagnosis)|number needed to")

_PROVENANCE = (r"\bsimulat\w+|in silico|synthetic|hypothetical|illustrative|"
               r"\bmodel(l)?ed\b|\bprojected\b|\bexpected under\b|not (measured|observed) in patients|"
               # a figure derived analytically from borrowed parameters is not
               # "simulated"; saying where it came from is the disclosure.
               r"\bborrowed\b|\bderived from\b|\bdemonstration of the mechanism\b|"
               # an explicitly published figure is also provenance-stated; the
               # rule is about unattributed numbers, not about the word
               # "simulated" in particular
               r"\bpublished estimate|\bas published\b|"
               r"\bnot as a calibrated\b|\bszimul\w+")


_FUTURE = (r"\bwill\b|\bwould\b|\bplanned?\b|\bproposed?\b|\bto be (recruited|enrolled|"
           r"fitted|estimated|measured|tested)\b|\bwe commit\b|\bis designed\b|\bare designed\b|"
           r"\bwe (propose|outline|set out|describe)\b|\bprospective\w*\b|\bcommits?\b|"
           r"\bbefore the first participant\b|\bthat supplies\b|\bthe sequence\b")


def _real_cohort_match(body):
    """A cohort that EXISTS, not one the paper promises.

    Added after a near-miss: describing a planned validation with the words
    "development cohort" matched the pattern and silenced the whole module on the very manuscript it was built from. A
    planned cohort is not a cohort."""
    for m in re.finditer(_REAL_COHORT, body, re.I):
        window = body[max(0, m.start() - 220):m.end() + 120]
        if re.search(_FUTURE, window, re.I):
            continue
        return m
    return None


def _is_review(doc):
    """A review reports other people's evaluations, so none of the provenance
    rules below apply to it. Judged on the title only: an abstract that says
    "we reviewed the literature" is said by most primary papers too."""
    if re.search(r"\breview\b|\bscoping\b|\bmeta-?analys|\b[aá]ttekint[eé]s\b",
                 title_of(doc), re.I):
        return True
    # a declared article type beats the title: one narrative review carried the
    # word only in an "**Article type:** Review" line above the abstract.
    return bool(re.search(r"(?mi)^\W*(article|manuscript|paper)\s*type\s*\W{0,3}\s*"
                          r"[^\n]{0,40}\b(review|meta-?analys|perspective|commentary)\b",
                          doc.sections.get("_preamble", "")))


def _is_simulation_paper(doc):
    """No patient-level cohort anywhere, and the evaluation is substantially
    simulated.

    Each clause is there because of a miss. Without the cohort test, every
    validation study that runs a sensitivity analysis trips the rules; without
    the review test, a narrative review that mentions simulation once is
    treated as having run one; and the count has to be more than one, because a
    single passing use of the word is not an evaluation."""
    if _is_review(doc):
        return False
    body = body_of(doc)
    if _real_cohort_match(body):
        return False
    if len(re.findall(_SIMULATED, body, re.I)) < 3:
        return False
    # and it has to be how the results were produced, not an aside in the discussion
    return bool(re.search(_SIMULATED, sec(doc, "abstract") + " " + sec(doc, "results")
                          + " " + sec(doc, "methods"), re.I))


def _presents_model(doc):
    if _is_review(doc):
        return False
    head = title_of(doc) + " " + sec(doc, "abstract") + " " + body_of(doc)[:4000]
    return bool(re.search(_MODEL, head, re.I))


# ── the rules ─────────────────────────────────────────────────────────────

def _simulated_metric_unlabelled(doc):
    """S-R1.3 — performance figures that come from simulation, not patients,
    and need saying so wherever they appear.

    The referee's point is placement, not disclosure: the manuscript did say so,
    in its limitations. So this rule deliberately ignores the limitations
    paragraph and reads the four places the referee named."""
    if not _is_simulation_paper(doc):
        return []
    out = []
    places = (("abstract", sec(doc, "abstract")),
              ("results", sec(doc, "results")),
              ("conclusions", sec(doc, "conclusions")))
    for where, text in places:
        for s in sentences(text):
            if not re.search(_METRIC, s, re.I) or not re.search(r"\d", s):
                continue
            if re.search(_PROVENANCE, s, re.I):
                continue
            out.append(F(CAT, ERROR, "simulation-metric-unlabelled",
                         f"A performance figure stated without saying it is simulated, "
                         f"in the {where}: \"{_q(s)}\"",
                         where=where,
                         fix="Carry the provenance in the sentence that carries the number — "
                             "'in simulation', 'under the modelled cohort'. A limitations "
                             "paragraph is not enough: the Abstract, Results, figures and "
                             "Conclusion are where the number gets quoted from."))
            break                       # one per place is the signal; more is noise
    return out


def _figure_caption_unlabelled(doc):
    """S-R1.3, the 'figures' half — a caption that reports a metric and does not
    say the data behind it are simulated. Captions travel without the paper."""
    if not _is_simulation_paper(doc):
        return []
    out = []
    for line in body_of(doc).splitlines():
        line = line.strip()
        if not re.match(r"^(\*\*)?(Figure|Fig\.?|Table)\s*\d+", line, re.I):
            continue
        if not re.search(_METRIC, line, re.I) or not re.search(r"\d", line):
            continue
        if re.search(_PROVENANCE, line, re.I):
            continue
        # A caption announcing pre-specified criteria states targets for a
        # future study, not results. Table 9 was a false positive here.
        if re.search(r"pre-?specified|falsification|success criteri|acceptance criteri|"
                     r"stopping rule|target value", line, re.I):
            continue
        out.append(F(CAT, WARN, "simulation-caption-unlabelled",
                     f"A display item reports a performance figure and the caption does not "
                     f"say it is simulated: \"{_q(line, 110)}\"",
                     where="figures",
                     fix="Put the word in the caption. A figure is lifted into slides and "
                         "into other papers without the sentence that qualified it."))
        if len(out) >= 3:
            break
    return out


def _model_maturity_overclaimed(doc):
    """S-R1.1 — maturity vocabulary in the title of a model that has never met
    a patient."""
    if not _is_simulation_paper(doc):
        return []
    head = title_of(doc) + " " + sec(doc, "abstract")
    # "adaptive" and "intelligent" are not on this list on their own: the first
    # one matched "adaptive immunity" in a microbiome title. They count only
    # when they modify the system itself.
    _SYS = r"(model|system|algorithm|framework|platform|classifier|engine|pipeline)"
    pat = (r"\bself-?learning\b|\bself-?improving\b|\bself-?correcting\b|\bAI-?(driven|powered|based)\b|"
           r"\bartificial intelligence[- ]driven\b|\bcontinuously learns?\b|"
           r"\blearns? from (every|each)\b|\bmachine[- ]learning " + _SYS + r"\b|"
           r"\b(adaptive|intelligent|autonomous)\s+" + _SYS + r"\b")
    hits = set()
    for m in re.finditer(pat, head, re.I):
        # a hedged use such as "a hypothesised learning system" is the fix a referee asks for,
        # not the overclaim; only an unhedged occurrence counts.
        # The hedge must attach to the word itself: a title that merely opens
        # with "Hypothesis" still drew the objection, which is why the window is
        # 24 characters and not the whole title.
        ctx = head[max(0, m.start() - 24):m.start()]
        if re.search(r"\bhypothesised\b|\bhypothesized\b|\bproposed\b|\bputative\b|"
                     r"\benvisaged\b|\bintended\b|\bprospective\b", ctx, re.I):
            continue
        hits.add(m.group(0).lower())
    if not hits:
        return []
    return [F(CAT, ERROR, "model-maturity-overclaimed",
              "Maturity vocabulary in the title or abstract of a model with no patient-level "
              f"cohort: {', '.join(sorted(hits))}.",
              where="title",
              fix="These words describe a system that has run; this one has been specified. "
                  "Either the title says what the paper is — a proposed, simulation-based "
                  "framework — or the first line of the abstract does, unmissably.")]


def _development_cohort_absent(doc):
    """S-R1.1 — no patient-level development or test cohort, in a paper that
    does not call itself a theoretical framework throughout.

    This is the rule cohort 8's `prediction-without-validation` could not be:
    that one goes quiet the moment the word AUC appears, which is precisely what
    a simulated evaluation produces in quantity."""
    if not _presents_model(doc):
        return []
    body = body_of(doc)
    if _real_cohort_match(body):
        return []
    declared = re.search(r"(theoretical|conceptual|simulation-based|proof[- ]of[- ]concept|"
                         r"hypothesis-generating|not (yet )?(clinically )?validated|"
                         r"no patients? (were|have been)|has not been (tested|validated) in patients)",
                         sec(doc, "abstract") + " " + title_of(doc), re.I)
    sev = WARN if declared else ERROR
    return [F(CAT, sev, "development-cohort-absent",
              "A model is presented and the manuscript names no training, validation or "
              "independent test cohort" +
              (" (the abstract does label it as theoretical, which is the mitigation a "
               "referee asked for — check the Results and Conclusion say it too)."
               if declared else ". Nothing in the title or abstract labels it as theoretical."),
              where="abstract",
              fix="Say what the paper is, in the title or the first abstract sentence and "
                  "again in the Conclusion: a framework specified and evaluated in "
                  "simulation, to be developed and validated. Cohort 8's "
                  "`prediction-without-validation` will not catch this — it falls silent as "
                  "soon as an AUC is printed, and a simulation prints many.")]


def _parameter_population_mismatch(doc):
    """S-R1.2 — a parameter measured in one population and applied to another."""
    body = body_of(doc)
    if not _presents_model(doc):
        return []
    out = []
    donor = (r"healthy (women|men|volunteers|controls|individuals|subjects|adults|donors)|"
             r"(the )?general population|blood donors|disease-free (controls|participants)|"
             r"normal (subjects|volunteers|range population)")
    for s in sentences(body):
        if not re.search(donor, s, re.I):
            continue
        if not re.search(r"\b(derived|taken|borrowed|obtained|estimated|adopted|drawn|based)\b"
                         r"[^.]{0,40}\b(from|on)\b|\bwe (used|applied|assumed)\b|\bvariation\b|"
                         r"\bcoefficient of variation\b|\bCV[vwi]?\b|\breference (change|interval)\b",
                         s, re.I):
            continue
        if re.search(r"provisional|until .{0,40}(estimated|measured)|differs from the target|"
                     r"may not (transfer|apply|hold)|caveat|limitation|target population "
                     r"(estimate|value) is (not|unknown)|"
                     # added after a false positive: two plain statements of
                     # the limit that the list above did not recognise.
                     r"\bnot from\b|rather than (measured|observed|from)\b|"
                     r"demonstration of the mechanism|not as a calibrated", s, re.I):
            continue
        out.append(F(CAT, WARN, "parameter-population-mismatch",
                     f"A parameter taken from a population other than the target one, with no "
                     f"note that it may not transfer: \"{_q(s)}\"",
                     where="methods",
                     fix="Name the donor population next to the parameter and mark the value "
                         "provisional until it is estimated in the target population. A "
                         "referee found one such borrowing and treated it as the test case "
                         "for all the others."))
        if len(out) >= 3:
            break
    return out


def _parameter_provenance_unseparated(doc):
    """S-R1.2, S-R1.5 — measured, borrowed and assumed parameters not told
    apart."""
    if not _presents_model(doc):
        return []
    body = body_of(doc)
    if not re.search(r"\bparameter|\bweight(s|ing)?\b|\bcoefficient|likelihood ratio|\bprior\b", body, re.I):
        return []
    marks = len(re.findall(r"\bassumed\b|\bassumption\b|\bprovisional\b|\bplaceholder\b|"
                           r"\bliterature-derived\b|\bexpert (opinion|judg)|\bimputed\b|"
                           r"\bderived (analytically|mathematically)\b|\bnot empirically\b|"
                           r"\bpending (estimation|measurement)\b", body, re.I))
    if marks >= 3:
        return []
    return [F(CAT, WARN, "parameter-provenance-unseparated",
              f"A parameterised model with {'no' if not marks else 'almost no'} vocabulary "
              "separating measured, borrowed and assumed values"
              + (f" ({marks} marker(s) in the whole text)." if marks else "."),
              where="methods",
              fix="One column, or one symbol, per parameter: measured in the target "
                  "population / borrowed from another population / assumed. Referees asked "
                  "for this separation twice in one report — once for the parameters and "
                  "once for the manuscript as a whole.")]


def _internal_validation_called_external(doc):
    """S-R1.4 — parameters estimated and performance judged in one cohort, which
    is internal validation under another name."""
    body = body_of(doc)
    if not re.search(r"\bprospective\w*\b", body, re.I):
        return []
    estimates = re.search(r"(estimate|derive|fit|calibrate|measure)\w*\s+(the\s+)?"
                          r"(missing|unknown|remaining|free|outstanding)?\s*parameters?|"
                          r"parameters? will be (estimated|derived|fitted|calibrated)", body, re.I)
    if not estimates:
        return []
    claims_external = re.search(r"\b(external|independent)\s+validat\w+", body, re.I)
    if not claims_external:
        return []
    separate = re.search(r"\b(separate|second|another|temporal|geographic\w*|different)\s+"
                         r"(cohort|centre|center|site|sample|dataset)|"
                         r"external validation (cohort|set|sample) will be (separate|distinct)|"
                         r"temporal validation", body, re.I)
    if separate:
        return []
    return [F(CAT, WARN, "internal-validation-called-external",
              "The same prospective cohort appears to both estimate the unknown parameters "
              "and furnish the 'external' or 'independent' validation, and no separate "
              "temporal or geographic cohort is named.",
              where="methods",
              fix="Fitting and judging in one cohort is development with internal "
                  "validation, whatever it is called. Say which parameters are frozen "
                  "before the cohort opens, and name the separate cohort that will test "
                  "the frozen model.")]


def _validation_roadmap_incomplete(doc):
    """S-R1.4 — no roadmap saying what will be estimated, what stays fixed, and
    where the final model will be tested."""
    body = body_of(doc)
    if not re.search(r"\bprospective\w*\b.{0,200}\b(stud(y|ies)|cohort|validat)", body, re.I | re.S):
        return []
    if not _presents_model(doc):
        return []
    frozen = re.search(r"\b(fixed|frozen|pre-?specified|locked|held constant|unchanged)\b"
                       r"[^.]{0,60}\b(parameter|weight|coefficient|model)|"
                       r"\b(parameter|weight|coefficient)s?\b[^.]{0,60}\b(fixed|frozen|"
                       r"pre-?specified|locked) (before|prior to)", body, re.I)
    if frozen:
        return []
    return [F(CAT, WARN, "validation-roadmap-incomplete",
              "A prospective study is proposed and the manuscript does not say which "
              "parameters are frozen before it opens.",
              where="methods",
              fix="Three lists make the roadmap answerable: estimated in the prospective "
                  "cohort, fixed before it, and tested afterwards in a separate cohort. "
                  "Without the middle list a referee cannot tell development from "
                  "validation, and will say so.")]


def _reference_standard_unspecified(doc):
    """S-R1.5 — a prospective accuracy study with no reference standard, or one
    named without addressing verification bias."""
    body = body_of(doc)
    if not _presents_model(doc):
        return []
    # a narrative review that says "prospective studies are needed" is not
    # proposing one; two reviews tripped this before the gate was tightened.
    if not re.search(r"\bprospective\s+(validation|accuracy|diagnostic|cohort|observational)\s*"
                     r"(stud(y|ies)|cohort|design)?|we (propose|plan|outline|describe|set out)"
                     r"[^.]{0,120}\bprospective\b", body, re.I):
        return []
    if not re.search(r"\bdiagnos\w+|\bdetect\w+|\bsensitivit|\bspecificit|\bPPV\b|\bNPV\b", body, re.I):
        return []
    named = re.search(r"\breference standard\b|\bgold standard\b|\bcase definition\b|"
                      r"\bdiagnosis will be (confirmed|established|defined)\b|"
                      r"\bconfirmed (by|at) (surgery|laparoscopy|histolog|biopsy)\b", body, re.I)
    bias = re.search(r"\bverification bias\b|\bwork-?up bias\b|\bpartial verification\b|"
                     r"\bdifferential verification\b|\bmisclassification\b", body, re.I)
    if named and bias:
        return []
    missing = []
    if not named:
        missing.append("no reference standard is named")
    if not bias:
        missing.append("verification bias is not addressed")
    return [F(CAT, ERROR if not named else WARN, "reference-standard-unspecified",
              "A prospective accuracy study is proposed and " + " and ".join(missing) + ".",
              where="methods",
              fix="Name what counts as a case and who gets that test. Verifying only the "
                  "high scorers inflates every accuracy figure the study will report; if "
                  "full verification is impractical, say which bias that buys and how it "
                  "is handled.")]


RULES_COHORT_9 = [
    _simulated_metric_unlabelled, _figure_caption_unlabelled, _model_maturity_overclaimed,
    _development_cohort_absent, _parameter_population_mismatch,
    _parameter_provenance_unseparated, _internal_validation_called_external,
    _validation_roadmap_incomplete, _reference_standard_unspecified,
]


def _borrowed_parameter_sensitivity(doc):
    """E-R1.4: a parameter borrowed from another population and no analysis of
    what happens if it is wrong. `parameter-population-mismatch` asks for a note;
    the second referee asked for the number."""
    if not _is_simulation_paper(doc):
        return []
    body = body_of(doc)
    if not has(body, r"healthy (?:volunteers?|women|controls|subjects|individuals)", r"general population",
               r"\bborrowed\b"):
        return []
    if not has(body, r"\bparameter", r"biological variation", r"\bCV_?[AI]?\b"):
        return []
    if has(body, r"sensitivity analys\w*[^.]{0,120}(?:parameter|variation|CV|inflat)",
           r"(?:parameter|variation|CV|inflat)\w*[^.]{0,120}sensitivity analys",
           r"\binflat\w+[^.]{0,60}(?:CV|variation|parameter)"):
        return []
    return [F(CAT, WARN, "borrowed-parameter-no-sensitivity",
              "A parameter is borrowed from another population and no sensitivity analysis shows "
              "what happens if it does not transfer.", where="methods",
              fix="Vary it over a plausible range in the target population and report the change "
                  "in the output.")]


def _projection_language(doc):
    """E-R1.1: model projections written as findings. In a simulation-only paper,
    'confirms' on a number is a claim about patients that the model cannot make."""
    if not _is_simulation_paper(doc):
        return []
    hits = [s for s in sentences(body_of(doc))
            if re.search(r"\bconfirms?\b|\bconfirmed\b|\bproves?\b|\bwill (?:detect|save|prevent|reduce)\b", s, re.I)
            and re.search(r"\d", s)
            and not re.search(r"\(\s*\d{1,3}(?:\s*[,–-]\s*\d{1,3})*\s*\)|\[\s*\d", s)
            and not re.search(r"\bproject\w+|\bsimulat\w+|\bwould\b|\bcould\b|\billustrat\w+|\bif\b|"
                              r"\bbiopsy|\bhistolog|\bsurgical\w*|\blaparoscop", s, re.I)]
    if len(hits) >= 2:
        return [F(CAT, WARN, "projection-language-unmarked",
                  f"{len(hits)} sentences state model output as fact, e.g. “{_q(hits[0])}”.",
                  where="results",
                  fix="Move projections into a labelled section with a disclaimer, and write them "
                      "as projected.")]
    return []


# Cohort 13: the same paper, read by a second referee and then by the editor.
RULES_COHORT_9 += [_borrowed_parameter_sensitivity, _projection_language]


def check_sim(doc, profile):
    out = []
    for rule in RULES_COHORT_9:
        try:
            out.extend(rule(doc))
        except Exception as exc:                      # a rule must never take the run down
            out.append(F(CAT, INFO, "rule-error",
                         f"{rule.__name__} could not run ({exc.__class__.__name__}).",
                         fix="Report this; the other rules are unaffected."))
    return out
