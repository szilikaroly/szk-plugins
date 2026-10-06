# Newcastle-Ottawa Scale — cohort and case-control studies

<!--
tool: nos
name: Newcastle-Ottawa Scale (NOS) — star system for cohort and case-control studies
answers: Yes|Partial yes|No|Unclear
aliases: Y=Yes; N=No; U=Unclear
unknown_answer: Unclear
verdicts: see the note on thresholds — the scale publishes none
published_by_scope: cohort=8; case-control=8
item_answers: S1,S2,S3,S4,O1,O2,O3,S5,S6,S7,S8,E1,E2,E3=Yes|No|Unclear; C1,C2=Yes|Partial yes|No|Unclear
unit: STUDY
use_for: cohort and case-control studies, when a star-based appraisal is required
scopes: cohort, case-control
scope_required: The cohort and case-control scales are separate forms of 8 items and 9 stars each; a study is rated on one of them, never out of 18.
-->

## Read this before using it

The NOS is the most-used and least-defensible instrument in this file. It is here because
journals and reviewers still ask for it, not because it is the best available answer.

Three things to know, and to say in your methods section if you use it:

1. **There is no official threshold.** The 7-9 = good / 4-6 = fair / 0-3 = poor cut-offs that
   appear in hundreds of reviews come from an AHRQ conversion, not from the scale's authors.
   If you use a threshold, name where you got it.
2. **Summing stars across domains assumes they are commensurable, and they are not.** A star
   for "adequacy of follow-up" and a star for "representativeness of the exposed cohort" are
   not interchangeable, and a study can lose the one that actually invalidates it while
   scoring 7.
3. **Its inter-rater reliability is poor** and has been repeatedly documented as such.

**Prefer ROBINS-I** (intervention questions) or **ROBINS-E** (exposure questions) whenever the
review will be scrutinised. Use the NOS when a journal or a supervisor requires it — and then
report the per-domain stars, never the total alone.

## One form per study

The cohort and the case-control scales are **separate questionnaires**, each 8 items and at most
9 stars (selection 4, comparability 2, outcome or exposure 3). Pick the one that fits the
design: `--skeleton nos --scope cohort` or `--scope case-control`, and the same scope for
`--verify` and `--rollup`. Without a scope the engine refuses (exit 2): in 2.0.0 it merged the
two forms into a 16-slot skeleton and reported totals such as "9/18 stars", a denominator the
scale never has.

## How the stars are counted

Each Selection and Outcome / Exposure item earns **at most one star** — Yes or nothing. Only
the comparability items (C1, C2) carry two stars, and only there does **Partial yes** mean
something: one of the two stars, for controlling the single most important factor but no
other. *Partial yes* on a one-star item is not an answer the scale offers; `--verify` rejects
it and the rollup scores it 0. There is no "PY" shorthand for this scale — write *Partial yes*.

There is no *not applicable* either: an item earns its star or it does not, and *Unclear* is the
answer when the paper does not say. `--verify` rejects N/A, and the rollup marks a count with
an N/A in it provisional (exit 1) — in 2.0.0 an all-N/A record came out "0/9 stars", final.

## Cohort studies — 8 items, 9 stars

### Domain S — Selection

**S1 (cohort) — Representativeness of the exposed cohort.**
Truly or somewhat representative of the average exposed person in the community earns a star;
a selected group of users, or no description, does not.

**S2 (cohort) — Selection of the non-exposed cohort.**
Drawn from the same community as the exposed cohort earns a star; a different source does not.

**S3 (cohort) — Ascertainment of exposure.**
Secure record or structured interview earns a star; written self-report or no description does
not.

**S4 (cohort) — Demonstration that the outcome of interest was not present at the start of the study.**

### Domain C — Comparability

**C1 (cohort, 2star) — Comparability of cohorts on the basis of the design or analysis.**
One star for controlling the single most important factor, a second for controlling any other
important factor. **Name the two factors in your protocol before you read the study** —
otherwise this item measures what the authors chose to adjust for.

### Domain O — Outcome

**O1 (cohort) — Assessment of outcome.**
Independent blind assessment or record linkage earns a star; self-report does not.

**O2 (cohort) — Was follow-up long enough for outcomes to occur?**
Against a duration you specify in advance.

**O3 (cohort) — Adequacy of follow-up of cohorts.**
Complete follow-up, or loss unlikely to introduce bias with a description of those lost.

## Case-control studies — 8 items, 9 stars

### Domain S — Selection

**S5 (case-control) — Is the case definition adequate?**
Independent validation earns a star; record linkage or self-report alone does not.

**S6 (case-control) — Representativeness of the cases.**
Consecutive or obviously representative series.

**S7 (case-control) — Selection of controls.**
Community controls earn a star; hospital controls do not.

**S8 (case-control) — Definition of controls.**
No history of the disease, stated.

### Domain C — Comparability

**C2 (case-control, 2star) — Comparability of cases and controls on the basis of the design or analysis.**
Same rule as C1, and the same warning.

### Domain E — Exposure

**E1 (case-control) — Ascertainment of exposure.**
Secure record or blinded structured interview earns a star.

**E2 (case-control) — Same method of ascertainment for cases and controls.**

**E3 (case-control) — Non-response rate.**
Same rate for both groups, described.

## Provenance

Wells GA, Shea B, O'Connell D, et al. *The Newcastle-Ottawa Scale (NOS) for assessing the
quality of nonrandomised studies in meta-analyses.* Ottawa Hospital Research Institute (no
formal journal publication). One star per Selection and Outcome / Exposure item and up to two
for comparability is the scale's rule as applied in published reviews (e.g. PMC13222748); the
separate cohort and case-control questionnaires with a maximum of nine stars each are described
in Lo, Mertz and Loeb, BMC Med Res Methodol 2014;14:45 (PMC4021422, Methods).
Item texts are working paraphrases of the published coding manual; the star-allocation
rules above are compressed and the manual should be consulted for the exact criteria. The absence of an official threshold, the poor reliability, and the
commensurability problem are documented in the methodological literature and are stated here
because a tool this widely used deserves its limits attached to it.
