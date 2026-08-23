# ROBINS-I — risk of bias in non-randomised studies of interventions

<!--
tool: robins-i
name: ROBINS-I (Risk Of Bias In Non-randomised Studies — of Interventions, 2016)
answers: Yes|Probably yes|Probably no|No|No information
verdicts: Low|Moderate|Serious|Critical|No information
unit: RESULT (one outcome, one comparison)
use_for: cohort, case-control, controlled before-after, interrupted time series and other non-randomised studies that evaluate an intervention
scopes: assignment, adherence, all
-->

## The idea that makes this tool work

ROBINS-I judges an observational study **against a hypothetical target randomised trial** —
the pragmatic RCT that could have answered the same question. Every domain asks how far the
study departs from that trial. So before the first signalling question, write the target
trial down in three lines: eligibility, the two interventions being compared, and the
outcome with its timing. An assessment without a stated target trial has nothing to be
"biased" relative to, and the domains become unanswerable in practice even though they look
answerable.

**Verdicts differ from RoB 2 on purpose.** *Low* here means comparable to a well-performed
randomised trial — a bar most observational studies do not clear, and rating one Low should
feel unusual. *Critical* means the study is too problematic to provide useful evidence and
should not be included in a synthesis at all. Reviews that never use *Serious* or *Critical*
have usually mistaken ROBINS-I for a scale.

## Domain 1 — Bias due to confounding

**1.1 (all, reverse) — Is there potential for confounding of the effect of intervention in this study?**
Reverse-polarity. Almost always Yes for an observational study; No only where intervention
allocation was effectively random for reasons outside anyone's control. If No, the domain is
Low and the remaining questions are not asked.

**1.2 (all, router) — Was the analysis based on splitting participants' follow-up time according to intervention received?**
Routes to the time-varying confounding branch (1.7–1.8) rather than the baseline branch
(1.4–1.6).

**1.3 (all, reverse) — If Y/PY to 1.2: were intervention discontinuations or switches likely to be related to factors that are prognostic for the outcome?**
Reverse-polarity.

**1.4 (all) — If N/PN to 1.2: did the authors use an appropriate analysis method that controlled for all the important confounding domains?**
"All the important" means the ones *you* listed before reading the paper. Decide the
confounder list from the topic, not from the paper's own table — otherwise the study defines
the standard it is judged by.

**1.5 (all) — If Y/PY to 1.4: were confounding domains that were controlled for measured validly and reliably by the variables available in this study?**
A self-reported proxy for a strong confounder is measured, not controlled.

**1.6 (all, reverse) — Did the authors control for any post-intervention variables that could have been affected by the intervention?**
Reverse-polarity. Adjusting for a mediator is over-adjustment and biases the total effect —
a common and invisible error, because it looks like more rigorous adjustment.

**1.7 (all) — If Y/PY to 1.2: did the authors use an appropriate analysis method that controlled for all the important confounding domains and for time-varying confounding?**
Marginal structural models, g-estimation. Standard regression on a time-varying exposure with
a time-varying confounder affected by prior exposure does not control it.

**1.8 (all) — If Y/PY to 1.7: were confounding domains that were controlled for measured validly and reliably?**

## Domain 2 — Bias in selection of participants into the study

**2.1 (all, reverse) — Was selection of participants into the study (or into the analysis) based on participant characteristics observed after the start of intervention?**
Reverse-polarity. Immortal time bias and prevalent-user designs live here: selecting people
who survived long enough to receive the intervention builds the result into the cohort.

**2.2 (all, reverse) — If Y/PY to 2.1: were the post-intervention variables that influenced selection likely to be associated with intervention?**
Reverse-polarity.

**2.3 (all, reverse) — If Y/PY to 2.2: were the post-intervention variables that influenced selection likely to be influenced by the outcome or a cause of the outcome?**
Reverse-polarity.

**2.4 (all) — Do start of follow-up and start of intervention coincide for most participants?**
When they do not, the unobserved period between them is where immortal time accumulates.

**2.5 (all) — If N/PN to 2.3 or N/PN to 2.4: were adjustment techniques used that are likely to correct for the presence of selection biases?**

## Domain 3 — Bias in classification of interventions

**3.1 (all) — Were intervention groups clearly defined?**
Including the dose, duration and comparator. "Users versus non-users" is not a definition.

**3.2 (all) — Was the information used to define intervention groups recorded at the start of the intervention?**

**3.3 (all, reverse) — Could classification of intervention status have been affected by knowledge of the outcome or risk of the outcome?**
Reverse-polarity. Recall bias in a case-control design sits here.

## Domain 4 — Bias due to deviations from intended interventions

**4.1 (assignment, reverse) — Were there deviations from the intended intervention beyond what would be expected in usual practice?**
Reverse-polarity.

**4.2 (assignment, reverse) — If Y/PY to 4.1: were these deviations from intended intervention unbalanced between groups and likely to have affected the outcome?**
Reverse-polarity.

**4.3 (assignment) — Was the analysis appropriate to estimate the effect of starting and adhering to the intervention?**

**4.4 (adherence, reverse) — Were important co-interventions balanced across intervention groups?**

**4.5 (adherence) — Was the intervention implemented successfully for most participants?**

**4.6 (adherence) — Did study participants adhere to the assigned intervention regimen?**

## Domain 5 — Bias due to missing data

**5.1 (all) — Were outcome data available for all, or nearly all, participants?**

**5.2 (all) — Were participants excluded due to missing data on intervention status, or on other variables needed for the analysis?**

**5.3 (all) — Are the proportion of participants and reasons for missing data similar across interventions?**

## Domain 6 — Bias in measurement of outcomes

**6.1 (all, reverse) — Could the outcome measure have been influenced by knowledge of the intervention received?**
Reverse-polarity. A registry-recorded death cannot; a clinician-adjudicated diagnosis can.

**6.2 (all, reverse) — Were outcome assessors aware of the intervention received by study participants?**
Reverse-polarity.

**6.3 (all, reverse) — Were the methods of outcome assessment comparable across intervention groups?**
Differential surveillance — more testing in the treated group — produces detection bias that
no adjustment repairs.

## Domain 7 — Bias in selection of the reported result

**7.1 (all, reverse) — Is the reported effect estimate likely to be selected, on the basis of the results, from multiple outcome measurements within the outcome domain?**
Reverse-polarity.

**7.2 (all, reverse) — ... from multiple analyses of the intervention-outcome relationship?**
Reverse-polarity. In observational research this is the largest single degree of freedom:
model specification, covariate sets, categorisation cut-points.

**7.3 (all, reverse) — ... from different subgroups?**
Reverse-polarity.

## Reaching the verdicts

Per domain: **Low** (comparable to a well-performed RCT), **Moderate** (sound for a
non-randomised study but not comparable to a rigorous RCT), **Serious**, **Critical**, or
**No information**. Overall = the **worst** domain, with one exception worth stating
explicitly: several Moderate domains may together justify Serious, and if you make that call,
say you made it.

Two rules people break:

1. **Do not sum, average or score domains.** ROBINS-I has no total; a "ROBINS-I score" is a
   misuse of the instrument.
2. **Confounding is not a domain you can pass by listing covariates.** 1.4 asks whether the
   analysis controlled for *the important* domains — a list decided before reading the paper.

## Provenance

Structure, domains and signalling-question set follow Sterne JAC, Hernán MA, Reeves BC, et al.
*ROBINS-I: a tool for assessing risk of bias in non-randomised studies of interventions.*
BMJ 2016;355:i4919, with the detailed guidance at riskofbias.info. Question texts here are
working paraphrases in the tool's vocabulary, and the exact item count differs between the
2016 tool, its guidance document and the 2024 ROBINS-I V2 restructure — **verify the item
list against the version you are citing** before publishing an assessment, and name the
version in the methods section. `--counts` deliberately carries no expected total for this
tool for that reason.
