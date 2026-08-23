# AMSTAR 2 — methodological quality of systematic reviews

<!--
tool: amstar2
name: AMSTAR 2 (A MeaSurement Tool to Assess systematic Reviews, version 2)
answers: Yes|Partial yes|No
verdicts: High|Moderate|Low|Critically low
published_items: 16
critical: 2,4,7,9,11,13,15
unit: REVIEW
use_for: systematic reviews of healthcare interventions, with or without meta-analysis
-->

## What the rating means, and what it does not

AMSTAR 2 produces **confidence in the results of the review** — not the quality of the
included studies, and not the certainty of the evidence. Those are ROBINS/RoB 2 and GRADE
respectively. Readers conflate all three constantly, so state which question you answered.

**It is not a score.** AMSTAR 2's authors removed the summative score that AMSTAR 1 had,
because reviews were being ranked by an arithmetic total in which a missing conflict-of-
interest statement offset a missing risk-of-bias assessment. An "AMSTAR 2 score of 11/16" is
a misuse of the instrument.

**Seven items are critical** (2, 4, 7, 9, 11, 13, 15). The rating follows from them
mechanically:

| Critical flaws | Non-critical weaknesses | Rating |
|---|---|---|
| 0 | 0 or 1 | **High** |
| 0 | more than 1 | **Moderate** |
| 1 | any | **Low** |
| more than 1 | any | **Critically low** |

`appraise.py --rollup ... --tool amstar2` computes this exactly. Most published systematic
reviews come out Low or Critically low; that is the empirical finding of every study that has
applied the tool at scale, not a sign that you have been harsh.

## The items

**1 — Did the research questions and inclusion criteria include the components of PICO?**
Population, Intervention, Comparator, Outcome. A timeframe and setting element counts toward
this but is not required.

**2 (critical) — Did the report contain an explicit statement that the review methods were established prior to the conduct of the review, and did it justify any significant deviations from the protocol?**
*Partial yes*: the authors state they had a written protocol or registration. *Yes*: additionally,
the protocol was registered and specified a meta-analysis plan, a risk-of-bias assessment plan,
and a justification for any deviation. A PROSPERO number with no deviations discussed is
usually Partial yes.

**3 — Did the review authors explain their selection of the study designs for inclusion?**

**4 (critical) — Did the review authors use a comprehensive literature search strategy?**
*Partial yes*: at least two databases, keywords and/or MeSH given, restrictions justified.
*Yes*: additionally, reference lists or registries searched, grey literature considered,
trial registries searched, experts consulted where appropriate, and the search run within 24
months of completion. This is the item where the composer plugin's search log pays for
itself — the PRISMA-S appendix answers it directly.

**5 — Did the review authors perform study selection in duplicate?**

**6 — Did the review authors perform data extraction in duplicate?**

**7 (critical) — Did the review authors provide a list of excluded studies and justify the exclusions?**
*Partial yes*: a list of potentially relevant studies excluded at full text. *Yes*:
additionally, the reason for each exclusion. This item fails more often than any other, and
it fails silently — a review without it cannot be checked for selective exclusion.

**8 — Did the review authors describe the included studies in adequate detail?**

**9 (critical) — Did the review authors use a satisfactory technique for assessing risk of bias in the individual studies?**
For RCTs: allocation concealment and blinding at minimum. For non-randomised studies:
confounding and selection at minimum. A review that reports "quality was assessed using the
Jadad scale" is No — a scale is not a risk-of-bias assessment.

**10 — Did the review authors report on the sources of funding for the studies included?**

**11 (critical) — If meta-analysis was performed, did the review authors use appropriate methods for statistical combination of results?**
Justified the model, investigated heterogeneity, combined only combinable studies. Answer
N/A — and say so — if no meta-analysis was done; N/A does not count as a flaw.

**12 — If meta-analysis was performed, did the review authors assess the potential impact of risk of bias in individual studies on the results?**

**13 (critical) — Did the review authors account for risk of bias in individual studies when interpreting or discussing the results?**
Assessing risk of bias (item 9) and then discussing the pooled estimate as though every study
were sound is the specific failure this item catches, and it is extremely common.

**14 — Did the review authors provide a satisfactory explanation for, and discussion of, any heterogeneity observed?**
Reporting I² and moving on is not a discussion of heterogeneity.

**15 (critical) — If quantitative synthesis was performed, did the review authors carry out an adequate investigation of publication bias, and discuss its likely impact?**
Funnel plot plus a test where the number of studies supports one (conventionally ≥10). With
fewer studies, saying that publication bias could not be assessed is the correct answer and
scores better than an uninterpretable funnel plot.

**16 — Did the review authors report any potential sources of conflict of interest, including funding received for conducting the review?**

## One judgement call the tool leaves open

A **Partial yes on a critical item** — most often item 2 or item 4 — is treated here as a
*non-critical weakness*, not a critical flaw, which is how the AMSTAR 2 guidance describes
partial adherence. Some published applications count it as a critical flaw and arrive at a
lower rating. The choice changes the verdict, so **state which convention you used**; the
rollup names every Partial yes it counted this way.

## Provenance

Shea BJ, Reeves BC, Wells G, et al. *AMSTAR 2: a critical appraisal tool for systematic
reviews that include randomised or non-randomised studies of healthcare interventions, or
both.* BMJ 2017;358:j4008, and the AMSTAR 2 guidance at amstar.ca. Item texts are working
paraphrases; the Yes / Partial yes thresholds above follow the published guidance and should
be checked against amstar.ca when an assessment is published.
