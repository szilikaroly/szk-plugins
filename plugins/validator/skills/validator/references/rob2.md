# RoB 2 — risk of bias in randomised trials

<!--
tool: rob2
name: RoB 2 (Cochrane risk-of-bias tool for randomised trials, version 2, 22 August 2019)
answers: Yes|Probably yes|Probably no|No|No information
verdicts: Low|Some concerns|High
published_items: 22
unit: RESULT (one specific outcome, from one specific trial)
use_for: individually randomised parallel-group trials; cluster-randomised and crossover trials add domain 1b / 1c questions from the variant tools
scopes: assignment, adherence, all
applicability: not part of RoB 2 — RoB 2 rates risk of bias only
-->

## What this tool actually rates

**A result, not a study.** The same trial can be at low risk of bias for its primary
outcome and high risk for a secondary one measured by an unblinded assessor. An appraisal
that produces one RoB 2 verdict "for the trial" has used the wrong unit and is not
interpretable — Cochrane's own guidance is explicit about this. Fill the table once per
result you intend to use.

**A specified effect of interest.** The default here is the *effect of assignment to
intervention* (intention-to-treat). The *effect of adhering to intervention* uses a
different domain 2 (per-protocol, adherence-focused), and mixing the two inside one
assessment is the second most common way this tool is misapplied. State which one you are
rating before answering 2.1.

Answer vocabulary: **Yes / Probably yes / Probably no / No / No information**. "Probably"
is not hedging — it marks a judgement made from indirect evidence rather than an explicit
statement, and it is a normal, expected answer.

## Domain 1 — Randomisation process

**1.1 (all) — Was the allocation sequence random?**
Look for the generation method: computer random number generator, random number table,
shuffling, coin toss, drawing lots. Alternation, date of birth, day of admission or record
number are *not* random — answer No. A bare "patients were randomised" with no method is
No information, not Probably yes.

**1.2 (all) — Was the allocation sequence concealed until participants were enrolled and assigned to interventions?**
Central randomisation, sequentially numbered opaque sealed envelopes, or identical
pre-numbered containers support Yes. An open list or envelopes that are not both opaque and
sequentially numbered support No. This is the item most predictive of exaggerated effect
estimates in meta-epidemiological studies; do not treat it as a formality.

**1.3 (all, reverse) — Did baseline differences between intervention groups suggest a problem with the randomisation process?**
Reverse-polarity: **Yes is the problem.** Judge the *pattern*, not any single imbalance —
some imbalance is expected by chance. A striking imbalance in a strong prognostic factor,
or imbalance across many variables in the same direction, suggests a compromised process.
Baseline significance testing is not evidence of a problem and its absence is not
reassurance.

## Domain 2 — Deviations from intended interventions

**2.1 (assignment, router) — Were participants aware of their assigned intervention during the trial?**
This is about awareness, not about the word "blinded". A trial comparing surgery with
physiotherapy cannot blind participants; answer Yes and let the later questions decide
whether it mattered.

**2.2 (assignment, router) — Were carers and people delivering the interventions aware of participants' assigned intervention during the trial?**

**2.3 (assignment, router) — If Y/PY/NI to 2.1 or 2.2: were there deviations from the intended intervention that arose because of the trial context?**
Only deviations *caused by the trial context* count — not the routine non-adherence that
would also happen outside a trial, which is part of the effect of assignment.

**2.4 (assignment, router) — If Y/PY to 2.3: were these deviations likely to have affected the outcome?**

**2.5 (assignment) — If Y/PY to 2.4: were these deviations from intended intervention balanced between groups?**

**2.6 (assignment) — Was an appropriate analysis used to estimate the effect of assignment to intervention?**
Intention-to-treat, or a "modified ITT" that excludes only participants with no outcome
data. Excluding participants for non-adherence, or analysing as-treated, answers No.

**2.7 (assignment, reverse) — If N/PN/NI to 2.6: was there potential for a substantial impact of the failure to analyse participants in the group to which they were randomised?**
Judge the *size* of the excluded group and how differently it plausibly fared. A handful of
exclusions in a large trial with a common outcome usually cannot move the result.

## Domain 3 — Missing outcome data

**3.1 (all) — Were data for this outcome available for all, or nearly all, participants randomised?**
"Nearly all" is not a fixed percentage. Judge against the event rate: 5% missing with a 3%
event rate can reverse a result, while 10% missing with a 50% event rate may not.

**3.2 (all) — If N/PN/NI to 3.1: is there evidence that the result was not biased by missing outcome data?**
A sensitivity analysis under plausible alternative assumptions is evidence. Similar
proportions missing in both arms is *not*, because the reasons can still differ.

**3.3 (all, router) — If N/PN to 3.2: could missingness in the outcome depend on its true value?**
Reverse-polarity. For mortality, missingness usually cannot depend on the true value in the
same way it can for a symptom score a suffering participant stops returning.

**3.4 (all, reverse) — If Y/PY/NI to 3.3: is it likely that missingness in the outcome depended on its true value?**
Reverse-polarity. 3.3 asks whether it is *possible*, 3.4 whether it is *likely*. Reasons for
missingness reported per arm are what let you answer this; without them, No information.

## Domain 4 — Measurement of the outcome

**4.1 (all, reverse) — Was the method of measuring the outcome inappropriate?**
Reverse-polarity: Yes is the problem. This is rarely Yes — it means the measurement does not
capture the outcome at all, not that a better instrument exists.

**4.2 (all, reverse) — Could measurement or ascertainment of the outcome have differed between intervention groups?**
Reverse-polarity. Different follow-up intensity, different diagnostic workup, or a
detection-biased outcome (more tests in the treated arm finds more disease).

**4.3 (all, router) — If N/PN/NI to 4.1 and 4.2: were outcome assessors aware of the intervention received?**
Reverse-polarity. The participant *is* the outcome assessor for a patient-reported outcome.

**4.4 (all, router) — If Y/PY/NI to 4.3: could assessment of the outcome have been influenced by knowledge of intervention received?**
Reverse-polarity. All-cause mortality: almost never. A subjective rating scale: readily.

**4.5 (all, reverse) — If Y/PY/NI to 4.4: is it likely that assessment of the outcome was influenced by knowledge of intervention received?**
Reverse-polarity. Possible (4.4) versus likely (4.5), again.

## Domain 5 — Selection of the reported result

**5.1 (all) — Were the data that produced this result analysed in accordance with a pre-specified analysis plan finalised before unblinded outcome data were available?**
A registry entry or published protocol is what makes Yes answerable. Registration *after*
recruitment started, or a registry entry with no analysis detail, is at best Probably no —
and a trial with no registration at all is No information, which is a real finding worth
stating rather than a gap to smooth over.

**5.2 (all, reverse) — Is the numerical result being assessed likely to have been selected, on the basis of the results, from multiple eligible outcome measurements within the outcome domain?**
Reverse-polarity. Multiple scales, multiple definitions of "response", multiple time points
— and only the favourable one reported.

**5.3 (all, reverse) — Is the numerical result being assessed likely to have been selected, on the basis of the results, from multiple eligible analyses of the data?**
Reverse-polarity. Adjusted versus unadjusted, different subsets, different cut-points for a
continuous variable.

## Question roles — what the tags in this file mean

Each item carries a tag that tells `appraise.py --rollup` how to read its answer:

- **normal** — `No` / `Probably no` is the problem (1.1, 1.2, 2.5, 2.6, 3.1, 3.2, 5.1).
- **reverse** — `Yes` / `Probably yes` is the problem (1.3, 2.7, 3.4, 4.1, 4.2, 4.5, 5.2, 5.3).
- **router** — the answer decides which question is asked next and means nothing on its own
  (2.1, 2.2, 2.3, 2.4, 3.3, 4.3, 4.4). Every open-label trial answers Yes to 2.1; scoring
  that as a problem would rate every unblinded trial high risk, which is not what the tool
  says. Routers are listed in the rollup and excluded from the verdict.

## The algorithm, and why this file does not pretend to run it

RoB 2's published algorithm branches on specific answers — domain 2 turns on 2.6 and 2.7,
domain 3 on the 3.3/3.4 pair, domain 4 on the 4.3–4.5 chain — and produces Low / Some
concerns / High per domain. `appraise.py --rollup` reports what the recorded answers *force*
and names the questions that forced it; it does not reproduce the flowcharts, because a
generic engine that claimed to would give official-looking wrong verdicts. For a borderline
domain, run the answers through the official Excel tool or the algorithm in the RoB 2
guidance and say which one you used.

**Overall:** Low risk of bias only if *every* domain is Low. Some concerns if at least one
domain is Some concerns and none is High. High if any domain is High, **or** if multiple
domains at Some concerns substantially lower confidence in the result — that second clause
is a judgement, and it must be stated when used.

## Provenance

Domain structure, the 22 signalling questions and the answer vocabulary follow Sterne JAC,
Savović J, Page MJ, et al. *RoB 2: a revised tool for assessing risk of bias in randomised
trials.* BMJ 2019;366:l4898, and the RoB 2 guidance document (version 22 August 2019) at
riskofbias.info. The question texts here are working paraphrases in the tool's own
vocabulary, not a verbatim reproduction; check the canonical wording at riskofbias.info
before quoting an item in a manuscript, and use the official Excel template when the
assessment will be published.
