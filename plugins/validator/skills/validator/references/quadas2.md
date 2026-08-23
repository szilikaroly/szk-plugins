# QUADAS-2 — quality of diagnostic accuracy studies

<!--
tool: quadas2
name: QUADAS-2 (Quality Assessment of Diagnostic Accuracy Studies, version 2)
answers: Yes|No|Unclear
verdicts: Low|High|Unclear
published_items: 11
unit: STUDY, but per index test — a study comparing two index tests is assessed once per test
use_for: diagnostic test accuracy studies contributing sensitivity and specificity
applicability: domains 1-3
-->

## Two judgements per domain, and they are not the same judgement

Every domain gets a **risk of bias** rating; the first three also get an **applicability**
rating. They answer different questions:

- *Risk of bias*: could this study's conduct have produced a wrong estimate of accuracy?
- *Applicability*: does this study's population, test or reference standard match **your**
  review question?

A flawlessly conducted study of a hospital population is at low risk of bias and high concern
for applicability if your question is about primary care. Collapsing the two loses exactly the
information a reader needs. **Tailor the signalling questions to the review question first** —
QUADAS-2 is explicitly designed to be tailored, and an untailored application is a misuse.

## Domain 1 — Patient selection

**1.1 (all) — Was a consecutive or random sample of patients enrolled?**

**1.2 (all, reverse) — Was a case-control design avoided?**
Reverse-polarity is *not* needed here — the item is worded so that Yes is good — but note the
trap: two-gate ("diagnostic case-control") designs, comparing clear cases with healthy
controls, inflate accuracy substantially. This is the most consequential single item in the
tool.

**1.3 (all, reverse) — Did the study avoid inappropriate exclusions?**
Excluding difficult-to-diagnose patients, prior test failures, or those with comorbidity
raises apparent accuracy.

## Domain 2 — Index test

**2.1 (all) — Were the index test results interpreted without knowledge of the results of the reference standard?**

**2.2 (all) — If a threshold was used, was it pre-specified?**
A threshold chosen from the study's own ROC curve is optimised on the data it is evaluated on,
and the reported sensitivity/specificity pair is optimistic. This is very common and rarely
acknowledged.

## Domain 3 — Reference standard

**3.1 (all) — Is the reference standard likely to correctly classify the target condition?**

**3.2 (all) — Were the reference standard results interpreted without knowledge of the results of the index test?**

## Domain 4 — Flow and timing

**4.1 (all) — Was there an appropriate interval between the index test and reference standard?**
Long enough for the condition to change is disease progression bias; short enough that the
reference standard cannot yet detect it is the opposite.

**4.2 (all) — Did all patients receive a reference standard?**

**4.3 (all) — Did all patients receive the same reference standard?**
Differential verification — index-positive patients getting the rigorous reference standard
and index-negative patients getting follow-up instead — biases accuracy upward.

**4.4 (all) — Were all patients included in the analysis?**
Excluding indeterminate index-test results is the usual failure, and it is usually invisible
in the abstract.

## Reporting it

A per-domain table with two columns — risk of bias and (for domains 1–3) applicability
concerns — and Low / High / Unclear in each. `Unclear` is a legitimate, frequent answer in
this literature; a QUADAS-2 assessment with no Unclear cells has usually inferred past what
was reported.

Do not compute a total. QUADAS-2 has no score, and the original QUADAS's summary score was
removed *because* it was being summed.

## Provenance

Whiting PF, Rutjes AWS, Westwood ME, et al. *QUADAS-2: a revised tool for the quality
assessment of diagnostic accuracy studies.* Ann Intern Med 2011;155:529-36, and the QUADAS-2
background document. Question texts are working paraphrases; the signalling questions are
meant to be tailored to the review, so treat this list as the starting set and record any
additions or deletions in the review's methods.
