# ROBINS-I — risk of bias in non-randomised studies of interventions

<!--
tool: robins-i
name: ROBINS-I (Risk Of Bias In Non-randomised Studies — of Interventions, 2016)
answers: Yes|Probably yes|Probably no|No|No information
aliases: Y=Yes; PY=Probably yes; PN=Probably no; N=No; NI=No information
unknown_answer: No information
verdicts: Low|Moderate|Serious|Critical|No information
tiers: Low|Moderate|Serious
published_items: 34
published_by_scope: assignment=30; adherence=32
unit: RESULT (one outcome, one comparison)
use_for: cohort, case-control, controlled before-after, interrupted time series and other non-randomised studies that evaluate an intervention
scopes: assignment, adherence, all
item_answers: 1.1=Yes|Probably yes|Probably no|No
not_applicable: 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.2, 2.3, 2.5, 4.2, 4.6, 5.4, 5.5
numbering: 2016 Table A
legacy_map: 4.3>4.6; 4.4>4.3; 4.5>4.4; 4.6>4.5; 5.3>5.4; 5.2>5.2+5.3
legacy_cue: 4.3=analysis appropriate; 4.4=co-intervention; 4.5=implemented; 4.6=participants adhere; 5.2=, or on; 5.3=proportion of participants
legacy_new_only: 5.5, 6.4
legacy_note: validator 1.x numbered domains 4 and 5 differently from the 2016 tool — 1.x 4.3 is now 4.6, 4.4 is 4.3, 4.5 is 4.4, 4.6 is 4.5 and 5.3 is 5.4; 1.x 5.2 is split into 5.2 (intervention status) and 5.3 (other variables); 5.5 and 6.4 are new
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

**1.1 (all, reverse, middle) — Is there potential for confounding of the effect of intervention in this study?**
Almost always Yes for an observational study; No only where allocation was effectively random
for reasons outside anyone's control. No / Probably no: the domain is Low and 1.2–1.8 are
N/A. Yes / Probably yes rules out Low — the 2016 tool reserves Low for "no confounding
expected" — and the remaining questions decide between Moderate and Serious, so the rollup
puts a Yes here in the middle tier, never higher on its own. There is no "No information"
option for this item.

**1.2 (all, router) — If Y/PY to 1.1: was the analysis based on splitting participants' follow-up time according to intervention received?**
Routing only. No / Probably no: answer the baseline-confounding questions 1.4–1.6. Yes /
Probably yes: go to 1.3.

**1.3 (all, router) — If Y/PY to 1.2: were intervention discontinuations or switches likely to be related to factors that are prognostic for the outcome?**
Routing only. No / Probably no: baseline questions 1.4–1.6. Yes / Probably yes: the
time-varying questions 1.7–1.8. Mark the branch you did not take N/A.

**1.4 (all) — If N/PN to 1.2 or 1.3: did the authors use an appropriate analysis method that controlled for all the important confounding domains?**
"All the important" means the ones *you* listed before reading the paper. Decide the
confounder list from the topic, not from the paper's own table — otherwise the study defines
the standard it is judged by.

**1.5 (all) — If Y/PY to 1.4: were confounding domains that were controlled for measured validly and reliably by the variables available in this study?**
A self-reported proxy for a strong confounder is measured, not controlled.

**1.6 (all, reverse) — If N/PN to 1.2 or 1.3: did the authors control for any post-intervention variables that could have been affected by the intervention?**
Reverse-polarity. Adjusting for a mediator is over-adjustment and biases the total effect —
a common and invisible error, because it looks like more rigorous adjustment.

**1.7 (all) — If Y/PY to 1.3: did the authors use an appropriate analysis method that controlled for all the important confounding domains and for time-varying confounding?**
Marginal structural models, g-estimation. Standard regression on a time-varying exposure with
a time-varying confounder affected by prior exposure does not control it.

**1.8 (all) — If Y/PY to 1.7: were confounding domains that were controlled for measured validly and reliably by the variables available in this study?**

## Domain 2 — Bias in selection of participants into the study

**2.1 (all, reverse, router) — Was selection of participants into the study (or into the analysis) based on participant characteristics observed after the start of intervention?**
A gateway. Immortal time bias and prevalent-user designs start here, but a Yes only opens 2.2
and 2.3: selection on a post-intervention characteristic biases the result only when that
characteristic is related to both the intervention and the outcome. So Yes / Probably yes
does not by itself rule out Low — 2.1 Yes with 2.2 No can be Low. No / Probably no: 2.2 and
2.3 are N/A, go to 2.4. No information leaves the domain unclear.

**2.2 (all, reverse, router) — If Y/PY to 2.1: were the post-intervention variables that influenced selection likely to be associated with intervention?**
Also a gateway: association with the intervention alone does not bias the comparison. No /
Probably no: 2.3 is N/A. Yes / Probably yes: go to 2.3.

**2.3 (all, reverse, middle) — If Y/PY to 2.2: were the post-intervention variables that influenced selection likely to be influenced by the outcome or a cause of the outcome?**
Yes here, after Yes at 2.2, is the mechanism — selection related to both intervention and
outcome — and it rules out Low. Whether it is Moderate or Serious depends on 2.5: Moderate
when the authors used methods likely to correct it, Serious when they did not.

**2.4 (all, middle) — Do start of follow-up and start of intervention coincide for most participants?**
When they do not, the unobserved period between them is where immortal time accumulates. A
No here is Moderate when the affected proportion is small or the analysis corrected it (2.5),
Serious when it did not.

**2.5 (all) — If Y/PY to 2.2 and 2.3, or N/PN to 2.4: were adjustment techniques used that are likely to correct for the presence of selection biases?**

## Domain 3 — Bias in classification of interventions

**3.1 (all) — Were intervention groups clearly defined?**
Including the dose, duration and comparator. "Users versus non-users" is not a definition.

**3.2 (all, middle) — Was the information used to define intervention groups recorded at the start of the intervention?**
Some retrospective classification is Moderate in the 2016 criteria; it becomes Serious only
when it could have been affected by knowledge of the outcome, which is 3.3.

**3.3 (all, reverse) — Could classification of intervention status have been affected by knowledge of the outcome or risk of the outcome?**
Reverse-polarity. Recall bias in a case-control design sits here.

## Domain 4 — Bias due to deviations from intended interventions

Two variants, and they are alternatives: 4.1–4.2 for the **effect of assignment** (scope
`assignment`), 4.3–4.6 for the **effect of starting and adhering** (scope `adherence`). State
which effect you are rating before answering.

**4.1 (assignment, reverse, middle) — Were there deviations from the intended intervention beyond what would be expected in usual practice?**
Deviations beyond usual practice whose impact is expected to be slight are Moderate; Serious
needs them to be unbalanced and likely to have affected the outcome, which is 4.2.

**4.2 (assignment, reverse) — If Y/PY to 4.1: were these deviations from intended intervention unbalanced between groups and likely to have affected the outcome?**
Reverse-polarity.

**4.3 (adherence, middle) — Were important co-interventions balanced across intervention groups?**
The co-interventions are the ones you listed in the protocol, not the ones the authors chose
to report.

**4.4 (adherence, middle) — Was the intervention implemented successfully for most participants?**

**4.5 (adherence, middle) — Did study participants adhere to the assigned intervention regimen?**
A No on 4.3–4.5 is Moderate when the analysis allowed for it (4.6 Yes) and Serious when it
did not.

**4.6 (adherence) — If N/PN to 4.3, 4.4 or 4.5: was an appropriate analysis used to estimate the effect of starting and adhering to the intervention?**
Methods that correct for non-adherence and co-interventions — inverse probability weighting,
g-methods. A naive per-protocol or as-treated comparison is No.

## Domain 5 — Bias due to missing data

**5.1 (all, router) — Were outcome data available for all, or nearly all, participants?**
A gateway. "Nearly all" is judged against the risk of the outcome, not as a fixed percentage.
No / Probably no opens 5.4 and 5.5; on its own it is not a verdict.

**5.2 (all, reverse, router) — Were participants excluded due to missing data on intervention status?**
A gateway, reverse-polarity: Yes opens 5.4 and 5.5.

**5.3 (all, reverse, router) — Were participants excluded due to missing data on other variables needed for the analysis?**
A gateway, reverse-polarity: Yes opens 5.4 and 5.5. Complete-case analysis on confounders
lives here.

**5.4 (all, joint, middle) — If PN/N to 5.1, or Y/PY to 5.2 or 5.3: are the proportion of participants and reasons for missing data similar across interventions?**

**5.5 (all, joint, middle) — If PN/N to 5.1, or Y/PY to 5.2 or 5.3: is there evidence that results were robust to the presence of missing data?**
Multiple imputation under a stated assumption, or a sensitivity analysis. In the 2016
criteria (Table C) missing data are Low when the missingness is similar across groups (5.4
Yes) **or** the analysis is likely to have removed the bias (5.5 Yes); only when both are No
is the domain Moderate or worse — Serious when the differences are substantial, which is a
judgement the answers do not record. The rollup scores 5.4 and 5.5 as a pair (`joint`): one
Yes clears the domain, both No put it in the middle tier with that judgement left to you.

## Domain 6 — Bias in measurement of outcomes

**6.1 (all, reverse, joint) — Could the outcome measure have been influenced by knowledge of the intervention received?**
Reverse-polarity. A registry-recorded death cannot; a clinician-adjudicated diagnosis can.

**6.2 (all, reverse, joint) — Were outcome assessors aware of the intervention received by study participants?**
Reverse-polarity. The 2016 criteria (Table C) make this Serious only together with an outcome
open to influence (6.1): an objective outcome, or assessors who did not know, is Low. The
rollup scores 6.1 and 6.2 as a pair (`joint`) — both Yes is the top tier, one Yes with the
other No flags nothing, and No information on the partner of a Yes leaves the domain
unclear.

**6.3 (all) — Were the methods of outcome assessment comparable across intervention groups?**
Yes is the good answer. Differential surveillance — more testing in the treated group —
produces detection bias that no adjustment repairs, and is a No here.

**6.4 (all, reverse) — Were any systematic errors in measurement of the outcome related to intervention received?**
Reverse-polarity. Differential misclassification of the outcome.

## Domain 7 — Bias in selection of the reported result

**7.1 (all, reverse) — Is the reported effect estimate likely to be selected, on the basis of the results, from multiple outcome measurements within the outcome domain?**
Reverse-polarity.

**7.2 (all, reverse) — ... from multiple analyses of the intervention-outcome relationship?**
Reverse-polarity. In observational research this is the largest single degree of freedom:
model specification, covariate sets, categorisation cut-points.

**7.3 (all, reverse) — ... from different subgroups?**
Reverse-polarity.

## Question roles — what the tags in this file mean

- **normal** — `No` / `Probably no` is the problem.
- **reverse** — `Yes` / `Probably yes` is the problem.
- **router** — a gateway: the answer only decides which question comes next, and is listed,
  not scored (1.2, 1.3, 2.1, 2.2, 5.1–5.3). *No information* at a gateway leaves the domain
  unclear (middle tier), because the questions that would decide it cannot be reached — unless
  another answer still reaches a question that gateway feeds and it is answered: 5.1 NI with
  5.2 Yes opens 5.4/5.5, and either of them Yes is Low (Table C).
- **middle** — a problem answer here rules out Low but cannot by itself make the domain worse
  than Moderate in the 2016 criteria (Tables B and C of the tool); a later question decides
  Serious (1.1, 2.3, 2.4, 3.2, 4.1, 4.3–4.5).
- **joint** — problem answers that count only together: 5.4 with 5.5 (both No: at least
  Moderate) and 6.1 with 6.2 (both Yes: Serious). One answer on the good side clears the pair.

**Routing is followed.** Every "If … to …" condition above is read from the question text.
A conditional question is scored only where its condition holds on the answers before it; an
answer recorded at a question the routing skips is listed and not scored (2.1 No with a stray
No at 2.5 is not Serious), and N/A where the routing reaches a question is a blank
(INCOMPLETE). N/A is offered only on the conditional questions listed in `not_applicable`.

The tags follow the judgement criteria of the 2016 tool (Tables B and C), read through the
routing of Table A: a question whose Yes only opens further questions is a gateway, not a
marker of bias in itself. Domain 2 in particular: 2.1 and 2.2 are gateways; 2.3 Yes (selection
related to both intervention and outcome) or 2.4 No (follow-up and intervention starting at
different times) rules out Low, and 2.5 decides Moderate (corrected) or Serious (not).

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

Item set, numbering, branching conditions and the 34-item count follow the 2016 tool:
Sterne JAC, Hernán MA, Reeves BC, et al. *ROBINS-I: a tool for assessing risk of bias in
non-randomised studies of interventions.* BMJ 2016;355:i4919 — the signalling questions are in
the web-extra Table A (PMC5062054, supplementary file), the judgement criteria in its Tables B
and C. 30 items apply to the effect of assignment, 32 to the effect of starting and adhering.
Question texts here are working paraphrases in the tool's vocabulary, not the canonical
wording; the polarity, `router`, `middle` and `joint` tags are this file's reading of Tables
B–C through Table A's routing. Validator 2.0.0 first tagged 2.1–2.2 and 5.1–5.3 `middle`
(rating any Yes there at least Moderate) and 6.1/6.2 separately (either Yes Serious); the
methodology review of the same release made them gateways and pairs, because Tables B–C give
Low for 2.1 Yes with 2.2 No, for missing data with 5.4 or 5.5 Yes, and for an open outcome
assessed by assessors who did not know. ROBINS-I V2 (2024) is a different item set — do not cite this file for it,
and name the version in the methods section.

**Numbering changed in validator 2.0.0.** Validator 1.x carried 31 items in its own order:
its 4.3 asked the adherence-analysis question under the assignment effect, its 4.4–4.6 were
the 2016 tool's 4.3–4.5, its 5.2 merged two questions, its 5.3 was the 2016 tool's 5.4, and
5.5 and 6.4 were missing. The same id therefore names a different question in a 1.x file.
`--verify` and `--rollup` recognise a 1.x file and refuse to score it;
`appraise.py --migrate <file> --tool robins-i --scope <scope>` rewrites it to this numbering,
carrying every answer whose question is unchanged and leaving the new and the split questions
blank to be answered.
