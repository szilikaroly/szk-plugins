# QUIPS — quality in prognostic factor studies

<!--
tool: quips
name: QUIPS (Quality In Prognosis Studies)
answers: Yes|Partly|No|Unclear
aliases: Y=Yes; N=No; U=Unclear; Partial=Partly; Unsure=Unclear
unknown_answer: Unclear
verdicts: Low|Moderate|High
tiers: Low|Moderate|High
published_items: 31
unit: STUDY, per prognostic factor and outcome
use_for: studies estimating the association between a prognostic factor and a later outcome — not intervention effects, not diagnostic accuracy
numbering: Hayden 2013 prompting items 1a-6d
legacy_ids: ^[1-6]\.[0-9]+$
legacy_map: 1.1>1b; 1.2>1d; 1.3>1e; 1.4>1f; 1.5>1a; 1.6>1c; 2.2>2c; 2.3>2d; 2.5>2e; 3.1>3a; 3.2>3b; 3.3>3d; 3.4>3e; 3.5>3f; 4.1>4a; 4.2>4b; 4.3>4c; 5.1>5a; 5.2>5b; 5.3>5c; 5.4>5d; 6.1>6a; 6.2>6b; 6.4>6d
legacy_retired: 2.1, 2.4, 3.6, 4.4, 5.5, 5.6, 6.3, 6.5
legacy_note: validator 1.x used its own 32 prompts numbered 1.1-6.5; 2.0.0 uses the 31 published prompting items 1a-6d — 24 1.x answers carry over to the matching published item, 8 1.x prompts have no published counterpart, and 2a, 2b, 3c, 5e, 5f, 5g and 6c are new
-->

## What separates a prognostic factor study from everything else

The question is *does this factor predict this outcome*, not *does treating it help*. So the
biases that matter are different: attrition that is related to the factor, a factor measured
differently in people who will later have the outcome, and — the one that swallows this
literature — analysis and reporting chosen after seeing which factors reached significance.

Six domains, each with prompting items. Rate each domain **Low / Moderate / High**, and give
the reason. There is no total score.

Answer each prompting item **Yes / Partly / No / Unclear** (the published four-level scale).
Every item is worded so that **Yes is the good answer**. *Partly* is the middle level: the
rollup puts a domain with any *Partly* in the middle tier (Moderate), never in Low.

## Domain 1 — Study participation

**1a (all) — Is participation in the study by eligible persons adequate?**
**1b (all) — Is the source population or population of interest described?**
**1c (all) — Is the baseline study sample described?**
**1d (all) — Are the sampling frame and recruitment adequately described?**
**1e (all) — Are the period and place of recruitment adequately described?**
**1f (all) — Are the inclusion and exclusion criteria adequately described?**

The domain judgement is about whether the sample represents the population of interest at a
common, well-defined point in the disease course. A cohort assembled at mixed disease stages
cannot give an interpretable prognosis.

## Domain 2 — Study attrition

**2a (all) — Is the response rate (the share of participants followed up) adequate?**
**2b (all) — Are attempts to collect information on participants who dropped out described?**
**2c (all) — Are the reasons for loss to follow-up provided?**
**2d (all) — Are the participants lost to follow-up adequately described?**
**2e (all) — Are there no important differences between participants who completed the study and those who did not?**

Attrition related to the prognostic factor is the specific danger, and it is what 2e asks
about. Overall attrition rate is the least informative number here and the one most often
reported alone.

## Domain 3 — Prognostic factor measurement

**3a (all) — Is a clear definition or description of the prognostic factor provided?**
**3b (all) — Is the method of prognostic factor measurement adequately valid and reliable?**
**3c (all) — Are continuous variables reported as such, or are appropriate (not data-derived) cut-points used?**
**3d (all) — Are the method and setting of prognostic factor measurement the same for all participants?**
**3e (all) — Does an adequate proportion of the sample have complete data on the prognostic factor?**
**3f (all) — Are appropriate methods of imputation used for missing prognostic factor data?**

**Continuous factors dichotomised at a data-derived cut-point** (3c) are the most frequent
measurement problem in this field: an "optimal" cut-point found in the same dataset inflates
the apparent association and does not replicate. A factor measured after the outcome had
begun to occur fails 3d and belongs in this domain's judgement.

## Domain 4 — Outcome measurement

**4a (all) — Is a clear definition of the outcome provided?**
**4b (all) — Is the method of outcome measurement adequately valid and reliable?**
**4c (all) — Are the method and setting of outcome measurement the same for all participants?**

Outcome assessors who knew the prognostic factor status are a reliability problem (4b) when
the outcome needs judgement; say so in the domain rationale.

## Domain 5 — Study confounding

**5a (all) — Are all important confounders measured?**
**5b (all) — Are clear definitions of the important confounders provided?**
**5c (all) — Is the measurement of all important confounders adequately valid and reliable?**
**5d (all) — Are the method and setting of confounder measurement the same for all participants?**
**5e (all) — If missing confounder data were imputed, were appropriate methods used?**
**5f (all) — Are important potential confounders accounted for in the study design?**
**5g (all) — Are important potential confounders accounted for in the analysis?**

Prognostic *prediction* does not require confounding control; prognostic *explanation* does.
Decide which claim the paper is making before rating this domain — the same analysis is sound
for one and inadequate for the other. 5e is N/A when nothing was imputed.

## Domain 6 — Statistical analysis and reporting

**6a (all) — Is enough data presented to assess the adequacy of the analytic strategy?**
**6b (all) — Is the model-building strategy appropriate and based on a conceptual framework or model?**
**6c (all) — Is the selected statistical model adequate for the design of the study?**
**6d (all) — Is there no selective reporting of results?**

Stepwise selection on p-values (a 6b problem) produces optimistic, unstable models, and too
few events per candidate variable makes any model inadequate for the design (6c).

## Reporting it

Six domain ratings with a sentence each, then a short statement of which domains actually
threaten the review's conclusion. Reviews often present all six as equally weighted; in most
prognostic-factor questions, confounding and reporting carry the weight.

## Provenance

Hayden JA, van der Windt DA, Cartwright JL, Côté P, Bombardier C. *Assessing bias in studies
of prognostic factors.* Ann Intern Med 2013;158:280-6. The six domains, the rating scheme, the
31 prompting items (1a–6d) and the four-level answer scale follow the published tool, checked
against its reproduction in Grooten WJA et al., Diagn Progn Res 2019;3:5 (PMC6460536),
Table 3. Item texts here are paraphrased as questions; use the published wording when the
assessment appears in a manuscript, and say in the methods that QUIPS was applied at domain
level, which is how the tool is meant to be reported.

**Numbering changed in validator 2.0.0.** Validator 1.x used its own adaptation — 32 prompts
numbered 1.1–6.5, three of them reverse-worded and several with no counterpart in the
published tool. `--verify` and `--rollup` recognise a 1.x file by its ids and refuse to score
it; `appraise.py --migrate <file> --tool quips` rewrites it to 1a–6d, carrying the 24 answers
whose question has a published counterpart (1.1→1b, 1.2→1d, 1.3→1e, 1.4→1f, 1.5→1a, 1.6→1c,
2.2→2c, 2.3→2d, 2.5→2e, 3.1→3a, 3.2→3b, 3.3→3d, 3.4→3e, 3.5→3f, 4.1→4a, 4.2→4b, 4.3→4c,
5.1→5a, 5.2→5b, 5.3→5c, 5.4→5d, 6.1→6a, 6.2→6b, 6.4→6d), listing the eight it cannot carry
(2.1, 2.4, 3.6, 4.4, 5.5, 5.6, 6.3, 6.5), and leaving 2a, 2b, 3c, 5e, 5f, 5g and 6c blank.
