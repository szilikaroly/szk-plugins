# GRADE — certainty of the evidence

<!--
tool: grade
name: GRADE — certainty (quality) of a body of evidence, rated per outcome
answers: Not serious|Serious|Very serious|Yes|No|Undetected|Suspected|Strongly suspected|High|Low
verdicts: High|Moderate|Low|Very low
group_label: GRADE domain
unit: OUTCOME — one rating per outcome, never per study and never per review
use_for: rating how much confidence to place in an effect estimate across the whole body of evidence for one outcome
-->

## The one structural rule

**Certainty is rated per outcome.** Not per study, not per review, not "for the evidence".
A review of the same intervention can be High for mortality and Very low for quality of life,
and reporting one certainty rating for the review is the error that makes a Summary of
Findings table uninterpretable. If more than one outcome matters, this table is repeated for
each.

Certainty answers: *how confident are we that the true effect lies close to this estimate*.
It is not risk of bias (that is one of its five inputs), and it is not the quality of the
review (that is AMSTAR 2).

## Starting level

**0.1 (all) — Study design: randomised trials start High; observational studies start Low.**
Record `High` for a body of RCTs or `Low` for observational evidence. Non-randomised studies
appraised with ROBINS-I may start High in the ROBINS-I-based approach — if you do that, say so,
because it changes every subsequent step.

## Domain 1 — Risk of bias

**1.1 (all) — Risk of bias across the contributing studies: not serious / serious / very serious.**
This is the *body*, weighted by contribution. One high-risk study contributing 3% of the weight
does not downgrade a pooled estimate; the same study carrying 60% does. Use the per-study RoB 2
/ ROBINS-I / ROBINS-E ratings as the input, and state which studies drove the decision.

## Domain 2 — Inconsistency

**2.1 (all) — Unexplained heterogeneity across studies: not serious / serious / very serious.**
Judge the overlap of confidence intervals, the point estimates, and I² together — and only
downgrade for heterogeneity that is *unexplained*. Heterogeneity fully accounted for by a
pre-specified subgroup is a finding, not a limitation. A single study cannot be inconsistent;
rate it not serious and say why.

## Domain 3 — Indirectness

**3.1 (all) — Indirectness of population, intervention, comparator or outcome: not serious / serious / very serious.**
Surrogate outcomes live here, and so does the indirect comparison. This is the domain most
often skipped, and the one most likely to matter in a review whose PICO drifted from the
question the clinician actually asked.

## Domain 4 — Imprecision

**4.1 (all) — Imprecision of the pooled estimate: not serious / serious / very serious.**
Does the confidence interval cross a decision threshold? Is the optimal information size met?
A wide interval that stays entirely on one side of the threshold may not warrant a downgrade;
a narrow one that straddles it may.

## Domain 5 — Publication bias

**5.1 (all) — Publication bias: undetected / suspected / strongly suspected.**
Small positive studies only, industry funding across the board, an asymmetric funnel plot with
enough studies to interpret one. With fewer than about ten studies, "could not be assessed" is
the honest answer, and it is not the same as "undetected" — say which one you mean.

## Domain 6 — Large effect

**6.1 (all) — Large magnitude of effect (RR > 2 or < 0.5, consistent, no plausible confounders)?**

## Domain 7 — Dose-response

**7.1 (all) — Dose-response gradient present?**

## Domain 8 — Opposing plausible residual confounding

**8.1 (all) — Would all plausible residual confounding have reduced the observed effect, or created a spurious null?**

## How the arithmetic works

Start High (RCTs) or Low (observational). Subtract one level per *serious* domain, two per
*very serious*. Upgrade factors apply **only to a body of evidence that has not been
downgraded** — in practice, only to observational evidence with no serious limitations. Floor
at Very low. `appraise.py --rollup ... --tool grade` computes this and refuses to apply an
upgrade alongside a downgrade.

| Certainty | What it licenses saying |
|---|---|
| **High** | "X reduces Y" — further research very unlikely to change the estimate |
| **Moderate** | "X probably reduces Y" |
| **Low** | "X may reduce Y" |
| **Very low** | "the evidence is very uncertain about the effect of X on Y" |

Use that phrasing. GRADE's informative statements exist so that a reader can tell a High
finding from a Very low one without reading the table, and substituting your own wording
throws that away.

## Provenance

The GRADE Handbook (Schünemann H, Brożek J, Guyatt G, Oxman A, eds., updated October 2013) and
the GRADE series in J Clin Epidemiol 2011;64. Domain names and the rating arithmetic follow
those sources; the guidance text here is a working summary. For a published Summary of
Findings table, use GRADEpro GDT — and note that the ROBINS-I-based approach to starting level
for non-randomised evidence is a documented variant, not the default.
