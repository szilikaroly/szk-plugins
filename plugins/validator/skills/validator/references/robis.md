# ROBIS — risk of bias in a systematic review

<!--
tool: robis
name: ROBIS (Risk Of Bias In Systematic reviews)
answers: Yes|Probably yes|Probably no|No|No information
aliases: Y=Yes; PY=Probably yes; PN=Probably no; N=No; NI=No information
unknown_answer: No information
verdicts: Low|High|Unclear
tiers: Low|Unclear|High
published_items: 24
unit: REVIEW
not_applicable: none
overall_from: P3
overall_note: ROBIS rates domains 1-4 as concerns that inform phase 3; the overall risk of bias is the phase-3 judgement, not the worst domain (Whiting 2016, PMC4687950, section 3.3).
use_for: assessing risk of bias in a systematic review — the companion question to AMSTAR 2's methodological quality
-->

## ROBIS or AMSTAR 2?

They are not competitors and they are not interchangeable:

- **AMSTAR 2** asks *was this review conducted well* — a methodological-quality judgement
  with a mechanical rating.
- **ROBIS** asks *could the review's conclusions be biased* — a risk-of-bias judgement, in
  the same idiom as RoB 2 and ROBINS-I, ending in Low / High / Unclear.

An overview of reviews usually wants both. If you can only run one: AMSTAR 2 when the audience
is deciding whether to trust the review, ROBIS when the review is being included as evidence
in something you are writing.

ROBIS runs in three phases. Phase 1 (assess relevance) is optional and is skipped when the
review is being appraised on its own terms rather than against a specific target question.

## Domain 1 — Study eligibility criteria

**1.1 (all) — Did the review adhere to pre-defined objectives and eligibility criteria?**
**1.2 (all) — Were the eligibility criteria appropriate for the review question?**
**1.3 (all) — Were eligibility criteria unambiguous?**
**1.4 (all, reverse) — Were any restrictions in eligibility criteria based on study characteristics inappropriate?**
Reverse-polarity. Language restrictions, date restrictions and design restrictions that are
not justified.
**1.5 (all, reverse) — Were any restrictions in eligibility criteria based on sources of information inappropriate?**
Reverse-polarity. Excluding grey literature, conference abstracts or non-indexed journals
without a stated reason.

## Domain 2 — Identification and selection of studies

**2.1 (all) — Did the search include an appropriate range of databases and electronic sources?**
**2.2 (all) — Were methods additional to database searching used to identify relevant reports?**
**2.3 (all) — Were the terms and structure of the search strategy likely to retrieve as many eligible studies as possible?**
**2.4 (all, reverse) — Were restrictions based on date, publication format or language inappropriate?**
Reverse-polarity.
**2.5 (all) — Were efforts made to minimise error in selection of studies?**
Duplicate screening, or a documented check on a sample.

## Domain 3 — Data collection and study appraisal

**3.1 (all) — Were efforts made to minimise error in data collection?**
**3.2 (all) — Were enough study characteristics available for both the review authors and readers to interpret the results?**
**3.3 (all) — Were all relevant study results collected for use in the synthesis?**
**3.4 (all) — Was risk of bias (or methodological quality) formally assessed using appropriate criteria?**
**3.5 (all) — Were efforts made to minimise error in risk-of-bias assessment?**

## Domain 4 — Synthesis and findings

**4.1 (all) — Did the synthesis include all studies that it should?**
**4.2 (all) — Were all pre-defined analyses reported, or departures explained?**
**4.3 (all) — Was the synthesis appropriate given the nature and similarity of the research questions, study designs and outcomes across included studies?**
**4.4 (all) — Was between-study variation minimal, or addressed in the synthesis?**
**4.5 (all) — Were the findings robust — e.g. as demonstrated through funnel plot or sensitivity analyses?**
**4.6 (all) — Were biases in primary studies minimal, or addressed in the synthesis?**
Scored normally: `No` is the problem. The point is that a synthesis of high-risk studies is
itself at risk unless the authors did something about it.

## Phase 3 — Risk of bias in the review

**3A (all) — Did the interpretation of findings address all of the concerns identified in domains 1 to 4?**
**3B (all) — Was the relevance of identified studies to the review's research question appropriately considered?**
**3C (all) — Did the reviewers avoid emphasising results on the basis of their statistical significance?**
Scored normally: `No` — emphasising significant results — is the problem.

Phase 3 produces the overall **Low / High / Unclear** risk of bias for the review. It is a
judgement, made in the light of the four domains, not a tally of them — a domain-4 concern that
the interpretation addressed (3A Yes) can still end in an overall Low. `--rollup` therefore
lists domains 1–4 as concerns and takes the implied overall from phase 3 alone; in 2.0.0 it
applied the RoB 2 rule "one high domain sets the overall" and rated such a review High at
exit 0. A blank anywhere still makes the overall INCOMPLETE.

Answers are **Yes / Probably yes / Probably no / No / No information** on every item; ROBIS
has no not-applicable option, and `--verify` rejects N/A (in 2.0.0 a record with all 24
answers N/A verified complete).

## Provenance

Whiting P, Savović J, Higgins JPT, et al. *ROBIS: a new tool to assess risk of bias in
systematic reviews was developed.* J Clin Epidemiol 2016;69:225-34 (PMC4687950; the tool is
its supplementary file), and the guidance at bristol.ac.uk/population-health-sciences/projects/robis.
Item texts are working paraphrases in the tool's vocabulary; check against the published ROBIS
form before publishing an assessment.

**Three items are deliberately negated relative to the published form.** ROBIS asks whether
the restrictions in 1.4, 1.5 and 2.4 were *appropriate* (Yes = good); this file asks whether
they were *inappropriate* and tags them reverse, so the meaning of a stored answer is the same
in every validator version. Invert those three answers when transcribing to or from the
published form. Every other item, including 4.6 and the phase-3 items 3A–3C (A–C on the
form), is worded as published, so Yes is the good answer. In validator 1.x, 4.6 and 3C were
wrongly tagged reverse and a flawless review was rated high risk.

Phase 3 is its own group in the skeleton and the rollup (`Phase 3`), not part of domain 3:
in 1.x the heading reused domain 3's key and the two were merged.
