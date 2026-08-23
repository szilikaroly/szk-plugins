# QUIPS — quality in prognostic factor studies

<!--
tool: quips
name: QUIPS (Quality In Prognosis Studies)
answers: Yes|Partly|No|Unclear
verdicts: Low|Moderate|High
unit: STUDY, per prognostic factor and outcome
use_for: studies estimating the association between a prognostic factor and a later outcome — not intervention effects, not diagnostic accuracy
-->

## What separates a prognostic factor study from everything else

The question is *does this factor predict this outcome*, not *does treating it help*. So the
biases that matter are different: attrition that is related to the factor, a factor measured
differently in people who will later have the outcome, and — the one that swallows this
literature — analysis and reporting chosen after seeing which factors reached significance.

Six domains, each with prompting items. Rate each domain **Low / Moderate / High**, and give
the reason. There is no total score.

## Domain 1 — Study participation

**1.1 (all) — Is the source population adequately described?**
**1.2 (all) — Are the sampling frame and recruitment adequately described?**
**1.3 (all) — Is the period and place of recruitment adequately described?**
**1.4 (all) — Are inclusion and exclusion criteria adequately described?**
**1.5 (all) — Is there adequate participation by eligible people?**
**1.6 (all) — Are the baseline characteristics of the study sample adequately described?**

The domain judgement is about whether the sample represents the population of interest at a
common, well-defined point in the disease course. A cohort assembled at mixed disease stages
cannot give an interpretable prognosis.

## Domain 2 — Study attrition

**2.1 (all) — Is the proportion of participants completing the study adequately described?**
**2.2 (all) — Are the reasons for loss to follow-up provided?**
**2.3 (all) — Are participants lost to follow-up adequately described?**
**2.4 (all) — Are participants lost to follow-up similar to those who completed, with respect to the prognostic factor?**
**2.5 (all) — Are there no important differences between completers and those lost, in outcome or key characteristics?**

Attrition related to the prognostic factor is the specific danger. Overall attrition rate is
the least informative number here and the one most often reported alone.

## Domain 3 — Prognostic factor measurement

**3.1 (all) — Is the prognostic factor clearly defined?**
**3.2 (all) — Is the method of measurement valid and reliable?**
**3.3 (all) — Is the measurement method the same for all participants?**
**3.4 (all) — Is the proportion of missing data on the factor acceptable?**
**3.5 (all) — Is the method for handling missing factor data appropriate?**
**3.6 (all, reverse) — Was the factor measured after the outcome had begun to occur?**
Reverse-polarity.

**Continuous factors dichotomised at a data-derived cut-point** belong here and are the most
frequent measurement problem in this field: an "optimal" cut-point found in the same dataset
inflates the apparent association and does not replicate.

## Domain 4 — Outcome measurement

**4.1 (all) — Is the outcome clearly defined?**
**4.2 (all) — Is the method of outcome measurement valid and reliable?**
**4.3 (all) — Is the measurement method the same for all participants?**
**4.4 (all, reverse) — Were outcome assessors aware of the prognostic factor status?**
Reverse-polarity.

## Domain 5 — Study confounding

**5.1 (all) — Are all important confounders measured?**
**5.2 (all) — Are the confounders clearly defined?**
**5.3 (all) — Is the method of confounder measurement valid and reliable?**
**5.4 (all) — Is the measurement method the same for all participants?**
**5.5 (all) — Is the proportion of missing confounder data acceptable, and handled appropriately?**
**5.6 (all) — Were appropriate methods used to account for confounding?**

Prognostic *prediction* does not require confounding control; prognostic *explanation* does.
Decide which claim the paper is making before rating this domain — the same analysis is sound
for one and inadequate for the other.

## Domain 6 — Statistical analysis and reporting

**6.1 (all) — Is there sufficient presentation of data to assess the analysis?**
**6.2 (all) — Is the model development strategy appropriate and clearly described?**
**6.3 (all, reverse) — Was the model developed by selecting variables on the basis of statistical significance?**
Reverse-polarity. Stepwise selection on p-values produces optimistic, unstable models.
**6.4 (all) — Is there no selective reporting of results?**
**6.5 (all) — Was the number of events per candidate variable adequate?**

## Reporting it

Six domain ratings with a sentence each, then a short statement of which domains actually
threaten the review's conclusion. Reviews often present all six as equally weighted; in most
prognostic-factor questions, confounding and reporting carry the weight.

## Provenance

Hayden JA, van der Windt DA, Cartwright JL, Côté P, Bombardier C. *Assessing bias in studies
of prognostic factors.* Ann Intern Med 2013;158:280-6.

The **six domains and their rating scheme are the published tool**. The prompting items below
each domain are a working adaptation: some published prompts are compressed and a few (6.3,
6.5) make explicit a concern the paper states in prose. So the item count here is this file's,
not QUIPS's, and `--counts` deliberately carries no expected total — a number asserted here
that nobody can check is worse than no number. Use the published prompt list verbatim when
the assessment will appear in a manuscript, and say in the methods that QUIPS was applied at
domain level, which is how the tool is meant to be reported.
