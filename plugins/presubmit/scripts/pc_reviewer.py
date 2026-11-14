"""Reviewer-anticipation checks.

The other checkers in this plugin catch what an editorial office catches — a
duplicate reference, a missing disclosure, an over-long abstract. This one
catches what a *reviewer* writes back about, which is a different list: not
whether the parts are present, but whether a claim is carried by what is in the
paper.

Every rule here comes from a real referee report, and each carries the comment it
came from in its `origin` so that a flagged finding can be read as "someone
already asked this". The first cohort is three referee reports on one review;
the rules are written for any manuscript, not for that one, and the reference
file `references/reviewer-patterns.md` keeps the mapping.

Nothing here is a language model. Each rule looks for a claim of a particular
shape and then asks whether the sentence that would have to support it exists.
That means the module is honest about what it cannot see: it reports a *missing
guard*, never a wrong result, and every message says which guard it looked for.
"""
from __future__ import annotations

import re

import pc_lib
from pc_lib import F, ERROR, WARN, INFO, word_count

CAT = "reviewer"

# ─────────────────────────────────────────────────────────────── helpers ──
# a sentence ends at . ! or ? followed by whitespace and an upper-case letter,
# a digit, a bracket or a quote. Splitting on every full stop broke a decimal
# number in two and hid the one number several referees asked about.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u00C0-\u017F\d\[\(\"\u201C])")


def _split_sentences(line):
    return [s.strip() for s in _SENT_SPLIT.split(line) if s.strip()]


def sentences(text):
    """Split per line first: a document is not one long sentence, and treating
    it as one makes every quoted excerpt come from the wrong place."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        out.extend(_split_sentences(line) or [line])
    return out


def paragraphs_with_sentences(text):
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        for s in _split_sentences(line) or [line]:
            yield line, s


def has(text, *patterns):
    return any(re.search(p, text or "", re.I) for p in patterns)


def sec(doc, *keys):
    """Body of the first section present among `keys`, else ''."""
    for k in keys:
        v = doc.sections.get(k)
        if v:
            return v
    return ""


def title_of(doc):
    pre = doc.sections.get("_preamble", "")
    for line in pre.splitlines():
        line = line.strip()
        if len(line) > 25:
            return line
    return ""


def cited(sentence):
    """Does this sentence carry a citation of any common flavour?"""
    # Vancouver numeric citations in parentheses — (61), (6, 30), (19, 18) — are
    # the style most medical journals require, and they were not recognised: a
    # correctly cited cut-off was reported as unsourced.
    # "(0.20)" and "(2024)" cannot match: a decimal point breaks the digit run,
    # and a four-digit year is handled by its own branch above.
    return bool(re.search(r"\[\s*\d|\(\s*\d{4}\s*\)|\bet al\b|\(\s*[A-Z][a-z]+,"
                          r"|\(\s*\d{1,3}(\s*,\s*\d{1,3})*\s*\)", sentence))


# ─────────────────────────────────────────────────── the rules, in order ──
def _design_self_description(doc):
    """R1.8 / R2.1 — systematic machinery described as a narrative review."""
    text = doc.text
    if not has(text, r"\bnarrative review\b"):
        return []
    systematic = sum(bool(has(text, p)) for p in
                     (r"\bPRISMA\b", r"\bscreen(ing|ed)\b", r"\beligibility criteria\b",
                      r"\bdeduplicat", r"\brisk of bias\b", r"\bflow diagram\b"))
    if systematic < 3:
        return []
    disclaimed = has(text,
                     r"not a (registered )?systematic review",
                     r"is not a systematic review",
                     r"without meta-analysis",
                     r"structured evidence map")
    if disclaimed:
        return []
    return [F(CAT, ERROR, "design-self-description",
              "The paper calls itself a narrative review while describing "
              "systematic machinery (PRISMA, screening, eligibility, risk of bias). "
              "A reviewer will read that as a systematic review without "
              "meta-analysis and ask why it is not registered.",
              where="methods",
              fix="State early in the Methods what it is not — 'not a registered "
                  "systematic review, not a systematic review with meta-analysis' — "
                  "then say which components are systematic, which are narrative, "
                  "and why no estimate is pooled.")]


def _absolute_title(doc):
    """R2.3 — a title that claims more than the data can carry."""
    t = title_of(doc)
    if not t:
        return []
    hits = [w for w in ("not accuracy", "never", "always", "proves", "proof that",
                        "definitive", "the first", "unprecedented", "solves")
            if re.search(rf"\b{re.escape(w)}\b", t, re.I)]
    if not hits:
        return []
    return [F(CAT, WARN, "absolute-title",
              f"The title makes an absolute claim ({', '.join(hits)}).",
              where="title",
              fix="Prefer a comparative to a denial — 'more than' rather than "
                  "'not' — unless every study in the corpus supports the absolute "
                  "form. A reviewer who disagrees with the title argues with the "
                  "whole paper.")]


def _single_database(doc):
    """R1.11 / R2.2 — one database, and whether the limitation admits it."""
    methods = sec(doc, "methods")
    if not methods:
        return []
    named = {d for d in ("PubMed", "MEDLINE", "Embase", "Scopus", "Web of Science",
                         "CINAHL", "Cochrane", "IEEE", "Google Scholar")
             if re.search(rf"\b{re.escape(d)}\b", methods, re.I)}
    if len(named) != 1:
        return []
    only = named.pop()
    limits = sec(doc, "discussion", "conclusions") + doc.text
    admits = has(limits, rf"{re.escape(only)} only", r"\bsearched (only|a single)\b",
                 r"were not searched", r"single[- ]database")
    if admits:
        others = [d for d in ("Embase", "Scopus", "Web of Science", "CINAHL",
                              "Cochrane", "grey literature", "citation chasing")
                  if re.search(re.escape(d), limits, re.I)]
        if len(others) >= 2:
            return []
        return [F(CAT, INFO, "single-database-limitation-thin",
                  f"The limitation admits that only {only} was searched but does "
                  f"not name what was not searched.",
                  where="discussion",
                  fix="Name the databases and sources you did not search, say "
                      "which parts of the literature that under-covers, and say "
                      "that the direction of the resulting bias is unknown. "
                      "'A limitation' is not a limitation until it is specific.")]
    return [F(CAT, WARN, "single-database-search",
              f"The search names only {only}, and no limitation says so.",
              where="methods",
              fix=f"Say in the Methods that identification was complete within "
                  f"{only} and not across databases, name what was not searched, "
                  f"and say in the limitations which parts of the literature that "
                  f"under-covers — and that the direction of the bias is unknown.")]


def _appraised_subset(doc):
    """R1.9 — a subset appraised, with no percentage and no direction of bias."""
    text = doc.text
    if not has(text, r"\bcore set\b", r"\bsubset of\b", r"\bpriority score\b",
               r"\bpurposive(ly)? (sampled|selected)\b"):
        return []
    out = []
    # a percentage somewhere in the Results is not the same as the share this
    # stratum represents, so look for one beside the sentence that selects it
    near = ""
    for m in re.finditer(r"\bcore set\b|\bpriority score\b", text, re.I):
        near += text[max(0, m.start() - 400):m.end() + 400]
    if not re.search(r"\b\d{1,2}(\.\d)?%", near):
        out.append(F(CAT, WARN, "subset-share-unstated",
                     "A selected subset was appraised, but the share it "
                     "represents of the eligible set is not stated as a percentage.",
                     where="methods",
                     fix="Give the arithmetic in the Methods: n of N, and the "
                         "percentage. Reviewers compute it anyway."))
    if not has(text, r"upper bound", r"over-?estimate", r"selection bias",
               r"biases? the proportions?"):
        out.append(F(CAT, ERROR, "subset-bias-direction",
                     "A subset selected on quality-correlated criteria is "
                     "appraised, and no sentence states the direction of the "
                     "resulting bias.",
                     where="methods",
                     fix="If the selection rule rewards the very properties being "
                         "counted, say so where the proportions are reported: they "
                         "are upper bounds, and saying it first is stronger than "
                         "being told."))
    return out


def _fulltext_availability(doc):
    """R1.10 — a flow diagram that never says how many texts were unreachable."""
    text = doc.text
    if not has(text, r"\bPRISMA\b", r"\bflow diagram\b"):
        return []
    if has(text, r"full text (was )?(not )?(available|retriev|obtain|access)",
           r"could not be (retrieved|obtained)", r"not (retrievable|accessible)"):
        return []
    return [F(CAT, WARN, "fulltext-availability-unreported",
              "A PRISMA flow is reported, but nothing says how many eligible "
              "records had no retrievable full text.",
              where="methods",
              fix="Report the count, and say exactly what was measured — "
                  "'not deposited in PubMed Central' is not the same claim as "
                  "'could not be obtained', and a reviewer will know the difference.")]


def _term_defined(doc):
    """R1.2 / R2.7 — a load-bearing term used without a stated rule."""
    out = []
    # a term is load-bearing only if the paper leans on it; one passing use of
    # "real-world" is not a definition failure, and flagging it would train the
    # reader to ignore the category
    for term, floor, guard in (("external validation", 2,
                                (r"we (define|treat|count)", r"under the rule",
                                 r"follows TRIPOD", r"defined as", r"our definition",
                                 r"we consider .{0,40}external")),
                               ("clinically significant", 3,
                                (r"defined as", r"threshold of", r"we define")),
                               ("real[- ]world", 4,
                                (r"defined as", r"we mean", r"we use the term")),
                               # D-R1.1 / D-R2.6: one word in several senses, none stated
                               ("prevention", 12,
                                (r"operational definition", r"we (define|use) .{0,30}prevention",
                                 r"prevention (is|was) defined", r"defined as .{0,60}prevention",
                                 r"criteria for (assigning|classifying)",
                                 r"we (therefore )?classify", r"by (two|three|the following) criteria")),
                               # D-R1.7: a term carried the argument and was never defined
                               ("dysbiosis", 6,
                                (r"dysbiosis[^.]{0,80}(defin|refers to|we mean|used here|"
                                  r"used in this|denote|understood as|is taken to)",
                                 r"(define|definition of|the term|the label)[^.]{0,30}dysbiosis"))):
        # counted in the body only: an English reference list is not the paper
        # leaning on the term, and it put one manuscript over the floor
        if len(re.findall(term, body_of(doc), re.I)) < floor:
            continue
        window = doc.text
        if any(re.search(g, window, re.I) for g in guard):
            continue
        out.append(F(CAT, ERROR, "undefined-load-bearing-term",
                     f"'{term}' carries conclusions but no sentence states the "
                     f"rule by which it is applied.",
                     where="methods",
                     fix="State the rule, name the main alternative convention, "
                         "say why you did not adopt it, and say which direction "
                         "your choice moves your own headline number."))
    # a rule that is stated but not defended is the next thing a referee asks about
    if len(re.findall(r"external validation", doc.text, re.I)) >= 3 and \
            not any(f.code == "undefined-load-bearing-term" for f in out) and \
            not has(doc.text, r"alternative (convention|framework|reading)",
                    r"internal.external cross-validation", r"a looser convention",
                    r"others treat", r"unlike .{0,30}we count"):
        out.append(F(CAT, WARN, "definition-not-defended",
                     "The rule for 'external validation' is stated but never "
                     "weighed against the competing convention.",
                     where="methods",
                     fix="Name the alternative reading, say why you did not adopt "
                         "it, and say which way your choice moves your own headline. "
                         "A definition that only ever favours the author reads as "
                         "chosen for the result."))
    return out


def _small_denominator(doc):
    """R1.3 — a striking proportion on a small denominator, with no interval."""
    out = []
    for m in re.finditer(r"\bnone of the (\d{1,3})\b|\ball (\d{1,3}) of\b|"
                         r"\b(\d{1,2}) of the (\d{1,2})\b", doc.text, re.I):
        n = next((int(g) for g in m.groups()[::-1] if g), None)
        if n is None or n > 40:
            continue
        tail = doc.text[m.end():m.end() + 220]
        if re.search(r"\b(95%\s*CI|confidence interval|\bCI\b)", tail, re.I):
            continue
        out.append(F(CAT, WARN, "small-denominator-no-interval",
                     f"A categorical claim on a denominator of {n} "
                     f"('{m.group(0).strip()}…') is stated without an interval.",
                     where="results",
                     fix="Give the interval and name the denominator that makes it "
                         "wide. A zero out of 18 is a real finding and a loose bound "
                         "at the same time; say both."))
        if len(out) >= 3:
            break
    return out


def _demonstrated_without_citation(doc):
    """R1.6 — 'each of these has been demonstrated', and nothing points at one."""
    out = []
    for para, s in paragraphs_with_sentences(doc.text):
        if not re.search(r"\b(has|have) been (demonstrated|shown|established|proven)\b"
                         r"|\bit is well (known|established)\b", s, re.I):
            continue
        # a sentence describing what someone would wrongly conclude is not
        # itself a claim that the thing was shown
        if re.search(r"\b(would|will conclude|might|appears? to|wrongly|"
                     r"at face value|as though|even if|unless)\b", s, re.I):
            continue
        # the claim may point back at citations given a sentence earlier; what
        # cannot stand is a paragraph that asserts prior work and cites none
        if cited(s) or cited(para):
            continue
        out.append(F(CAT, ERROR, "demonstrated-uncited",
                     f"Claim of prior demonstration with no citation in the "
                     f"sentence: \"{s[:110].strip()}…\"",
                     where="introduction",
                     fix="Cite one study per claim, not one citation per paragraph. "
                         "If the claims come from your own corpus, say so — it makes "
                         "them checkable against your appraisal."))
        if len(out) >= 4:
            break
    return out


def _ranking_claim(doc):
    """R1.4 — a ranking, which depends on how the ranking was constructed."""
    out = []
    for s in sentences(doc.text):
        if not re.search(r"\b(leading|foremost|top|greatest|largest|principal) "
                         r"(causes?|killers?|threats?)\b|\bamong the leading\b", s, re.I):
            continue
        if re.search(r"\b(depends on|ranking|attributed|how causes)", s, re.I):
            continue
        out.append(F(CAT, WARN, "ranking-claim",
                     f"A ranking claim: \"{s[:110].strip()}…\"",
                     where="introduction",
                     fix="A rank depends on how causes are attributed and grouped, "
                         "in a way the underlying estimate does not. Quote the "
                         "estimate, cite the source that produced it, and say that "
                         "the ranking is method-dependent."))
        if len(out) >= 2:
            break
    return out


def _figures_ambiguity(doc):
    """R1.5 — 'these figures' meaning numbers, in a paper with numbered Figures."""
    if not re.search(r"\bFigure\s+\d", doc.text):
        return []
    hits = [s for s in sentences(doc.text)
            if re.search(r"\b(these|those) figures\b(?!\s+\d)", s, re.I)]
    if not hits:
        return []
    return [F(CAT, INFO, "figures-ambiguity",
              f"'figures' is used to mean numbers in a paper that also has "
              f"numbered Figures: \"{hits[0][:100].strip()}…\"",
              where="text",
              fix="Use 'estimates', 'counts' or 'proportions' for numbers, and "
                  "reserve 'Figure' for the artwork.")]


def _gap_statement(doc):
    """R1.7 / R3.2 — the reader asks what is new and the Introduction does not say."""
    intro = sec(doc, "introduction")
    if not intro:
        return []
    if has(intro, r"\bgap\b", r"\bwhat (this|the present) (review|study|work) adds\b",
           r"\bnovelt", r"\bfor the first time\b", r"\bno previous\b", r"\bnone of (them|these)\b",
           r"\bhi[aá]ny(t|a|p[oó]tl)", r"korl[aá]tozott [^.]{0,30}adat", r"kev[eé]s [^.]{0,20}adat",
           r"\bels[oő]k[eé]nt\b", r"nem (ismert|vizsg[aá]lt)",
           r"little is known",
           r"remains? (unknown|unclear|poorly (understood|characteri[sz]ed)|to be)",
           r"has (not|never) (yet )?been (studied|examined|investigated|reported|addressed|explored)",
           r"to (the best of )?our knowledge",
           r"\bscarce\b",
           r"limited (evidence|data|information)",
           r"\black(ing)? of\b|\bis lacking\b",
           r"\bunexplored\b|\bunderstudied\b|\bnot well\b",
           r"\bno (prior|published) (stud|review|report)"):
        return []
    return [F(CAT, WARN, "gap-not-stated",
              "The Introduction never states the gap or what this work adds "
              "that the cited work does not.",
              where="introduction",
              fix="Give it its own paragraph at the end of the Introduction, with "
                  "numbered points, each naming what previous work does instead. "
                  "Two of the three reports behind this rule asked for exactly this.")]


def _prior_work_described(doc):
    """R3.2 — previous studies cited in a list rather than described."""
    intro = sec(doc, "introduction")
    if not intro:
        return []
    listy = re.findall(r"\[[\d,\s–-]+\][,.;]", intro)
    described = len(re.findall(r"\b(and colleagues|et al\.)\s", intro))
    if len(listy) < 4 or described >= 3:
        return []
    return [F(CAT, WARN, "prior-work-listed-not-described",
              f"The Introduction cites previous work as bare markers "
              f"({len(listy)} such runs) and describes almost none of it.",
              where="introduction",
              fix="Describe each comparable study — scope, size, instrument, "
                  "finding — and, if there are more than four, put them in a table "
                  "with your own work as the last row, limitations included.")]


def _discussion_novelty(doc):
    """R3.3 — novelty stated as aims in the Introduction and never as findings."""
    disc = sec(doc, "discussion")
    if not disc:
        return []
    if has(disc, r"\bnew to this literature\b", r"\bwhat this (study|review) adds\b",
           r"\bnovel(ty)?\b", r"\bhas not (previously )?been (reported|measured)\b",
           r"\bno previous (review|study)\b", r"\bels[oő]k[eé]nt\b", r"\bel[oő]sz[oö]r\b",
           r"korábban nem (vizsg[aá]lt|k[oö]z[oö]lt|mért)", r"\búj (eredm[eé]ny|adat)",
           r"\b(the )?first (study|report|time|to)\b",
           r"\bnew (finding|evidence|insight|data)",
           r"\b(adds|extends|expands) (to|on|the)\b",
           r"\bin contrast (to|with)\b",
           r"\bunlike (previous|prior|earlier)\b",
           r"\bnot (previously|yet) (reported|described)\b",
           r"\bto our knowledge\b",
           r"\bhas not (previously )?been (described|shown|examined)\b"):
        return []
    return [F(CAT, WARN, "discussion-novelty-absent",
              "The Discussion never says which of the findings are new, as "
              "opposed to which confirm previous work.",
              where="discussion",
              fix="State novelty as findings with their numbers, not as aims, and "
                  "keep it separate from the paragraph on agreement with prior work.")]


def _conclusions_perspectives(doc):
    """R3.4 — conclusions that end on a principle rather than on a next step."""
    con = sec(doc, "conclusions")
    if not con:
        return []
    if has(con, r"\bnext step\b", r"\bfuture (work|research|studies)\b",
           r"\bshould (be|now) (done|performed|tested)\b", r"\bthe study that should follow\b",
           r"\bwe (will|plan to)\b", r"\bwhat follows\b",
           r"tov[aá]bbi kutat[aá]s", r"\bfolytat[aá]sk[eé]nt\b", r"\bj[oö]v[oő]be(n|li)\b",
           r"javasolt [^.]{0,40}(vizsg[aá]lat|felm[eé]r[eé]s|kutat[aá]s)",
           r"\bfuture (trials|investigations|directions)\b",
           r"\bfurther (work|research|studies|trials|investigation)\b",
           r"\bwarrant",
           r"\bremains? to be\b",
           r"\bshould (be|now) (explored|examined|investigated|evaluated|confirmed|validated)\b",
           r"\b(longitudinal|prospective|randomi[sz]ed) (studies|trials|designs?)\b",
           r"\bneeds? to be\b"):
        return []
    return [F(CAT, WARN, "conclusions-without-perspective",
              "The Conclusions do not say what should be done next.",
              where="conclusions",
              fix="Give the next steps in the order their dependencies impose, each "
                  "with an outcome that would falsify what precedes it. 'Concrete "
                  "perspectives' is the phrase referees use for this.")]


def _proposal_marked(doc):
    """R2.4 — a design presented in the indicative, as though it existed."""
    text = doc.text
    proposes = has(text, r"\bwe propose\b", r"\bproposed (platform|system|device|architecture)\b",
                   r"\bthe platform\b", r"\bour (design|architecture)\b")
    if not proposes:
        return []
    marks = sum(bool(has(text, p)) for p in
                (r"design specification", r"testable hypothes", r"\bhypothetical\b",
                 r"no performance data", r"has not been (built|characterised|characterized)",
                 r"\bwould be\b"))
    if marks >= 3:
        return []
    return [F(CAT, ERROR, "proposal-unmarked",
              "A system is proposed but is described in the language of "
              "something that exists.",
              where="results/discussion",
              fix="Mark it as a proposal in the section heading, in the opening "
                  "paragraph and sentence by sentence: 'would be', not 'is'. Keep "
                  "the arithmetic of the specification in the present tense — what "
                  "is uncertain is the device, not the sum — and say that.")]


def _validation_pathway(doc):
    """R2.5 / R2.6 — a proposal with no falsification path and no endpoint order."""
    text = doc.text
    if not has(text, r"\bwe propose\b", r"\bproposed (platform|system|device|architecture)\b"):
        return []
    # a lifestyle framework or a treatment argument is a proposal too, but it has no
    # limit of detection; the analytical pathway is asked of things that measure
    if not has(text, r"\bassay\b", r"\bsequencing\b", r"\bclassifier\b", r"\bbiomarker",
               r"point[- ]of[- ]care", r"limit of detection",
               r"diagnostic (accuracy|test|platform|tool|device)"):
        return []
    out = []
    if not has(text, r"analytical valid", r"limit of detection", r"\bLoD\b",
               r"inclusivity and exclusivity"):
        out.append(F(CAT, ERROR, "no-analytical-pathway",
                     "A diagnostic or measurement system is proposed with no "
                     "analytical validation pathway.",
                     where="discussion",
                     fix="Stage it: analytical validity first, with named "
                         "experiments and acceptance criteria; then clinical "
                         "validity; then utility. Say that failure at any stage "
                         "stops the next, and say how much of stage one is done."))
    if has(text, r"\bAUC\b", r"\barea under the curve\b", r"\bdiscrimination\b") and \
       not has(text, r"primary endpoint", r"endpoint hierarchy", r"clinical utility",
               r"time to (appropriate|effective) therapy"):
        out.append(F(CAT, WARN, "endpoint-hierarchy-absent",
                     "Discrimination is discussed as the measure of success with "
                     "no clinical endpoint named above it.",
                     where="discussion",
                     fix="Name the hierarchy: analytical validity, then calibration "
                         "as a primary endpoint wherever decisions are "
                         "threshold-driven, then the clinical outcome. Say "
                         "explicitly that no AUC is a primary endpoint."))
    return out


def _universal_interval(doc):
    """R2.10 — a turnaround or timeline given as though it were universal."""
    out = []
    for m in re.finditer(r"\b(\d{1,3})\s*(?:to|–|-)\s*(\d{1,3})\s*(hours?|days?|minutes?)\b",
                         doc.text, re.I):
        window = doc.text[max(0, m.start() - 200):m.end() + 320]
        if re.search(r"\b(varies|not universal|depends on|typically|median|"
                     r"in our (setting|institution)|shorter where|longer for)\b",
                     window, re.I):
            continue
        out.append(F(CAT, INFO, "universal-interval",
                     f"An interval is stated without qualification: "
                     f"'{m.group(0)}'.",
                     where="introduction",
                     fix="Say what makes it shorter and what makes it longer, then "
                         "say why the unqualified interval is still the right one to "
                         "argue from."))
        break
    return out


def _terminology_relationships(doc):
    """R2.11 — overlapping terms counted as though they partitioned the corpus."""
    text = doc.text
    fam = [t for t in ("artificial intelligence", "machine learning", "deep learning")
           if re.search(t, text, re.I)]
    if len(fam) < 3:
        return []
    near = ""
    for m in re.finditer(r"deep learning", text, re.I):
        near += text[max(0, m.start() - 500):m.end() + 500]
    if has(near, r"subset of machine learning", r"\bnested\b",
           r"overlap rather than partition", r"⊃"):
        return []
    return [F(CAT, WARN, "terminology-relationship-undefined",
              "Artificial intelligence, machine learning and deep learning are "
              "all used, and their relationship is never stated.",
              where="introduction",
              fix="Define them once and say they are nested, so any counts by "
                  "class overlap rather than partition the corpus — and say that "
                  "the appraisal applies to the model inside a study, not to the "
                  "label its authors chose.")]


def _rob_method_detail(doc):
    """R2.8 — a risk-of-bias tool named, with no account of how it was applied."""
    text = doc.text
    tools = [t for t in ("PROBAST", "QUADAS", "ROBINS", "RoB 2", "AMSTAR", "QUIPS",
                         "Newcastle-Ottawa", "GRADE")
             if re.search(rf"\b{re.escape(t)}", text, re.I)]
    if not tools:
        return []
    out = []
    if not has(text, r"\b(two|three|independent(ly)?) (reviewers?|assessors?|coders?)\b",
               r"single (assessor|reviewer|coder)", r"\bone (assessor|reviewer|coder)\b"):
        out.append(F(CAT, ERROR, "rob-assessors-unstated",
                     f"{tools[0]} is applied and the number of assessors is never "
                     f"stated.",
                     where="methods",
                     fix="Say how many people appraised, and if it was one, say so "
                         "plainly and name it as the principal weakness. A reviewer "
                         "who has to ask will assume the worse answer."))
    if not has(text, r"\bkappa\b", r"\bagreement\b", r"\binter-?rater\b", r"\badjudicat"):
        out.append(F(CAT, WARN, "rob-reliability-unmeasured",
                     f"{tools[0]} judgments carry the conclusions, and no "
                     f"reliability is reported for them.",
                     where="methods",
                     fix="Measure it rather than asserting it: re-code the items "
                         "the conclusions rest on, report agreement and kappa per "
                         "item, and supply the adjudicated disagreements."))
    return out


def _abstract_order(doc):
    """R3.1 — an abstract whose order does not follow the paper's own."""
    ab = sec(doc, "abstract")
    if not ab or word_count(ab) < 80:
        return []
    # a structured abstract carries its moves as labels; the cue words below
    # are for one unstructured paragraph and misread a labelled one
    if len(re.findall(r"(?m)^(Background|Introduction|Objectives?|Methods?|Results|"
                      r"Conclusions?|Bevezet[eé]s|C[eé]lkit[uű]z[eé]s|M[oó]dszers?|"
                      r"Eredm[eé]nyek|K[oö]vetkeztet[eé]sek?)\s*:", ab)) >= 3:
        return []
    cues = [("background", r"\b(is|are) (widely )?(proposed|recognised|recognized|"
                          r"unclear|a (growing|major) )|remains? unclear"),
            ("methods", r"\bwe (searched|appraised|included|analysed|analyzed)\b"),
            ("results", r"\b\d{1,3}(\.\d)?%|\bodds ratio\b|\bwere (externally )?"),
            ("proposal", r"\bwe (derive|propose|specify|present a)\b|"
                          r"\bdesign (constraints?|specification)\b"),
            ("conclusion", r"\b(we conclude|limit this field|these findings|"
                           r"suggests? that)\b")]
    pos = []
    for name, pat in cues:
        m = re.search(pat, ab, re.I)
        pos.append((name, m.start() if m else None))
    seen = [p for p in pos if p[1] is not None]
    missing = [n for n, p in pos if p is None]
    out = []
    if missing:
        out.append(F(CAT, INFO, "abstract-missing-move",
                     f"The abstract has no recognisable {', '.join(missing)} move.",
                     where="abstract",
                     fix="One unstructured paragraph can still follow the paper's "
                         "own order; referees ask for that when it does not."))
    order = [n for n, _ in seen]
    if order != sorted(order, key=lambda n: [c[0] for c in cues].index(n)):
        out.append(F(CAT, WARN, "abstract-out-of-order",
                     f"The abstract's moves run {' → '.join(order)}, which is not "
                     f"the order of the paper.",
                     where="abstract",
                     fix="Put them in the manuscript's sequence. Ending on a "
                         "caveat instead of on the finding is the usual symptom."))
    return out


RULES_COHORT_1 = [
    _design_self_description, _absolute_title, _single_database, _appraised_subset,
    _fulltext_availability, _term_defined, _small_denominator,
    _demonstrated_without_citation, _ranking_claim, _figures_ambiguity,
    _gap_statement, _prior_work_described, _discussion_novelty,
    _conclusions_perspectives, _proposal_marked, _validation_pathway,
    _universal_interval, _terminology_relationships, _rob_method_detail,
    _abstract_order,
]


def check_reviewer(doc, profile):
    out = []
    for rule in RULES:
        try:
            out.extend(rule(doc))
        except Exception as exc:                      # a rule must never take the run down
            out.append(F(CAT, INFO, "rule-error",
                         f"{rule.__name__} could not run ({exc.__class__.__name__}).",
                         fix="Report this; the other rules are unaffected."))
    return out


# ═══════════════════════════════════════════════════ cohorts 2 – 6 ═══════
# Added 2026-09-12 from every referee report the author has received since
# the first cohort. Codes in the docstrings:
#   D-R1.n / D-R2.n   cohort 2, a review; two referees, 52 points.
#   M-AE.n / M-R1..3  cohort 3, a review; academic editor + three referees,
#                     30 points.
#   O-Ed / O-R1 / O-R2 cohort 4, a Hungarian review; editor + two referees,
#                     43 points.
#   A-Ed.n / A-R1..3  cohort 5, an opinion piece; editors + three referees,
#                     37 points.
#   T-A..T-F          cohort 6, a long-form work in Hungarian; a six-part
#                     report, 109 points.
# The reference file maps every code below to the points it came from.

import datetime as _dt

_DB = (r"PubMed|MEDLINE|Embase|Scopus|Web of Science|CINAHL|Cochrane|IEEE|"
       r"Google Scholar|PsycINFO|LILACS|adatb[aá]zis")
_MONTHS = (r"January|February|March|April|May|June|July|August|September|"
           r"October|November|December|janu[aá]r|febru[aá]r|m[aá]rcius|[aá]prilis|"
           r"m[aá]jus|j[uú]nius|j[uú]lius|augusztus|szeptember|okt[oó]ber|"
           r"november|december")
_METRIC = (r"\bAUC\b|\bAUROC\b|\bc-statistic\b|odds ratio|\bOR\b\s*[=:]?\s*\d|"
           r"\bRR\b\s*[=:]?\s*\d|hazard ratio|\bHR\b\s*[=:]?\s*\d|95%\s*CI|"
           r"sensitivity of|specificity of|\bAUC\s*[=:]")


def _year_now():
    return _dt.date.today().year


def body_of(doc):
    """Everything before the reference list."""
    ref = doc.sections.get("references", "")
    if ref and ref in doc.text:
        return doc.text.split(ref)[0]
    return doc.text


def is_review(doc):
    head = (title_of(doc) + " " + sec(doc, "abstract") + " " + doc.text[:600])
    return bool(re.search(r"\breview\b|\b[aá]ttekint[eé]s|\bscoping\b|\boverview\b",
                          head, re.I))


def is_hungarian(doc):
    return len(re.findall(r"\b(és|hogy|nem|vagy|mint|amely|ezért)\b", doc.text)) >= 40


def references_of(doc):
    """Reference entries: the References section if there is one, else the
    trailing run of numbered lines — a Hungarian manuscript whose heading
    was not recognised still has a bibliography."""
    from pc_checks import _reference_entries
    entries = _reference_entries(doc)
    if entries:
        return entries
    paras = [t for t, _ in doc.paragraphs]
    tail = paras[len(paras) // 2:]
    numbered = [re.sub(r"^\[?\d{1,3}[\].]\s*", "", t) for t in tail
                if re.match(r"^\[?\d{1,3}[\].]\s+\S", t)]
    return numbered if len(numbered) >= 8 else []


def _quote(s, n=100):
    return s.strip()[:n] + ("…" if len(s.strip()) > n else "")


# ---------------------------------------------------------------- rules --
def _placeholders(doc):
    """D-R1.16, D-R2.2, T-A-M2, T-B-m4, T-F-M3 — editorial placeholders in a
    submitted file. One report listed several of them back to the authors."""
    pats = (r"citation needed", r"\[(?:ref|cite|citation|source)[^\]]{0,40}\]",
            r"\bauthors? to (add|confirm|complete|insert|verify|supply)\b",
            r"\bTODO\b", r"\bTBD\b", r"\bXXX\b", r"\[degree\]", r"\[affiliation",
            r"\[insert", r"\bto be (added|inserted|confirmed|completed) (later|by)",
            r"Error! (Reference source|Bookmark) not found", r"\blorem ipsum\b",
            r"\[\?\]", r"\?\?\?", r"Word-?ben friss[uü]l", r"\bUpdate field\b",
            r"\bkieg[eé]sz[ií]tend[oő]\b", r"\bp[oó]toland[oó]\b",
            r"\bplaceholder\b", r"\[(name|author|year|journal|doi)\]")
    hits = []
    for pat in pats:
        for m in re.finditer(pat, doc.text, re.I):
            ctx = doc.text[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
            hits.append(ctx.strip())
            if len(hits) >= 3:
                break
        if len(hits) >= 3:
            break
    if not hits:
        return []
    return [F(CAT, ERROR, "editorial-placeholder",
              f"Editorial placeholder left in the text: "
              f"{' | '.join(_quote(h, 80) for h in hits)}",
              where="text",
              fix="Resolve every one before upload. A referee who finds "
                  "'citation needed' stops trusting the citations that are "
                  "there.")]


def _search_reporting(doc):
    """D-R1.3, D-R2.1, M-AE.1, M-R2.2, T-B-M6 (and R1.11) — a review whose
    search cannot be repeated. Five cohorts out of six asked for this; it is
    the single most-repeated objection in the whole corpus."""
    if not is_review(doc):
        return []
    body = body_of(doc)
    missing = []
    if not re.search(_DB, body, re.I):
        missing.append("database")
    if not re.search(rf"(?:{_MONTHS})\s+\d{{4}}|\d{{4}}\.?\s*(?:{_MONTHS})|"
                     r"\b(up to|through|until|as of|between|from)\s+(\w+\s+){0,2}(19|20)\d\d\b|"
                     r"\b(search(ed)?|keres[eé]s)[^.]{0,60}\b(19|20)\d\d\b", body, re.I):
        missing.append("search date")
    if not re.search(r"search (terms?|strings?|strategy|query)|\bMeSH\b|\bBoolean\b|"
                     r"keywords? (used|were|included|combined)|keres[oő]kifejez|"
                     r"kulcsszav[^.]{0,30}(keres|haszn)", body, re.I):
        missing.append("search terms")
    if not re.search(r"inclusion criteria|exclusion criteria|eligib|were included if|"
                     r"bev[aá]laszt[aá]si|kiz[aá]r[aá]si", body, re.I):
        missing.append("selection criteria")
    if not missing:
        return []
    sev = ERROR if len(missing) >= 3 else WARN
    return [F(CAT, sev, "search-not-reported",
              f"A review with no reproducible search: missing {', '.join(missing)}.",
              where="methods",
              fix="Even a narrative review states databases, final search date, "
                  "main terms and how sources were chosen. Readers in several "
                  "cohorts asked for exactly this list; 'narrative' excuses the "
                  "pooling, not the search.")]


def _systematic_label(doc):
    """O title, D-R1.3, T-B-M6 — the word
    'systematic' used as an adjective of quality rather than of method."""
    head = title_of(doc) + " " + sec(doc, "abstract")
    if not re.search(r"\bsystematic(ally)?\b|\bszisztematikus", head, re.I):
        return []
    body = body_of(doc)
    machinery = sum(bool(re.search(p, body, re.I)) for p in
                    (r"\bPRISMA\b", _DB, r"inclusion criteria|eligib|bev[aá]laszt",
                     r"\bscreen(ed|ing)\b|sz[uű]r[eé]s", r"flow diagram|folyamat[aá]bra"))
    if machinery >= 3:
        return []
    return [F(CAT, ERROR, "systematic-label-unsupported",
              "The title or abstract says 'systematic', and the text has none "
              "of the machinery the word promises (PRISMA, named databases, "
              "eligibility criteria, screening).",
              where="title",
              fix="Either report the search as a systematic review must, or "
                  "drop the word. A referee reads 'systematic' as a method.")]


def _evidence_table(doc):
    """M-AE.3, M-R2.5, M-R3.6, M-R3.7, D-R1.1, D-R1.4, D-R2.5, T-E-M8 — effect
    sizes and accuracies scattered through prose with no table to hold them.
    Three cohorts, six separate points."""
    if not is_review(doc):
        return []
    body = body_of(doc)
    n = len(re.findall(_METRIC, body))
    if n < 6:
        return []
    if re.search(r"\bTable\s+\d|\b[IVX]{1,4}\.\s*t[aá]bl[aá]zat|\d+\.\s*t[aá]bl[aá]zat",
                 doc.text, re.I):
        return []
    return [F(CAT, WARN, "evidence-table-absent",
              f"{n} effect sizes or accuracy metrics are reported in prose and "
              f"there is no table.",
              where="results",
              fix="One summary table: study, design, cohort size, population, "
                  "instrument or model, validation strategy, estimate with "
                  "interval, certainty. Referees asked for it in three of the "
                  "five cohorts, sometimes twice in one report.")]


def _limitations(doc):
    """M-R2.3, M-R2.8, A-R2.2, D-R1.7, T-B-m6 — no limitations at all, or
    limitations that do not say what they change."""
    if word_count(doc.text) < 1000:
        return []
    if re.search(r"\blimitation|\bcaveat|\bkorl[aá]t|\blimit[aá]ci|"
                 r"\bcannot (show|establish|exclude|distinguish|rule out)\b|"
                 r"\bnem (tudja|k[eé]pes) (kimutatni|igazolni|kiz[aá]rni)", doc.text, re.I):
        return []
    return [F(CAT, ERROR, "limitations-absent",
              "The manuscript never names a limitation.",
              where="discussion",
              fix="A paragraph, near the end of the Discussion, that says what "
                  "the design cannot show and which direction the resulting bias "
                  "runs. Every cohort with a Discussion was asked for a more "
                  "cautious one; the one without limitations was asked for them "
                  "twice.")]


def _causal_language(doc):
    """D-R1.2, D-R1.5, D-R1.25, D-R2.4, D-R1.18, O-R2.6, O-R2.7 — causal verbs
    on an observational evidence base."""
    body = body_of(doc)
    obs = len(re.findall(r"case[- ]control|\bcohort\b|observational|cross[- ]sectional|"
                         r"eset[- ]kontroll|megfigyel[eé]ses", body, re.I))
    if obs < 2:
        return []
    out = []
    epi = (r"\b(diet(ary)?|intake|consumption|exposure|risk|incidence|disease|lesions?|"
           r"onset|diagnosis|prevalence|progression|recurrence)\b")
    for s in sentences(body):
        fixed = re.search(r"\b(is|are) transmitted through\b|\bjointly generate\b|"
                          r"\bpreventive effect\b|\bprotective (food|effect|factor)s?\b", s, re.I)
        generic = re.search(r"\bcauses?\b(?! of)|\bprevents?\b(?! (us|the reader))|"
                            r"\bdrives?\b", s, re.I) and re.search(epi, s, re.I)
        if not (fixed or generic):
            continue
        if re.search(r"\b(may|might|could|hypothes|associated|suggest|propose|"
                     r"potential|would|plausibl|proposed|putative|if\b|whether)", s, re.I):
            continue
        # a cited mechanism or trial result is someone else's claim, carried by
        # its citation; what the referees objected to was the authors' own
        if cited(s):
            continue
        out.append(F(CAT, WARN, "causal-verb-on-observational",
                     f"Causal language in a paper whose evidence is observational: "
                     f"\"{_quote(s)}\"",
                     where="text",
                     fix="'Associated with a lower risk' is what a "
                         "case-control study shows; 'prevents' is not. Figures "
                         "should be drawn to match."))
        if len(out) >= 3:
            break
    return out


def _certainty_adjectives(doc):
    """D-R1.4, D-R1.7, D-R1.10, T-C-m5 — 'robust', 'consistent', 'promising'
    doing the work a certainty rating should do."""
    body = body_of(doc)
    hits = re.findall(r"\b(robust|consistent|strong|compelling|promising|convincing|"
                      r"well[- ]supported|reasonably well supported|solid)\s+"
                      r"(evidence|support|signal|data|body of evidence|findings)\b|"
                      r"\bclinically actionable\b", body, re.I)
    if len(hits) < 2:
        return []
    if re.search(r"\bcertainty\b|\bGRADE\b|level of evidence|evidence (level|hierarchy|"
                 r"grade)|low[- ]quality|high[- ]quality evidence|very low|"
                 r"bizony[ií]t[eé]k(ok)?\s+(szintj|min[oő]s[eé]g)", body, re.I):
        return []
    return [F(CAT, WARN, "certainty-adjective-unscaled",
              f"{len(hits)} certainty adjectives ('robust evidence', 'promising "
              f"signal', 'clinically actionable') and no stated evidence level.",
              where="discussion",
              fix="State the level for each major conclusion (high / moderate / "
                  "low / very low, with the criteria), then the adjectives can "
                  "go. A referee asked for the adjectives to be replaced, not "
                  "softened.")]


def _relative_as_absolute(doc):
    """D-R1.5, D-R1.26 — a relative risk read as a percentage prevented."""
    body = body_of(doc)
    m = re.search(r"\b\d{1,2}%\s+(preventive|protective|lower risk|reduction in risk|"
                  r"risk reduction|reduced risk)\b", body, re.I)
    if not m:
        return []
    if re.search(r"\babsolute\b|per 1,?000|number needed|\bNNT\b", body, re.I):
        return []
    return [F(CAT, INFO, "relative-effect-as-prevention",
              f"A relative effect stated as a prevented share: "
              f"'{m.group(0)}', with no absolute rate anywhere.",
              where="results",
              fix="Give the absolute rates beside the relative one: a risk "
                  "ratio is not a share of cases prevented.")]


def _taxonomy_criteria(doc):
    """D-R1.1, D-R1.12, D-R1.24, D-R2.3, D-R2.6 — a taxonomy applied without
    its assignment rule, five points across two referees."""
    body = body_of(doc)
    levels = {l for l in ("primary prevention", "secondary prevention",
                          "tertiary prevention", "primer prevenci", "szekunder prevenci",
                          "tercier prevenci") if re.search(l, body, re.I)}
    if len(levels) < 2:
        return []
    if re.search(r"criteria for (assign|classif)|we (classify|assign|allocate)|"
                 r"classified as .{0,40}(because|when|if)|operational definition|"
                 r"(is|was|were) (defined|classified) as|according to the "
                 r"(definition|classification|taxonomy)|besorol[aá]s[^.]{0,40}"
                 r"(krit[eé]rium|szerint)", body, re.I):
        return []
    return [F(CAT, WARN, "classification-criteria-unstated",
              f"{len(levels)} prevention levels are used and no sentence states "
              f"how an intervention is assigned to one.",
              where="methods",
              fix="State the criterion (outcome actually measured: incident "
                  "disease, diagnosis, delay, progression, recurrence, symptoms), "
                  "then classify every intervention by it in a table. A treatment "
                  "trial in diagnosed patients is not primary-prevention evidence.")]


def _screening_guards(doc):
    """D-R1.12, D-R1.13 — screening proposed without its metrics or its harms."""
    body = body_of(doc)
    hits = list(re.finditer(r"\bscreening\b|\bsz[uű]r[eé]s", body, re.I))
    # in a review, "screening" is what was done to records, not to patients, and
    # a rule about overdiagnosis has nothing to say about it
    # only the unambiguous markers of the review sense; a loose list catches
    # "study" or "search" beside a clinical screening proposal and silences it
    METHODS = (r"\brecords?\b|title and abstract|\beligibilit|\bPRISMA\b|deduplicat|"
               r"full[- ]text|screening decisions?|screened in two stages|"
               r"\brekord|absztrakt")
    clinical = [m for m in hits
                if not re.search(METHODS, body[max(0, m.start() - 160):m.end() + 160], re.I)]
    n = len(clinical)
    if n < 8:
        return []
    out = []
    if not re.search(r"overdiagnos|false[- ]positive|t[uú]ldiagnosztiz|[aá]lpozit", body, re.I):
        out.append(F(CAT, WARN, "screening-harms-unstated",
                     f"'Screening' appears {n} times and neither overdiagnosis nor "
                     f"false positives are mentioned.",
                     where="discussion",
                     fix="Weigh harms beside benefits: false-positive labelling, "
                         "unnecessary imaging or surgery, treatment without a secure "
                         "diagnosis, anxiety, opportunity cost — especially for "
                         "adolescents and population-level proposals."))
    if len(re.findall(r"sensitivity|specificity|predictive value|\bPPV\b|\bNPV\b|"
                      r"szenzitivit|specificit", body, re.I)) < 2:
        out.append(F(CAT, INFO, "screening-metrics-absent",
                     "A screening strategy is discussed with no sensitivity, "
                     "specificity or predictive value anywhere.",
                     where="results",
                     fix="Name the target population, the intended use, the "
                         "reference standard, and the operating characteristics; "
                         "reserve 'screening' for defined programmes and call the "
                         "rest case-finding or triage."))
    return out


def _harms(doc):
    """D-R1.13, D-R1.31, A-R2.2, O-R2.9 — a recommendation with no harm beside
    it, and 'no adverse events' read as 'safe'."""
    body = body_of(doc)
    out = []
    recs = len(re.findall(r"\bwe recommend\b|\bshould be (offered|adopted|implemented|"
                          r"used|considered|prescribed)\b|\bclinicians should\b|"
                          r"\bjavasoljuk\b|\baj[aá]nlott\b", body, re.I))
    if recs >= 2 and not re.search(r"\bharm|\badverse|side[- ]effect|\brisk of\b|"
                                   r"\bburden\b|mell[eé]khat[aá]s|kock[aá]zat", body, re.I):
        out.append(F(CAT, WARN, "harms-not-weighed",
                     f"{recs} recommendations and no harm, adverse effect or "
                     f"burden named anywhere.",
                     where="discussion",
                     fix="Every recommendation carries a cost; say what it is and "
                         "for whom. A referee who cannot find the harms assumes "
                         "they were not looked for."))
    for s in sentences(body):
        if re.search(r"\bno (serious |significant )?adverse (events?|effects?|reactions?)\b",
                     s, re.I) and re.search(r"\bsafe(ty)?\b", s, re.I) \
                and not re.search(r"underpowered|cannot (establish|exclude|rule out)|"
                                  r"not powered|insufficient to", s, re.I):
            out.append(F(CAT, INFO, "absence-of-harm-as-safety",
                         f"Absence of reported harm read as safety: \"{_quote(s)}\"",
                         where="text",
                         fix="A small trial that reports no adverse events has "
                             "not shown safety; say what it can exclude and at what "
                             "sample size."))
            break
    return out


def _novelty_unhedged(doc):
    """D-R1.17, D-R2.1, and cohort 5 —
    'no previous review', 'the first to', stated without 'to our knowledge'
    and without a search that could support it."""
    body = body_of(doc)
    out = []
    for s in sentences(body):
        if not re.search(r"\bno (previous|prior|existing|published|other) (review|study|"
                         r"framework|work|analysis)\b|\b(the )?first (review|study|framework|"
                         r"paper|analysis) to\b|\bonly (one|a single) [^.]{0,60}(exists|has been|"
                         r"is available)|\bhas (never|not) (previously )?been (reviewed|"
                         r"integrated|addressed|examined|asked)\b|\bunlike (all )?(previous|"
                         r"prior|recent|existing) (reviews|studies)\b|\bdiffers from [^.]{0,40}"
                         r"(reviews|studies|syntheses)\b|\bscarcely been asked\b|\basked about only rarely\b|"
                         r"\b(differentiates?|distinguishes|sets? apart) (the present|this|our) "
                         r"[^.]{0,40}\bfrom\b",
                         s, re.I):
            continue
        if re.search(r"to (the best of )?our knowledge|as far as we (know|are aware)|"
                     r"we are not aware|we (found|identified) no|our search (found|"
                     r"identified)|tudom[aá]sunk szerint", s, re.I):
            continue
        out.append(F(CAT, WARN, "novelty-unhedged",
                     f"An absolute novelty claim: \"{_quote(s)}\"",
                     where="introduction",
                     fix="'To our knowledge', plus the search that would have found "
                         "a competitor — or state that it is the authors' reading "
                         "of a non-systematic search."))
        if len(out) >= 3:
            break
    return out


def _numeric_target(doc):
    """A-Ed.4, A-R1.2, A-R2.1, A-R3.5, A-R3.6, A-R3.17 — a numeric target
    with no source. Six points from four readers of one short paper."""
    body = body_of(doc)
    out = []
    pat = (r"\b(target|goal|threshold|cut-?off|benchmark|aim(ing)? for|ceiling|floor)"
           r"\s*(of|at|is|:)?\s*(≈|~|approximately |about |around )?\d[\d.,]*\s*"
           r"(kg|g|mg|%|mmol|mg/dL|weeks?|days?|months?|years?|cm|kg/m2|per (week|day|month))"
           r"|(≈|~)\s*\d[\d.,]*\s*(kg|%|mg)\s*(per|/)\s*(week|day|month)")
    for para, s in paragraphs_with_sentences(body):
        m = re.search(pat, s, re.I)
        if not m:
            continue
        if cited(s) or re.search(r"\bguideline|\bconsensus\b|derived from|based on|"
                                 r"as in \[|\bcalibrated (against|to|from)\b", s, re.I):
            continue
        hedged = re.search(r"provisional|arbitrar|not (yet )?(empirically|validated|"
                           r"derived)|to be calibrated|hypothes|illustrative|placeholder",
                           s + " " + para, re.I)
        out.append(F(CAT, WARN if hedged else ERROR, "numeric-target-unsourced",
                     f"A numeric target with no source: '{m.group(0).strip()}' — "
                     f"\"{_quote(s)}\"" +
                     (" (hedged as provisional, which did not stop the question)"
                      if hedged else ""),
                     where="text",
                     fix="Say where the number comes from — guideline, trial, "
                         "consensus — or say it is a hypothesis awaiting prospective "
                         "calibration and do not call it a target."))
        if len(out) >= 2:
            break
    return out


def _recommendation_vs_validation(doc):
    """A-Ed.4, A-R3.0, A-R2.5, D-R1.2, D-R2.16, M-AE.2, M-R2.3 — the paper
    admits the idea is unvalidated and recommends it anyway."""
    body = body_of(doc)
    if not re.search(r"not (yet )?(a )?(validated|proven|established)|\bunvalidated\b|"
                     r"hypothesis[- ]generating|requires prospective|remains (to be )?"
                     r"(tested|validated|shown)|\bconceptual (framework|proposal)\b|"
                     r"has not been (tested|validated)", body, re.I):
        return []
    out = []
    for s in sentences(body):
        if re.search(r"\bshould (be|now be|become) (adopted|used|identified|offered|"
                     r"implemented|standard|the standard|routine|incorporated)\b|"
                     r"\bwe recommend\b|\bclinicians should\b|\bshould (guide|replace)\b|"
                     r"\b(must|should) (now )?(be )?(integrated|applied) (in|into|to) "
                     r"(practice|routine|clinical)", s, re.I) \
                and not re.search(r"\bfuture\b|\bonce\b|\bif\b|\buntil\b|\bafter\b|"
                                  r"trial|validat", s, re.I):
            out.append(F(CAT, WARN, "recommendation-outruns-evidence",
                         f"The text calls the approach unvalidated and still "
                         f"recommends it: \"{_quote(s)}\"",
                         where="discussion",
                         fix="Recommend the study, not the practice, and separate "
                             "general advice from what the evidence supports."))
            break
    return out


def _own_study_registration(doc):
    """A-R2.6, A-R3.9, D-R1.33 — the authors' own trial or programme named
    with no registration and no status."""
    body = body_of(doc)
    if not re.search(r"\b(our|the authors'?) (ongoing|prospective|planned|forthcoming|registered) "
                     r"(trial|study|program(me)?|research program(me)?|cohort)\b|\bwe are (now )?testing\b|"
                     r"\bis being tested (prospectively )?in\b|ethics[- ]approved (program(me)?|study|trial)|"
                     r"currently (recruiting|enrolling)|\bsaj[aá]t (foly[oó]|tervezett) (vizsg[aá]lat|program)",
                     body, re.I):
        return []
    if re.search(r"\bNCT\d{8}\b|\bISRCTN\d+|EudraCT|\bCTRI/|\bDRKS\d+|ClinicalTrials\.gov|"
                 r"registered (at|with|in|on)|not yet (publicly )?registered|registration "
                 r"(number|is pending)|EU CT number|\bPROSPERO\b|\bOSF\b", body, re.I):
        return []
    return [F(CAT, WARN, "own-study-registration-unstated",
              "The authors' own trial or programme is invoked, and no registration "
              "identifier or registration status is given.",
              where="discussion",
              fix="Give the registry and identifier, the population, intervention, "
                  "comparator, primary endpoints and follow-up; if it is not yet "
                  "registered, say so in those words.")]


def _stated_reference_count(doc):
    """T-F-M1, T-B-M8, T-C-m6 (and a cohort 4 referee who counted the list)
    — the text states a count that the list does not match."""
    refs = references_of(doc)
    if len(refs) < 8:
        return []
    body = body_of(doc)
    out = []
    for m in re.finditer(r"\b(?:total of|includes?|comprises?|cites?|list(?:s|ing)? of|"
                         r"drawing on|based on|reviewing|[aá]ttekint[oő]|hivatkozik|"
                         r"felhaszn[aá]lt)\s+(\d{2,3})\s+(?:references|sources|citations|"
                         r"cited works|irodalm[iat]|irodalom|hivatkoz[aá]s|forr[aá]s)|"
                         r"\b(\d{2,3})\s+(?:references|sources|citations|irodalm[iat]|"
                         r"hivatkoz[aá]s)\s+(?:were|are|was|is)\s+(?:cited|included|used|"
                         r"listed|reviewed)", body, re.I):
        n = int(m.group(1) or m.group(2))
        if abs(n - len(refs)) > 2:
            out.append(F(CAT, WARN, "stated-reference-count-mismatch",
                         f"The text says '{m.group(0)}' and the list has {len(refs)}.",
                         where="text",
                         fix="Recount after the last edit."))
            break
    return out


def _mixed_citation_styles(doc):
    """T-F-M2 — numbered and author-year citations in one body."""
    body = body_of(doc)
    numbered = len(re.findall(r"\[\d{1,3}", body))
    author_year = len(re.findall(r"\([A-Z][A-Za-z\-]+(?: et al\.?| and [A-Z][A-Za-z\-]+)?,? "
                                 r"(?:19|20)\d\d[a-z]?\)", body))
    if numbered < 5 or author_year < 5:
        return []
    return [F(CAT, WARN, "mixed-citation-styles",
              f"Both numbered ({numbered}) and author-year ({author_year}) "
              f"citations are used in the body.",
              where="text",
              fix="One style, the journal's. Mixed styles read as a merge of "
                  "two drafts, and the referee who notices checks the rest of "
                  "the list harder.")]


def _reference_double_format(doc):
    """O-R1.5 — every entry repeated in a second format, which the referee
    read as a sign about how the literature had been handled."""
    refs = references_of(doc)
    if len(refs) < 5:
        return []
    doubled = [r for r in refs
               if re.search(r"\{[^}]{10,}\}", r)
               or re.search(r"^([A-Z][a-zÀ-ſ]+ [A-Z]{1,3})\b.*\b\1\b", r)]
    if len(doubled) < 3:
        return []
    return [F(CAT, ERROR, "reference-entry-double-format",
              f"{len(doubled)} of {len(refs)} reference entries carry a second "
              f"copy of themselves in another format, e.g. "
              f"\"{_quote(doubled[0], 90)}\"",
              where="references",
              fix="Strip the export residue (the {…} block or the repeated "
                  "author-year tail) from every entry. A referee can take it as "
                  "evidence about citation practice, not as a formatting slip.")]


def _ai_disclosure(doc):
    """O-Ed, D-R2.11 — AI assistance disclosed with no statement of the model,
    the version, or how each reference was verified. A reference that does not
    exist can end a submission on its own."""
    text = doc.text
    m = None
    for cand in re.finditer(r"generative AI|large language model|ChatGPT|\bClaude\b|GPT-?\d|"
                            r"\bGemini\b|\bCopilot\b|mesters[eé]ges intelligenci", text, re.I):
        around = text[max(0, cand.start() - 250):cand.end() + 250]
        if re.search(r"\b(used|assisted|employed|helped|language editing|writing|"
                     r"translation|disclos|declar|statement|acknowledg|haszn[aá]l|"
                     r"seg[ií]ts[eé]g|nyilatkoz|ford[ií]t)", around, re.I):
            m = cand
            break
    if not m:
        return []
    out = []
    if not re.search(r"(references?|citations?|sources?)[^.]{0,80}(verified|checked|"
                     r"validated|confirmed)|verified (each|every|all) [^.]{0,30}"
                     r"(reference|citation)|against (Crossref|PubMed|the original)|"
                     r"hivatkoz[aá]s[^.]{0,60}ellen[oő]r", text, re.I):
        out.append(F(CAT, WARN, "ai-references-verification-unstated",
                     "AI assistance is disclosed and nothing says the references "
                     "were verified against a bibliographic source.",
                     where="disclosures",
                     fix="State that every reference was checked against Crossref "
                         "or PubMed by a named author, and do it: a single "
                         "reference that does not exist can end a submission."))
    window = text[max(0, m.start() - 200):m.end() + 300]
    sent = next((s for s in sentences(window) if re.search(re.escape(m.group(0)), s, re.I)),
                window)
    if not re.search(r"\bversion\b|\bv\d|\b(20\d\d)-\d\d|\bmodel\b|\d\.\d|Sonnet|Opus|"
                     r"Haiku|Fable|GPT-?\d", window, re.I):
        out.append(F(CAT, INFO, "ai-disclosure-vague",
                     f"AI use is disclosed without model or version: "
                     f"\"{_quote(sent.strip(), 90)}\"",
                     where="disclosures",
                     fix="Name the tool, the model, the version or date, what it "
                         "was used for, and who checked its output."))
    return out


def _reference_recency(doc):
    """O-R1.3 (nothing from the current year), T-A-M5e, and cohort 5."""
    refs = references_of(doc)
    if len(refs) < 8:
        return []
    years = []
    for r in refs:
        ys = [int(y) for y in re.findall(r"\b(19[5-9]\d|20[0-4]\d)\b", r)]
        if ys:
            years.append(max(ys))
    if not years:
        return []
    now = _year_now()
    out = []
    newest = max(years)
    if newest < now:
        out.append(F(CAT, WARN if newest < now - 1 else INFO, "references-not-current",
                     f"The newest reference is from {newest}; nothing from {now}"
                     + (f" or {now - 1}" if newest < now - 1 else "") + ".",
                     where="references",
                     fix="Search the last eighteen months before submission. A "
                         "referee who works in the field knows what came out "
                         "this year and reads its absence as unawareness."))
    old = sum(1 for y in years if y <= now - 6)
    if old / len(years) > 0.5:
        out.append(F(CAT, INFO, "references-mostly-old",
                     f"{old} of {len(years)} dated references are six or more "
                     f"years old.",
                     where="references",
                     fix="Keep the foundational ones and replace the rest with "
                         "the current syntheses they have been superseded by."))
    return out


def _conference_abstracts(doc):
    """O-R1.2 — conference abstracts in the reference list."""
    refs = references_of(doc)
    hits = [r for r in refs
            if re.search(r"\b(abstract|poster|congress|proceedings|annual meeting|"
                         r"kongresszus|el[oő]ad[aá]s)\b|\bSuppl(ement)?\.?\s*\d", r, re.I)]
    if not hits:
        return []
    return [F(CAT, INFO, "conference-abstract-cited",
              f"{len(hits)} reference(s) look like conference abstracts or "
              f"supplements: \"{_quote(hits[0], 80)}\"",
              where="references",
              fix="Replace each with the full paper if one exists; if not, ask "
                  "whether the claim needs it.")]


def _domestic_literature(doc):
    """O-R1.1, O-R1.4 — a Hungarian-language submission citing no Hungarian
    authors, journals or guidelines; both referees raised it."""
    if not is_hungarian(doc):
        return []
    refs = references_of(doc)
    if len(refs) < 20:
        return []
    if any(re.search(r"Orv\.?\s*Hetil|Orvosi Hetilap|B[oő]rgy[oó]gy|\bMagyar\b|"
                     r"\bHung(arian|ary)?\b|\bBudapest\b|\bSzemle\b|\bLAM\b|"
                     r"\bMOTESZ\b|szakmai ir[aá]nyelv", r, re.I) for r in refs):
        return []
    return [F(CAT, WARN, "domestic-literature-absent",
              f"A Hungarian-language manuscript with {len(refs)} references and "
              f"none from a Hungarian journal, author group or guideline.",
              where="references",
              fix="Cite the national protocol and the domestic groups who "
                  "published on the topic internationally. A national journal's "
                  "referees are often those groups.")]


def _title_length(doc):
    """O-R2.1, T-A-M3 — a title that carries the whole abstract."""
    t = title_of(doc)
    n = len(t.split())
    if n <= 20:
        return []
    return [F(CAT, WARN if n >= 30 else INFO, "title-long",
              f"The title is {n} words.",
              where="title",
              fix="Under 20 words, one claim.")]


def _table_overload(doc):
    """O-R1, O-R2.1, T-E-M9 — more tables than a reader can take in."""
    caps = set(re.findall(r"^\s*(?:Table\s+(\d{1,2})|([IVX]{1,4})\.\s*t[aá]bl[aá]zat|"
                          r"(\d{1,2})\.\s*t[aá]bl[aá]zat)", doc.text, re.I | re.M))
    n = len(caps)
    if n <= 8:
        return []
    return [F(CAT, INFO, "table-overload",
              f"{n} tables.",
              where="tables",
              fix="Merge or move to supplement.")]


def _long_sentences(doc):
    """A-R1.1, T-A-m3, T-C-m7 — sentences past fifty words."""
    body = body_of(doc)
    sents = [s for s in sentences(body) if not re.match(r"^\[?\d{1,3}[\].]", s)]
    if len(sents) < 20:
        return []
    long_ = [s for s in sents if word_count(s) > 50]
    if len(long_) < 5 and len(long_) / len(sents) < 0.05:
        return []
    worst = max(long_, key=word_count)
    return [F(CAT, INFO, "long-sentences",
              f"{len(long_)} of {len(sents)} sentences exceed 50 words; the "
              f"longest is {word_count(worst)}: \"{_quote(worst, 80)}\"",
              where="text",
              fix="Split them. Three cohorts, in two languages, said so.")]


_ABBR_STOP = {"DNA", "RNA", "USA", "UK", "EU", "CI", "OR", "RR", "HR", "SD", "SE",
              "IQR", "BMI", "PCR", "ALL", "AND", "THE", "FOR", "NOT", "WHO", "NIH",
              "FDA", "EMA", "COVID", "SARS", "HIV", "ICD", "MD", "PHD", "MSC", "MBA",
              "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "XIII",
              "ET", "AL", "VS", "AM", "PM", "US", "NB", "IE", "EG", "MDPI", "DOI",
              "ISBN", "ISSN", "PMID", "PMCID", "URL", "PDF", "HTML", "XML", "JAMA", "BMJ", "NEJM",
              "CC", "BY", "NC", "ND", "SA", "ID", "NR", "NA", "OK", "TM", "CD",
              "UC", "IBD", "IBS", "T2DM", "T1DM", "HU", "EN", "ORCID", "PICO",
              "MESH", "PRISMA", "GRADE", "IMRAD", "RCT", "RCTS", "AI", "ML", "DL",
              "USD", "EUR", "GBP", "HUF", "CHF", "NCBI", "MRSA", "MDRO", "ESBL", "ICU"}


def _abbreviations(doc):
    """M-R3.3, M-AE.4, D-R1.23, O-R1.17, O-R2.13, O-R2.14, T-A-m7 — an
    abbreviation used before or without its expansion; six points, five
    cohorts. The rule looks for the '(ABBR)' definition anywhere, or an
    abbreviation-list line, or the token in the title."""
    body = body_of(doc)
    counts = {}
    for m in re.finditer(r"(?<![-\w])[A-Z][A-Z]{1,6}\b(?![-\d])", body):
        tok = m.group(0)
        if tok in _ABBR_STOP:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    title = title_of(doc)
    listed = abbreviation_list(doc)
    undefined = []
    for tok, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n < 2 or tok in listed:
            continue
        # an extension named in parentheses defines its stem too: a paper that
        # writes "(PROBAST+AI)" has not left PROBAST undefined
        if re.search(rf"\({re.escape(tok)}s?[;,)+\-]", doc.text) \
                or re.search(rf"(?m)^\s*{re.escape(tok)}[\w\s/-]{{0,8}}[=:–—]", doc.text) \
                or re.search(rf"\b{re.escape(tok)}\b", title) \
                or re.search(rf"\b{re.escape(tok)}\s*\((?=[a-z])", doc.text):
            continue
        undefined.append(f"{tok} ({n}×)")
    if not undefined:
        return []
    return [F(CAT, WARN if len(undefined) >= 3 else INFO, "abbreviation-undefined",
              f"Abbreviations with no '(ABBR)' definition and no list entry: "
              f"{', '.join(undefined[:6])}" + (" …" if len(undefined) > 6 else ""),
              where="text",
              fix="Expand at first use in the text and again in each figure "
                  "legend; keep the abbreviation list complete. Most cohorts "
                  "reported at least one.")]


def _cross_references(doc):
    """D-R2.15 ('above' for something that is below), T-D-m2, T-B-m2, T-E-M3 —
    a cross-reference pointing the wrong way or at nothing."""
    text = doc.text
    out = []
    for m in re.finditer(r"\b(Hypothesis|Table|Figure|Fig\.|Section|Box)\s+(\d{1,2})\s+"
                         r"(above|below)\b", text):
        label, n, direction = m.group(1), m.group(2), m.group(3)
        base = "Figure" if label == "Fig." else label
        defs = [d.start() for d in re.finditer(
            rf"(?m)^\s*{base}\s+{n}\b(?![\d.])", text)]
        if not defs:
            continue
        first = min(defs)
        wrong = (direction == "above" and first > m.start()) or \
                (direction == "below" and first < m.start())
        if wrong:
            out.append(F(CAT, INFO, "cross-reference-direction",
                         f"'{m.group(0)}' — {base} {n} is actually "
                         f"{'below' if direction == 'above' else 'above'}.",
                         where="text",
                         fix="Point the reader the right way, or drop the "
                             "direction word."))
            if len(out) >= 2:
                break
    # a numbered table or figure cited but never captioned
    for base, cap in (("Table", r"(?m)^\s*Table\s+(\d{1,2})\b"),
                      ("Figure", r"(?m)^\s*(?:Figure|Fig\.)\s+(\d{1,2})\b")):
        cited_n = {int(x) for x in re.findall(rf"\b{base}s?\s+(\d{{1,2}})\b", text)}
        if base == "Figure":
            cited_n |= {int(x) for x in re.findall(r"\bFigs?\.\s+(\d{1,2})\b", text)}
        capped = {int(x) for x in re.findall(cap, text)}
        if not capped:
            continue
        dangling = sorted(n for n in cited_n if n > max(capped))
        dangling = [n for n in dangling
                    if not re.search(rf"(draft|version|supplement|File S|moved|now )[^.]{{0,60}}"
                                     rf"{base} {n}\b|{base} {n}\b[^.]{{0,60}}(draft|version|"
                                     rf"supplement|File S|moved|now )", text)]
        if dangling:
            out.append(F(CAT, INFO, "figure-table-reference-dangling",
                         f"{base} {', '.join(map(str, dangling))} cited; captions "
                         f"stop at {base} {max(capped)}.",
                         where="text",
                         fix="Renumber after the last deletion."))
    return out


def abstract_of(doc):
    """The Abstract section, or — when no heading was recognised — the first
    long paragraph before the Introduction. MDPI templates carry the abstract
    as an unstyled paragraph, and every abstract rule was silent on them."""
    ab = sec(doc, "abstract")
    if ab:
        return ab
    # walk the sections before the Introduction: a styled title becomes its
    # own section and swallows the abstract paragraph under it
    keys = ["_preamble"] + [k for k in doc.sections.get("_order", [])]
    for k in keys:
        if k in ("introduction", "methods", "results"):
            break
        for para in doc.sections.get(k, "").split("\n"):
            if word_count(para) >= 120:
                return para
    return ""


def _abstract_numbers(doc):
    """M-R3.5, M-AE.4 — the headline number is in the body and not in the
    abstract."""
    ab = abstract_of(doc)
    if not ab or word_count(ab) < 80:
        return []
    body = body_of(doc)
    vals = re.findall(r"(?:AUC|AUROC|c-statistic|C-index)[^\d\n]{0,14}(0\.\d{2,3})", body)
    if vals:
        top = sorted(set(vals), key=float, reverse=True)[:3]
        if not any(v in ab for v in vals):
            return [F(CAT, INFO, "abstract-headline-number-missing",
                      f"The body reports AUC values ({', '.join(top)}) and none of "
                      f"them appears in the abstract.",
                      where="abstract",
                      fix="Put the headline estimate in the abstract. The academic "
                          "editor and a referee separately asked for one AUC to be "
                          "moved there.")]
        return []
    if len(re.findall(_METRIC, body)) < 5 or re.search(r"\d", ab):
        return []
    return [F(CAT, INFO, "abstract-without-numbers",
              "The body reports effect sizes or accuracies; the abstract has no "
              "number at all.",
              where="abstract",
              fix="Put the headline estimate in the abstract.")]


def _vague_quantifier(doc):
    """T-B-m6, D-R1.4 — a quantity word with no number or threshold."""
    body = body_of(doc)
    out = []
    for s in sentences(body):
        if re.search(r"\b(a )?(substantial|significant|considerable|large|major|sizeable)"
                     r"\s+(proportion|share|fraction|number|part|minority|majority)\b|"
                     r"jelent[oő]s h[aá]nyad", s, re.I) and not re.search(r"\d", s):
            out.append(F(CAT, INFO, "vague-quantifier",
                         f"A share with no number: \"{_quote(s)}\"",
                         where="text",
                         fix="Give the proportion, or the threshold above which "
                             "you would call it substantial."))
            if len(out) >= 3:
                break
    return out


def _figure_provenance(doc):
    """O-R1.19, D-R1.18 — a figure with no stated origin, licence or policy
    compliance."""
    text = doc.text
    if not re.search(r"(?m)^\s*(Figure|Fig\.)\s+\d|\d+\.\s*[aá]bra\b", text, re.I):
        return []
    if re.search(r"created (with|in|using)|\bBioRender\b|\bdrawn\b|original (figure|"
                 r"artwork|illustration)|adapted from|reproduced (with|from)|"
                 r"own (work|figure|illustration)|saj[aá]t (szerkeszt|[aá]bra|k[eé]sz[ií]t)|"
                 r"k[eé]sz[uü]lt|licen[cs]e", text, re.I):
        return []
    return [F(CAT, INFO, "figure-provenance-unstated",
              "Figures are present and nothing says who made them, with what, "
              "or under what licence.",
              where="figures",
              fix="One clause per legend: 'Created by the authors in BioRender "
                  "under an academic licence' or 'adapted from [n] with "
                  "permission'. A referee asked for the origin outright; another "
                  "asked for AI-policy compliance to be confirmed.")]


def _single_source_strong_verb(doc):
    """O-R2.12, D-R1.10 — one source, or two small ones, carrying a strong
    verb."""
    body = body_of(doc)
    out = []
    for s in sentences(body):
        if not re.search(r"\b(proves?|demonstrates?|establishes?|confirms?|"
                         r"bizony[ií]tja|igazolja)\b", s, re.I):
            continue
        cites = re.findall(r"\[(\d{1,3})\]", s)
        if len(cites) != 1 or re.search(r"\[\d{1,3}\s*[,–-]", s):
            continue
        if re.search(r"systematic review|meta-analys|synthesis|pooled|umbrella", s, re.I):
            continue
        out.append(F(CAT, INFO, "single-source-strong-verb",
                     f"'Proves' or 'confirms' on one citation: \"{_quote(s)}\"",
                     where="text",
                     fix="One study shows; several confirm. Match the verb to the "
                         "count."))
        if len(out) >= 3:
            break
    return out


def _in_press_references(doc):
    """T-F-m4 — entries that are in press or have no DOI yet."""
    refs = references_of(doc)
    hits = [r for r in refs if re.search(r"\bin press\b|\bforthcoming\b|DOI pending|"
                                         r"\bsubmitted\b|megjelen[eé]s alatt|"
                                         r"\bunpublished\b", r, re.I)]
    if not hits:
        return []
    return [F(CAT, INFO, "references-in-press",
              f"{len(hits)} reference(s) are in press, submitted or unpublished.",
              where="references",
              fix="A referee cannot check them; keep only the ones the argument "
                  "cannot do without, and give a preprint DOI where one exists.")]


def _self_citation(doc):
    """T-C-M3 — a large share of the bibliography by the author or unpublished."""
    refs = references_of(doc)
    if len(refs) < 15:
        return []
    pre = doc.sections.get("_preamble", "")
    names = set()
    for line in pre.splitlines()[1:6]:
        if line.count(",") >= 1 and not re.search(r"@|University|Department|Egyetem", line):
            for m in re.finditer(r"\b([A-Z][a-zÀ-ſ]{2,}(?:-[A-Z][a-zÀ-ſ]+)?)\b", line):
                names.add(m.group(1))
    names -= {"Dr", "Prof", "MD", "PhD", "The", "And"}
    if not names:
        return []
    own = [r for r in refs if any(re.search(rf"\b{re.escape(n)}\b", r[:60]) for n in names)]
    share = len(own) / len(refs)
    if len(own) < 5 or share < 0.25:
        return []
    return [F(CAT, INFO, "self-citation-share",
              f"{len(own)} of {len(refs)} references ({share:.0%}) carry an "
              f"author's surname.",
              where="references",
              fix="Keep the ones the argument needs; a high share reads as a "
                  "closed loop.")]


RULES_COHORTS_2_6 = [
    _placeholders, _search_reporting, _systematic_label, _evidence_table,
    _limitations, _causal_language, _certainty_adjectives, _relative_as_absolute,
    _taxonomy_criteria, _screening_guards, _harms, _novelty_unhedged,
    _numeric_target, _recommendation_vs_validation, _own_study_registration,
    _stated_reference_count, _mixed_citation_styles, _reference_double_format,
    _ai_disclosure, _reference_recency, _conference_abstracts, _domestic_literature,
    _title_length, _table_overload, _long_sentences, _abbreviations,
    _cross_references, _abstract_numbers, _vague_quantifier, _figure_provenance,
    _single_source_strong_verb, _in_press_references, _self_citation,
]



# ═══════════════════════════════════════════════════════ cohort 7 ═══════
# Added from three referee reports on a Hungarian cross-sectional questionnaire
# survey. Codes G-R1.n, G-R2.n, G-R3.n. Every earlier cohort was a review or an
# opinion piece; on this, the first primary survey, the module returned few
# findings and none of them was a point a referee raised.

_SURVEY = r"k[eé]rd[oő][ií]v|questionnaire|\bsurvey\b"
_ONLINE = (r"\bonline\b|k[oö]z[oö]ss[eé]gi (oldal|m[eé]dia|h[aá]l[oó])|social media|"
           r"web-?based|internetes")
_STAT = (r"\bp\s*[=<>≤]\s*0[.,]\d|\bq\s*=\s*0[.,]\d|\ba?OR\s*=\s*\d|\b[HR]R\s*=\s*\d|"
         r"95\s*%[- ]?(?:os)?\s*(?:CI|konfidencia)|\br\s*=\s*0[.,]\d")
_SUPPLEMENT = (r"kieg[eé]sz[ií]t[oő] (anyag|t[aá]bl[aá]zat|[aá]br)|supplementary (material|"
               r"file|table|figure|appendix|information|data)|online supplement|"
               r"\bappendix\b|mell[eé]klet")


def is_survey(doc):
    return len(re.findall(_SURVEY, body_of(doc), re.I)) >= 2


def _sentence_at(text, pos):
    start = max(text.rfind(". ", 0, pos), text.rfind("\n", 0, pos)) + 1
    ends = [e for e in (text.find(". ", pos), text.find("\n", pos)) if e != -1]
    return text[start:(min(ends) + 1 if ends else len(text))].strip()


def abbreviation_list(doc):
    """{abbreviation: its list line} from the run of short definition-shaped
    paragraphs after an Abbreviations heading. 'S / NS – …' gives S and NS,
    'N, n – …' gives N and n; the run ends at the first ordinary paragraph."""
    paras = [t for t, _ in doc.paragraphs]
    out = {}
    for i, t in enumerate(paras):
        key = re.sub(r"^\d+[.\)]?\s*", "", pc_lib._norm(t.rstrip(":. ")))
        if pc_lib.SECTION_ALIASES.get(key) != "abbreviations":
            continue
        for e in paras[i + 1:]:
            if word_count(e) > 25 or not re.search(r"\s[–—=:-]\s|\(|:\s", e):
                break
            head = re.split(r"\s*(?:\(|[–—=]|\s-\s|:)", e, maxsplit=1)[0]
            for k in re.split(r"\s*[/,;]\s*", head):
                k = k.strip()
                if k and " " not in k and len(k) <= 15:
                    out[k] = e
        break
    return out


def _instrument(doc):
    """G-R1.5, G-R1.7, G-R2.1 — a self-built questionnaire, not validated,
    with nothing about how it was built. Two of three referees; one said the
    missing validation put every conclusion at risk, and could not find the
    questionnaire in the supplement the Methods pointed to."""
    if not is_survey(doc):
        return []
    body = body_of(doc)
    methods = sec(doc, "methods") or body
    out = []
    unvalidated = re.search(r"nem (esett [aá]t|volt) [^.]{0,30}valid[aá]l|valid[aá]l[aá]s n[eé]lk[uü]l|"
                            r"nem valid[aá]lt|not (been |formally |yet )?validated|"
                            r"\bunvalidated\b|non-validated", body, re.I)
    content = re.search(r"tartalmi (validit|valid[aá]l|[eé]rv[eé]nyess)|content validity|"
                        r"face validity|szak[eé]rt[oő]i? ?(panel|konszenzus|v[eé]lem[eé]ny|"
                        r"b[ií]r[aá]lat|egyeztet)|expert (panel|review|consensus)|\bDelphi\b|"
                        r"\bpilot|pr[oó]bak[ií]t[oö]lt|el[oő]teszt|pre-?test|cognitive interview|"
                        r"kognit[ií]v interj[uú]", body, re.I)
    if unvalidated and not content:
        out.append(F(CAT, ERROR, "instrument-validation-unexplained",
                     "The questionnaire is said not to be validated, and nothing says "
                     "whether its content was checked at all: "
                     f"\"{_quote(_sentence_at(body, unvalidated.start()))}\"",
                     where="methods",
                     fix="Say why formal validation was not done, then what was: expert "
                         "review of the items (who, how many, how disagreements were "
                         "settled), a pilot fill-in and what it changed."))
    selfmade = re.search(r"saj[aá]t (szerkeszt[eé]s|fejleszt[eé]s|k[eé]sz[ií]t[eé]s)[^.]{0,20}"
                         r"k[eé]rd[oő]|self-(developed|designed|constructed)|"
                         r"(researcher|author)s?-(developed|designed)|"
                         r"developed (by|for) (the authors|this study)", body, re.I)
    built = re.search(r"szakirodalm[^.]{0,60}(alapj|alapul|nyom[aá]n|felhaszn)|"
                      r"(based on|derived from|adapted from|informed by) (the )?(literature|"
                      r"previous|existing|guideline)|k[eé]rd[eé]scsoport|dom[eé]n|\bdomains?\b|"
                      r"t[eé]mak[oö]r|t[eé]telblokk|sections? (on|covering|addressing)|"
                      r"(items|t[eé]telek) (covered|addressed|[eé]rintett)", methods, re.I)
    if selfmade and not built:
        in_supp = re.search(r"k[eé]rd[oő][ií]v[^.]{0,60}(" + _SUPPLEMENT + r")|questionnaire"
                            r"[^.]{0,60}(" + _SUPPLEMENT + r")", body, re.I)
        out.append(F(CAT, WARN, "instrument-development-undescribed",
                     "A self-developed questionnaire, and the Methods say neither what it "
                     "was built from nor which domains and variables it covers"
                     + (" — it is only pointed to in the supplement." if in_supp else "."),
                     where="methods",
                     fix="Describe the source of the items, the question groups and what "
                         "each measures, and attach the full instrument — then check it "
                         "is really in the uploaded supplement."))
    return out


def _recruitment(doc):
    """G-R1.6, G-R2.2 — online recruitment with no platform, no sampling
    method and no exclusion rule; neither referee could tell how respondents
    were reached."""
    if not is_survey(doc):
        return []
    body = body_of(doc)
    if not re.search(_ONLINE, body, re.I):
        return []
    missing = []
    if not re.search(r"\bFacebook|\bInstagram|\bTikTok|\bLinkedIn|\bTwitter|\bReddit|"
                     r"\bWhatsApp|\bViber|\bMessenger|\bYouTube|Google Forms?|MS Forms|"
                     r"\bQualtrics|SurveyMonkey|LimeSurvey|\bREDCap|h[ií]rlev[eé]l|newsletter|"
                     # a bare "E-mail:" is the corresponding author's address, not a channel
                     r"e-?mail(ben|en|t|ek|ekben)\b|e-?mail(ing)? list|mailing list", body, re.I):
        missing.append("platform or channel")
    if not re.search(r"k[eé]nyelmi|h[oó]labda|convenience|snowball|purposive|"
                     r"c[eé]lzott mintav[eé]tel|kv[oó]t|quota|v[eé]letlen(szer[uű])? mintav|"
                     r"random(ly)? (sampl|select)|r[eé]tegzett|stratified", body, re.I):
        missing.append("sampling method")
    if not re.search(r"bev[aá]laszt[aá]si|kiz[aá]r[aá]si|inclusion criteria|exclusion "
                     r"criteria|eligib|were excluded|kiz[aá]rtuk|kiz[aá]r[aá]sra", body, re.I):
        missing.append("eligibility and exclusion criteria")
    if not missing:
        return []
    return [F(CAT, WARN if len(missing) >= 2 else INFO, "recruitment-undescribed",
              f"Online recruitment with no {', no '.join(missing)}.",
              where="methods",
              fix="Name the platforms and groups the link was posted to, how often and "
                  "by whom, the sampling method (usually convenience or snowball — say "
                  "so), and who was excluded. One referee asked for exactly this; the "
                  "other drew the non-representativeness conclusion from its absence.")]


def _response_rate(doc):
    """G-R1.8, G-R2.3 — a response rate in an open online survey, where no one
    knows how many people saw the invitation."""
    if not is_survey(doc):
        return []
    body = body_of(doc)
    m = re.search(r"(v[aá]laszad[aá]si|r[eé]szv[eé]teli|kit[oö]lt[eé]si) ar[aá]ny[^.]{0,30}?"
                  r"(\d{1,3}(?:[.,]\d)?)\s*%|(response|participation|completion) rate"
                  r"[^.]{0,30}?(\d{1,3}(?:[.,]\d)?)\s*%", body, re.I)
    if not m:
        return []
    value = float((m.group(2) or m.group(4)).replace(",", "."))
    online = re.search(_ONLINE, body, re.I)
    invited = re.search(r"\d+\s*(f[oő]|szem[eé]ly|people|individuals|persons)?[^.]{0,30}"
                        r"(megh[ií]v|kik[uü]ld|megkeres|invited|approached|contacted)", body, re.I)
    if online and value >= 99.5:
        sev = ERROR
    elif online and not invited:
        sev = WARN
    else:
        return []
    return [F(CAT, sev, "response-rate-without-denominator",
              f"A response rate of {m.group(2) or m.group(4)}% is reported for open "
              f"online recruitment, where the number invited is unknown.",
              where="methods",
              fix="An open link has no denominator, so drop the response rate or define "
                  "what was counted (started vs completed questionnaires) and report it "
                  "in the Results.")]


def _sample_skew(doc):
    """G-R1.12, G-R2.2 — a sample heavily skewed to one sex, and selection bias
    never named. A general remark on representativeness did not satisfy the
    referee, who asked for the cause and for it to be discussed."""
    if not is_survey(doc):
        return []
    body = body_of(doc)
    share = None
    for m in re.finditer(r"\b(n[oő]k?|n[oő]i|female|women|f[eé]rfi(?:ak)?|males?|men)\b[^.]{0,40}?"
                         r"(?<![\d,.])(\d{2}(?:[.,]\d)?)\s*%|(?<![\d,.])(\d{2}(?:[.,]\d)?)\s*%"
                         r"[^.]{0,25}?\b(n[oő]k?|n[oő]i|female|women|f[eé]rfi(?:ak)?|males?|men)\b",
                         body, re.I):
        v = float((m.group(2) or m.group(3)).replace(",", "."))
        if v >= 80 and (share is None or v > share[0]):
            share = (v, m.group(2) or m.group(3))
    if not share:
        return []
    if re.search(r"szelekci[oó]s torz|kiv[aá]laszt[aá]si torz|mintav[eé]teli torz|"
                 r"[oö]nszelekci|selection bias|sampling bias|self-selection", body, re.I):
        return []
    return [F(CAT, WARN, "sample-skew-bias-unnamed",
              f"{share[1]}% of the sample is one sex, and selection bias is never named.",
              where="discussion",
              fix="Name it as selection bias, give its likely mechanism (who follows the "
                  "groups the link went to, who fills in surveys), say which groups are "
                  "under-represented and which way that moves the estimates, and put it "
                  "in the Discussion, not only in a limitations list.")]


def _fieldwork_window(doc):
    """G-R3.16 — fieldwork across the winter holidays, not acknowledged."""
    body = body_of(doc)
    hu = re.search(r"(20\d\d)\.\s*december\s*(\d{1,2})\.?\s*(?:[–-]|[eé]s)\s*(20\d\d)\.\s*janu[aá]r",
                   body, re.I)
    en = re.search(r"(\d{1,2})\s+December\s+(20\d\d)\s*(?:[–-]|to|and)\s*\d{1,2}\s+January|"
                   r"December\s+(\d{1,2}),?\s+(20\d\d)\s*(?:[–-]|to|and)\s*January", body, re.I)
    m = hu or en
    if not m:
        return []
    day = int(m.group(2) if hu else (m.group(1) or m.group(3)))
    if day > 26:
        return []
    if re.search(r"[uü]nnep|holiday|t[eé]li sz[uü]net|kar[aá]csony|Christmas|New Year|"
                 r"szilveszter", body, re.I):
        return []
    return [F(CAT, INFO, "fieldwork-over-holidays",
              f"Data collection ran across the winter holidays ('{_quote(m.group(0), 60)}') "
              f"and nothing says what that did to recruitment.",
              where="methods",
              fix="Say it in the limitations, with the direction: fewer respondents, and "
                  "possibly a different mix of them. A referee pointed it out unprompted.")]


def _descriptive_stats(doc):
    """G-R1.9 — mean and SD promised in the Methods, medians in the Results,
    and no IQR anywhere."""
    methods = sec(doc, "methods")
    if not methods:
        return []
    body = body_of(doc)
    mean_sd = re.search(r"[aá]tlag[^.]{0,40}(SD|sz[oó]r[aá]s)|mean[^.]{0,20}(SD|standard "
                        r"deviation)|mean\s*±", methods, re.I)
    if not mean_sd:
        return []
    if re.search(r"\bIQR\b|interkvartilis|interquartile|kvartilis", body, re.I):
        return []
    median = re.search(r"\bmedi[aá]n", body, re.I)
    nonpar = re.search(r"Mann[–-]Whitney|Kruskal[–-]Wallis|Wilcoxon|Spearman", body, re.I)
    if not (median or nonpar):
        return []
    return [F(CAT, WARN if median else INFO, "descriptive-statistics-inconsistent",
              "The Methods describe continuous variables by mean and SD, but the "
              + ("Results report medians" if median else "tests are non-parametric")
              + " and no IQR is given anywhere.",
              where="methods",
              fix="Decide from the distribution: normal — mean (SD); skewed or ordinal "
                  "scores — median (IQR), and then the non-parametric tests follow. Say "
                  "the rule once in the Methods and apply it everywhere.")]


def _model_covariates(doc):
    """G-R1.10 — a multivariable model with no stated reason for its predictors."""
    body = body_of(doc)
    m = re.search(r"logisztikus regresszi|logistic regression|t[oö]bbv[aá]ltoz[oó]s (modell|"
                  r"elemz|regresszi)|multivariable|multivariate (model|analysis|regression)|"
                  r"Cox (regression|model)|linear regression|line[aá]ris regresszi", body, re.I)
    if not m:
        return []
    if re.search(r"a priori|\bDAG\b|directed acyclic|szakirodalm[^.]{0,60}(alapj|alapul|"
                 r"v[aá]laszt)|(chosen|selected|included) (a priori|based on|on the basis of|"
                 r"because)|based on (the )?(literature|prior|clinical)|klinikai (relevanci|"
                 r"megfontol)|konfuz|confound|univari[aá](ns|ble)[^.]{0,60}p\s*<|stepwise|"
                 r"l[eé]pcs[oő]zetes|backward|forward selection|events per variable|\bEPV\b|"
                 r"v[aá]ltoz[oó]k? (kiv[aá]laszt|bev[aá]laszt)[^.]{0,40}(alap|szerint|krit)",
                 body, re.I):
        return []
    return [F(CAT, WARN, "model-covariate-selection-unstated",
              "A multivariable model is fitted and nothing says why its predictors were "
              f"chosen: \"{_quote(_sentence_at(body, m.start()))}\"",
              where="methods",
              fix="State the question the model answers, the rule for entering variables "
                  "(a priori from the literature, a causal diagram, or a univariable "
                  "screen with its threshold) and the events per variable.")]


def _answer_key(doc):
    """G-R3.12 — a knowledge score whose wrong answers are declared wrong with
    no guideline beside them. The referee named one, scored wrong, that
    practice in fact uses."""
    if not is_survey(doc):
        return []
    body = body_of(doc)
    if not re.search(r"tud[aá]sindex|tud[aá]spont|pontsz[aá]m|knowledge score|correct "
                     r"(answer|response)|helyes (v[aá]lasz|teend)|helyesnek", body, re.I):
        return []
    hits = [s for s in sentences(sec(doc, "results") or body)
            if re.search(r"\bhib[aá]s\b|helytelen|t[eé]ves\b|t[eé]vhit|ellenjavallt|"
                         r"nem javasolt|\btilos\b|incorrect|\bwrong\b|misconception|"
                         r"contraindicated|not recommended", s, re.I) and not cited(s)]
    if not hits:
        return []
    return [F(CAT, WARN, "answer-key-unsourced",
              f"{len(hits)} Results sentence(s) judge a response wrong with no citation, "
              f"e.g. \"{_quote(hits[0])}\"",
              where="results",
              fix="Give the answer key in the Methods, item by item, with the guideline "
                  "behind each (ERC, ILCOR, the national protocol), and say which options "
                  "are acceptable alternatives rather than errors.")]


def _discussion_statistics(doc):
    """G-R1.13 — the Discussion re-reports test statistics instead of
    explaining them."""
    disc = sec(doc, "discussion")
    if not disc:
        return []
    nd = len(re.findall(_STAT, disc))
    nr = len(re.findall(_STAT, sec(doc, "results")))
    if nd < 8 or (nr and nd < 0.3 * nr):
        return []
    return [F(CAT, WARN, "discussion-restates-statistics",
              f"The Discussion carries {nd} p/q values, odds ratios or intervals "
              f"(the Results {nr}).",
              where="discussion",
              fix="Report each statistic once, in the Results. The Discussion names the "
                  "finding in words and spends its space on why it came out that way and "
                  "what it changes.")]


def _supplement_offloading(doc):
    """G-R3.13 — the argument moved into a supplement that the referee does
    not count as part of the paper; many pointers in one manuscript."""
    body = body_of(doc)
    n = len(re.findall(_SUPPLEMENT, body, re.I))
    tail = sec(doc, "discussion") + "\n" + sec(doc, "conclusions")
    pointers = [s for s in sentences(tail)
                if re.search(_SUPPLEMENT, s, re.I) and word_count(s) <= 18
                and not re.search(r"\d", s)]
    if len(pointers) >= 3:
        return [F(CAT, ERROR, "supplement-carries-discussion",
                  f"{len(pointers)} sentences in the Discussion or Conclusions only point "
                  f"to the supplement ({n} supplement references in all), e.g. "
                  f"\"{_quote(pointers[0])}\"",
                  where="discussion",
                  fix="Whatever the argument needs goes in the paper; the supplement "
                      "holds data, not reasoning.")]
    if n >= 8:
        return [F(CAT, WARN, "supplement-pointer-overload",
                  f"The body points to the supplement {n} times.",
                  where="text",
                  fix="Bring back what the reader needs to follow the paper and leave "
                      "the supplement for tables and the instrument.")]
    return []


def _figure_overload(doc):
    """G-R3.11 — many figures and tables for a small sample, most of them bar
    charts of numbers already in the text."""
    text = doc.text
    figs = set(re.findall(r"(?<![\d.])(\d{1,2})\.\s*[aá]br[aá]", text)) | \
        set(re.findall(r"\b(?:Figure|Fig\.)\s+(\d{1,2})\b", text))
    tabs = set(re.findall(r"(?<![\d.])(\d{1,2})\.\s*t[aá]bl[aá]zat", text)) | \
        set(re.findall(r"\bTable\s+(\d{1,2})\b", text))
    nf, nt = len(figs), len(tabs)
    if nf < 8 and not (nf + nt >= 12 and nt <= 8):
        return []
    ns = [int(x) for x in re.findall(r"\bN\s*=\s*(\d{2,5})\b", text)]
    small = max(ns) if ns and max(ns) <= 500 else None
    return [F(CAT, WARN, "figure-table-overload",
              f"{nf} figures and {nt} tables"
              + (f" for a sample of {small}." if small else "."),
              where="figures",
              fix="Keep the figures that show something the text cannot — a comparison, "
                  "an interaction, a network — and put single-variable distributions in a "
                  "sentence or one table.")]


def _abbreviation_list_quality(doc):
    """G-R1.15, G-R3.2–G-R3.6 — an abbreviation list with an entry the text
    never uses, statistical notation that is not an abbreviation, and an
    acronym the text uses but the list lacks. Both referees who read the list
    found something."""
    listed = abbreviation_list(doc)
    if not listed:
        return []
    lines = set(listed.values())
    # the preamble carries the author block, and an 'AB: ...' contribution line
    # is an initial, not an abbreviation the list forgot
    pre = set(doc.sections.get("_preamble", "").splitlines())
    pre |= set(doc.sections.get("author contributions", "").splitlines())
    body = "\n".join(t for t, _ in doc.paragraphs
                     if t not in lines and t not in pre
                     and not re.match(r"^[A-ZÁÉÍÓÖŐÚÜŰ]{2,6}\s*[:：]", t))
    ref = doc.sections.get("references", "")
    if ref and ref in body:
        body = body.split(ref)[0]
    out = []
    notation = [k for k in listed if len(k) == 1 or re.search(r"[α-ωΑ-Ω]", k)]
    unused = [k for k in listed if k not in notation and not re.search(
        rf"(?<![A-Za-zÀ-ž]){re.escape(k)}(?![A-Za-zÀ-ž])", body)]
    if unused:
        out.append(F(CAT, WARN, "abbreviation-list-unused",
                     f"Listed but never used in the text: {', '.join(unused)}.",
                     where="abbreviations",
                     fix="Delete the entry, or use the term."))
    if notation:
        out.append(F(CAT, INFO, "abbreviation-list-non-abbreviation",
                     f"Notation, not abbreviations, in the list: {', '.join(notation)}.",
                     where="abbreviations",
                     fix="Symbols and statistical notation (n, N, q, φ, Cronbach's α) are "
                         "explained at first use, not listed."))
    skip = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "ET", "AL", "VS",
            "DOI", "URL", "PMID", "PMCID", "ISBN", "ISSN", "ORCID", "HTML", "PDF", "XML"}
    missing = sorted({t for t in re.findall(r"(?<![-\w])[A-Z]{2,8}\b(?![-\d])", body)
                      if t not in listed and t not in skip})
    if missing:
        out.append(F(CAT, WARN if len(missing) >= 3 else INFO, "abbreviation-list-incomplete",
                     f"Used in the text, missing from the list: {', '.join(missing[:8])}"
                     + (" …" if len(missing) > 8 else ""),
                     where="abbreviations",
                     fix="Once a list exists, a referee checks it against the text."))
    return out


def _dangling_clause(doc):
    """G-R1.3, G-R3.8 — a sentence that stops on a participle with its object
    and no complement, so the reader asks: on whom? Two referees picked out
    the sentence, and what made it visible to both was that the same unfinished
    ending closed two paragraphs.

    Hungarian ends sentences on an adverbial participle legitimately, so a bare
    pattern cannot separate style from an unfinished thought: on a large stored
    set it matched often, mostly sound prose. What is checkable is the repetition — the same tail closing
    two sentences — and the one idiom that always wants a target. Narrow on
    purpose: a single dangling participle is not reported, so silence here is
    not evidence."""
    hu_fw = re.compile(r"\b(és|hogy|nem|vagy|mint|amely|ezért|szerint|miatt|"
                       r"között|alapján|a|az)\b", re.I)
    hungarian = is_hungarian(doc)
    found, tails = [], {}
    for s in sentences(body_of(doc)):
        # a caption is a label, not a sentence, and ends on a participle by convention
        if re.match(r"^\s*(\d{1,2}\.\s*([aá]bra|t[aá]bl[aá]zat)|\[)", s, re.I):
            continue
        core = re.sub(r"\s*\[[\d,\s–-]+\]\s*", " ", s).strip().rstrip(".").strip()
        m = re.search(r"\b[\wáéíóöőúüű]+t\s+[\wáéíóöőúüű]{2,}(?:va|ve)$", core, re.I)
        if m and hungarian and len(hu_fw.findall(s)) >= 2:
            tail = m.group(0).lower()
            found.append((s, tail))
            tails[tail] = tails.get(tail, 0) + 1
            continue
        # the English shape of the same complaint is unambiguous on its own
        if re.search(r"\b(placing|imposing|putting|posing) (an? )?(\w+ ){0,2}"
                     r"(burden|strain|load|pressure)$", core, re.I):
            found.append((s, "burden"))
            tails["burden"] = tails.get("burden", 0) + 1
    idiom = re.compile(r"\bterhet (r[oó]va|jelentve|okozva|h[aá]r[ií]tva)$", re.I)
    hits = [s for s, t in found if tails[t] >= 2 or idiom.search(t)]
    if not hits:
        return []
    worst = max(tails, key=lambda t: tails[t])
    return [F(CAT, WARN, "sentence-left-unfinished",
              f"{len(hits)} sentence(s) stop on a participle with nothing to complete "
              f"it, the same ending each time: \"{_quote(hits[0])}\"",
              where="introduction",
              fix="Finish the thought: say on whom or on what. A repeated ending reads "
                  "as text assembled rather than written.")]


def _telegraphic(doc):
    """G-R1.1, G-R3.1 — note-form sentences in the body, a label and a value
    with no verb. One referee read the paper as a condensed longer text; the
    other asked for subjects and predicates."""
    text = "\n".join(sec(doc, k) for k in ("methods", "results", "discussion", "conclusions"))
    hits = []
    for s in sentences(text):
        if re.match(r"^(\d{1,2}\.\s*([aá]bra|t[aá]bl[aá]zat)|(Figure|Table|Fig\.)\s*\d|\[)",
                    s, re.I):
            continue
        label = re.match(r"^[A-ZÁÉÍÓÖŐÚÜŰ][\wáéíóöőúüű/\- ]{2,30}:\s+\S", s)
        # a two-to-four word 'sentence' is note form in a word processor file and
        # line-wrap debris in an extracted PDF ('et al.', 'Fig.', 'group.'): on the
        # 38 open-review PDFs the unguarded branch fired on 19 of them, all noise
        stub = (2 <= word_count(s) <= 4 and s.endswith(".") and not re.search(r"\d", s)
                and doc.source != "pdf"
                and not re.search(r"\b(al|Fig|Suppl?|e\.g|i\.e|vs|etc|No|cf)\.$", s, re.I))
        if label or stub:
            hits.append(s)
    if len(hits) < 4:
        return []
    return [F(CAT, WARN, "telegraphic-sentences",
              f"{len(hits)} note-form sentences in the body, e.g. \"{_quote(hits[0], 60)}\", "
              f"\"{_quote(hits[1], 60)}\"",
              where="text",
              fix="Write them out with a subject and a verb. 'Label: value' belongs in a "
                  "table; in prose it reads as a condensed draft, and both referees who "
                  "commented on the language said so.")]


def _approval_number(doc):
    """G-R3.10 — an ethics or permit number with no year."""
    m = re.search(r"(enged[eé]lysz[aá]m(a)?|enged[eé]ly sz[aá]ma|iktat[oó]sz[aá]m|approval "
                  r"(number|no\.?|code|ID)|reference (number|no\.?)|protocol (number|no\.?)|"
                  r"IRB (number|no\.?))\s*[:.#]?\s*(?P<id>[A-Za-z0-9][\w/.\-]*)", doc.text, re.I)
    if not m:
        return []
    ident = m.group("id").rstrip(".")
    if re.search(r"(19|20)\d\d", ident + doc.text[m.end():m.end() + 30]):
        return []
    return [F(CAT, WARN, "approval-number-without-year",
              f"The approval number has no year: '{_quote(m.group(0), 60)}'.",
              where="ethics",
              fix="Give the full identifier as issued — number, year, and the body that "
                  "issued it.")]


def _bilingual_abstract(doc):
    """G-R1.2 — a Hungarian and an English abstract that do not carry the same
    numbers."""
    ab = sec(doc, "abstract")
    m = re.search(r"(?m)^(Introduction|Background|Objectives?|Aims?|Purpose)\s*:", ab)
    if not m or not re.search(r"(?m)^(Bevezet[eé]s|H[aá]tt[eé]r|C[eé]lkit[uű]z[eé]s)\s*:",
                              ab[:m.start()]):
        return []

    def nums(t):
        return {x.replace(",", ".") for x in re.findall(r"(?<![\w.,])\d+(?:[.,]\d+)?(?!\w)", t)
                if not (x.isdigit() and int(x) < 10)}
    hu, en = nums(ab[:m.start()]), nums(ab[m.start():])
    diff = sorted((hu - en) | (en - hu))
    if not diff:
        return []
    return [F(CAT, WARN, "bilingual-abstract-mismatch",
              f"The Hungarian and English abstracts differ in {len(diff)} number(s): "
              f"{', '.join(diff[:6])}" + (" …" if len(diff) > 6 else ""),
              where="abstract",
              fix="Translate one from the other after the last edit, and make the "
                  "Results and Conclusion sentences say the same thing in the same order.")]


RULES_COHORT_7 = [
    _instrument, _recruitment, _response_rate, _sample_skew, _fieldwork_window,
    _descriptive_stats, _model_covariates, _answer_key, _discussion_statistics,
    _supplement_offloading, _figure_overload, _abbreviation_list_quality,
    _dangling_clause, _telegraphic, _approval_number, _bilingual_abstract,
]

RULES = RULES_COHORT_1 + RULES_COHORTS_2_6 + RULES_COHORT_7
