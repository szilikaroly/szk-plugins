# ROBINS-E — risk of bias in studies of exposures

<!--
tool: robins-e
name: ROBINS-E (Risk Of Bias In Non-randomised Studies — of Exposures, 2023)
answers: Yes|Probably yes|Probably no|No|Weak no|Strong no|No information
aliases: Y=Yes; PY=Probably yes; PN=Probably no; N=No; WN=Weak no; SN=Strong no; NI=No information
restricted_answers: Weak no|Strong no
item_answers: 1.1=Yes|Probably yes|Weak no|Strong no|No information
not_applicable: 1.5, 3.3, 4.2, 5.3
low_label: 1=Low, apart from the uncontrolled confounding no observational study can exclude
unknown_answer: No information
verdicts: Low|Some concerns|High|Very high
tiers: Low|Some concerns|High
unit: RESULT (one exposure-outcome pair)
use_for: observational studies of an exposure — environmental, occupational, nutritional, pharmacoepidemiological when the question is about exposure rather than a treatment decision
-->

## Why this is not ROBINS-I with different words

ROBINS-I asks how far a study departs from a **target trial** — a trial that could, in
principle, be run. For most exposures that trial cannot exist: nobody randomises people to
air pollution, to a dietary pattern for twenty years, or to occupational asbestos. ROBINS-E
therefore judges the study against the **ideal observational study** of the same question,
and adds two things ROBINS-I does not have:

- a **preliminary considerations** step, completed *before* any signalling question, that
  fixes the effect of interest, the confounders you will require, and the exposure window;
- a **Very high** verdict, for studies whose result should not be used at all.

Do the preliminary step in writing. Deciding the required confounder list after reading the
paper's adjustment table lets the study set its own standard, and this is the single most
common way an exposure appraisal becomes decorative.

## Domain 1 — Bias due to confounding

**1.1 (all) — Does the analysis adjust for each important confounder that required adjustment?**
Against your pre-specified list, not theirs. This question has a graded No in the 2023 tool
(PMC11098530, section 3): **Weak no** — not all controlled, but the uncontrolled confounding is
probably not substantial (middle tier); **Strong no** — probably substantial (top tier). There
is no plain No or Probably no here, and the graded forms exist on no other question of this
file: `--verify` rejects either the wrong way round.

**1.2 (all) — Were confounding factors that were controlled for measured validly and reliably?**
Nutritional and occupational exposures are frequently adjusted for a proxy — a food frequency
questionnaire, a job-exposure matrix — and residual confounding survives adjustment.

**1.3 (all, reverse) — Did the authors control for any variables that could have been affected by the exposure?**
Reverse-polarity. Over-adjustment for a mediator.

**1.4 (all, router) — Did the study involve time-varying exposure?**
Routing only: Yes opens 1.5 (the time-varying variant of the domain). No information leaves
the domain unclear, because the variant cannot be chosen.

**1.5 (all) — If Y/PY to 1.4: was the analysis method appropriate for time-varying confounding?**

## Domain 2 — Bias arising from measurement of the exposure

**2.1 (all) — Does the measure of exposure reflect the exposure of interest, over the window of interest?**
The window is the point most exposure studies fail: a single blood sample standing in for
decades of accumulated exposure is a different construct, not a noisy version of the same one.

**2.2 (all, reverse) — Could measurement or classification of the exposure have differed between groups defined by the outcome?**
Reverse-polarity. Recall bias — cases remembering exposures more thoroughly than controls.

**2.3 (all) — Were exposure measurement errors likely to be non-differential with respect to the outcome?**
Scored normally: `No` (differential error) is the problem and `Yes` is reassuring, because
non-differential error usually biases toward the null rather than inventing an effect. Say
which direction the error plausibly pushes the estimate; "measurement error"
alone tells a reader nothing about whether the finding is likely to be too big or too small.

## Domain 3 — Bias in selection of participants into the study (or into the analysis)

**3.1 (all, reverse, middle) — Was selection into the study related to both exposure and outcome?**
Reverse-polarity. Selection on a collider is the mechanism, and it can create an association
where none exists. Yes rules out Low; 3.3 decides whether it is worse — a correction the
authors made keeps it in the middle tier, none raises it.

**3.2 (all, middle) — Do start of follow-up and start of exposure coincide for most participants?**
No rules out Low; 3.3 decides as for 3.1.

**3.3 (all) — If Y/PY to 3.1 or N/PN to 3.2: were adjustment techniques used that are likely to correct for selection bias?**
N/A when selection was not a problem — a study that needed no correction is not marked down
for not making one.

## Domain 4 — Bias due to post-exposure interventions

**4.1 (all, reverse, middle) — During follow-up, did people receive interventions that their earlier exposure had prompted?**
Reverse-polarity. Screening or treatment that follows from being known to be exposed. No,
Probably no or No information: 4.2 is N/A (the tool's own example of a conditional question,
PMC11098530 section 3). Yes rules out Low here; 4.2 decides whether it is worse.

**4.2 (all) — If Y/PY to 4.1: did the analysis probably remove the effect of those interventions?**
Censoring at the intervention with inverse-probability-of-censoring weights is the usual
correction, and it needs the reasons for the intervention to be modelled.

## Domain 5 — Bias due to missing data

**5.1 (all, router) — Were outcome data available for all, or nearly all, participants?**
A gateway: No opens 5.3, which decides.

**5.2 (all, reverse, router) — Were participants excluded due to missing exposure or covariate data?**
A gateway, reverse-polarity: Yes opens 5.3.

**5.3 (all) — If N/PN to 5.1 or Y/PY to 5.2: is there evidence that the result was not biased by missing data?**
Multiple imputation under a stated missingness assumption, or a sensitivity analysis. Complete
case analysis is not evidence.

## Domain 6 — Bias arising from measurement of the outcome

**6.1 (all, reverse) — Could the outcome measure have been influenced by knowledge of the exposure?**
Reverse-polarity.

**6.2 (all) — Were the methods of outcome assessment comparable across exposure groups?**
Yes is the good answer. Differential surveillance again: exposed cohorts are often monitored more closely, which finds
more disease.

**6.3 (all) — Were any systematic errors in outcome measurement unrelated to exposure?**

## Domain 7 — Bias in selection of the reported result

**7.1 (all, reverse) — Is the reported result likely to have been selected from multiple exposure measurements?**
Reverse-polarity. Exposure studies carry unusually many defensible ways to define exposure —
continuous, quantiles, cut-points, lags, cumulative versus peak.

**7.2 (all, reverse) — ... from multiple outcome measurements?**

**7.3 (all, reverse) — ... from multiple analyses?**

**7.4 (all, reverse) — ... from different subgroups?**

## Reaching the verdicts

Per domain and overall: **Low** / **Some concerns** / **High** / **Very high**. The overall is
the worst domain. The best judgement domain 1 can reach is Low with a standing caveat — no
observational study can exclude uncontrolled confounding (PMC11098530, section 5) — and the
rollup prints that caveat with a Low domain 1.

**Routing and N/A.** A conditional question (1.5, 3.3, 4.2, 5.3) is scored only where its
condition holds; an answer at one the routing skips is listed and not scored, N/A where the
routing reaches it is a blank, and N/A anywhere else is rejected. 1.4, 5.1 and 5.2 are
gateways (`router`): their answer opens the next question and is not a verdict, but No
information there leaves the domain unclear — unless another answer still opens the question
the gateway feeds and that question is answered (5.1 NI with 5.2 Yes opens 5.3; 5.3 Yes is Low). ROBINS-E's own guidance stresses that *Low* requires the study to be
comparable to a well-conducted study with no important residual confounding — for most
exposure epidemiology, **Some concerns is the realistic ceiling**, and an appraisal that
returns Low for a food-frequency-questionnaire cohort has almost certainly under-read
domain 2.

Close by stating the **direction** the identified biases would push the estimate, and whether
the result could plausibly be explained by them. ROBINS-E asks for this explicitly, and it is
the part reviewers actually use.

## Provenance

Follows Higgins JPT, Morgan RL, Rooney AA, et al. *A tool to assess risk of bias in
non-randomized studies of exposures (ROBINS-E).* Environment International 2024;186:108602
(PMC11098530), and the guidance at riskofbias.info/robins-e. The seven domains and the issues
each one covers follow the paper's Table 1, with domain 3 named for selection into the study
*or into the analysis*; the **signalling questions here are a condensed working set, not the
released tool's question list** (the 2023 release asks more questions, for example several on
missing data, and has variants of domains 1 and 2). That is why `--counts` carries no
expected total for this tool. What the paper fixes is followed: the response options (Yes,
Probably yes, Probably no, No, No information, and the graded weak/strong No of the first
confounding question), conditional questions that become N/A when earlier answers say so
(4.2 after 4.1 No, Probably no or No information), the four judgements, and the overall as
the worst domain. Name the version you used, and use the released form when the assessment
will be published.

Changed in the methodology review of 2.0.0: 1.1 accepts Weak no / Strong no (they were
rejected as unrecognised); N/A is accepted only on the conditional questions (an all-N/A
record rolled up Low); 3.1 and 3.2 are middle and 4.1 middle, so a correction recorded at 3.3
or 4.2 is no longer overridden by a top-tier flag; 5.1 and 5.2 are gateways, so 5.3 Yes
(evidence the result is not biased by missing data) is no longer rated High.

Polarity was corrected in validator 2.0.0: 2.3 (non-differential error) and 6.2 (comparable
outcome assessment) are scored normally — Yes is reassuring — and 5.2 (exclusion for missing
data) is reverse-worded. In 1.x the three were the other way round, so a well-conducted study
was rated high risk in domains 2, 5 and 6.
