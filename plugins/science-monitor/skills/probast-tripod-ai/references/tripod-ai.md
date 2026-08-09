# TRIPOD+AI — reporting checklist reference

27 items, 52 subitems. Each is tagged **D** (development studies only), **E** (evaluation studies only), or **D;E** (both). Check the manuscript's scope first (Mode B, step 1) and skip items that don't apply — a pure external-validation paper doesn't need to satisfy D-only items like model specification (22) or model output (15).

This checks **completeness of reporting only** — whether the paper told readers enough to judge it, not whether what it did was methodologically sound. Use `probast-ai.md` for the soundness question.

Source: Collins et al., "TRIPOD+AI statement," *BMJ* 2024;385:e078378, and its Expanded Checklist (Explanation & Elaboration Light) supplement — both CC BY 4.0.

---

## Title

**1 (D;E)** — Identify the study as developing or evaluating a prediction model, name the target population, and name the outcome predicted. *Common gap: titles like "A machine learning model for X" that don't specify development vs. evaluation, or omit the population.*

## Abstract

**2 (D;E)** — See the Abstracts checklist at the bottom of this file (13 items).

## Introduction

**3a (D;E)** — Healthcare context (diagnostic or prognostic), rationale for developing/evaluating this model, references to existing models for the same purpose.
**3b (D;E)** — Target population and intended purpose in the care pathway — what decision this is meant to inform, at what point, for whom (clinicians? patients? both?).
**3c (D;E)** — Known health inequalities between sociodemographic groups in the target population, with citations. *New in +AI, frequently absent entirely — worth checking explicitly rather than assuming it's covered elsewhere.*
**4 (D;E)** — Explicit statement of study objectives: development, evaluation, or both.

## Methods

**5a (D;E)** — Data source(s) for development and evaluation *separately* (trial, cohort, routine care, registry), rationale for using this source, and its representativeness of the target population.
**5b (D;E)** — Start/end dates of participant accrual; end of follow-up if applicable.
**6a (D;E)** — Study setting (primary/secondary care, general population), number and location of centres.
**6b (D;E)** — Eligibility criteria for participants.
**6c (D;E)** — Treatments received and how handled during development/evaluation, if relevant.
**7 (D;E)** — Data pre-processing and quality-checking steps (cleaning, harmonisation, feature engineering); whether these were applied consistently across sociodemographic groups.
**8a (D;E)** — Outcome definition, time horizon, how/when assessed, rationale for choosing it, consistency of assessment across sociodemographic groups.
**8b (D;E)** — If outcome assessment needs subjective interpretation: assessor qualifications and demographics.
**8c (D;E)** — Actions taken to blind outcome assessment (avoiding label leakage).
**9a (D)** — How the initial predictor list was chosen (literature, prior models, all available data) and any pre-selection before modelling.
**9b (D;E)** — Clear definition of every predictor, incl. how/when measured, and blinding actions.
**9c (D;E)** — If predictor measurement needs subjective interpretation: assessor qualifications and demographics.
**10 (D;E)** — How the study size was determined, separately for development and evaluation, with justification that it's sufficient — not just "we used all available data" with no comment on adequacy.
**11 (D;E)** — How missing data were handled, and reasons for any omitted data.
**12a (D)** — How data were used/partitioned (development, hyperparameter tuning, evaluation), with sample-size reasoning behind the partitioning; confirmation of no leakage if the data contain multiple records per person.
**12b (D)** — How predictors were handled analytically (functional form, rescaling, transformation, standardisation).
**12c (D)** — Model type and rationale, all model-building steps including hyperparameter tuning, and the internal-validation method — with confirmation that *all* build steps were replayed inside internal validation, not just the final fit.
**12d (D;E)** — Handling/quantification of heterogeneity across clusters (hospitals, countries) if relevant — see TRIPOD-Cluster for specialised recommendations if this is central to the study.
**12e (D;E)** — All performance measures and plots used, with rationale; method for comparing models if more than one was built.
**12f (E)** — Any model updating (e.g., recalibration) arising from the evaluation.
**12g (E)** — How predictions were actually calculated for evaluation (formula, code, object, API) — especially important when there's no closed-form equation (tree ensembles, neural nets).
**13 (D;E)** — If class-imbalance methods were used: why, how, and any subsequent recalibration.
**14 (D;E)** — Approaches used to address model fairness, with rationale. *Emphasised throughout TRIPOD+AI — check this is a substantive paragraph with method, not a token sentence asserting fairness was considered.*
**15 (D)** — What the model outputs (probability vs. classification); rationale and threshold derivation for any classification/risk grouping.
**16 (D;E)** — Differences between development and evaluation data in setting, eligibility, outcome, or predictor definitions.
**17 (D;E)** — Named ethics committee/IRB approval, and how informed consent (or a waiver) was handled.

### Open science

**18a (D;E)** — Funding source and the funder's role.
**18b (D;E)** — Conflicts of interest and financial disclosures, all authors.
**18c (D;E)** — Where the study protocol can be accessed, or an explicit statement that none was prepared.
**18d (D;E)** — Registration details (register name, number), or an explicit statement that the study wasn't registered.
**18e (D;E)** — Data availability, with actual conditions specified — "available upon reasonable request" with no further detail is explicitly called out in the guideline as insufficient.
**18f (D;E)** — Code availability, incl. how to retrieve it and any licence/version conditions; this covers analysis code (cleaning, feature engineering, model building) *and*, separately, the code needed to generate predictions for a new individual (see item 22).

## Patient & public involvement

**19 (D;E)** — Details of PPI during design, conduct, reporting, or dissemination — or an explicit "none."

## Results

**20a (D;E)** — Participant flow (a diagram helps); numbers with/without the outcome; follow-up summary.
**20b (D;E)** — Baseline characteristics — dates, predictors (incl. demographics), treatments, sample size, outcome events, follow-up time, missingness — overall and by data source/setting; differences across demographic groups.
**20c (E)** — For evaluation studies: comparison of the evaluation-data predictor/outcome distribution against the development data.
**21 (D;E)** — N participants and N outcome events in *each* analysis separately (development, hyperparameter tuning, evaluation) — these routinely differ due to partitioning and missing data, and readers need each one, not just an overall total.
**22 (D)** — Full model specification (equation, code, software object, or API) sufficient for a third party to generate predictions and evaluate the model independently, plus access/reuse conditions if it isn't freely available.
**23a (D;E)** — Performance estimates with confidence intervals, including for key subgroups; plots where they aid interpretation.
**23b (D;E)** — Heterogeneity in performance across clusters, if examined.
**24 (E)** — Results of any model updating, including the updated model's own performance.

## Discussion

**25 (D;E)** — Overall interpretation of the main results, including fairness issues, in the context of the study's objectives and prior models/studies.
**26 (D;E)** — Limitations — representativeness, sample size, overfitting, missing data — and their implications for bias, statistical uncertainty, and generalisability.
**27a (D)** — How poor-quality or unavailable input data should be assessed and handled at the point of use.
**27b (D)** — Whether/how much user interaction is required at the point of use, and what expertise users need.
**27c (D;E)** — Next steps for future research, specifically regarding applicability and generalisability.

---

## TRIPOD+AI for Abstracts (13 items)

Use this when the check is specifically on an abstract (a submission, a conference abstract, or a manuscript's abstract section in isolation).

1. Identify as development/evaluation, name the target population and outcome.
2. Brief healthcare context and rationale.
3. State objectives (development, evaluation, or both).
4. Describe data source(s).
5. Describe eligibility criteria and setting.
6. Specify the predicted outcome, incl. time horizon for prognostic models.
7. Specify model type, summary of build steps, and internal-validation method *(development only)*.
8. Specify performance measures used.
9. Report N participants and N outcome events.
10. Summarise predictors in the final model *(development only)*.
11. Report performance estimates with confidence intervals.
12. Overall interpretation of main results.
13. Registration number and registry/repository name.

---

## Known weak spots

The systematic reviews that motivated both TRIPOD+AI and PROBAST+AI (cited throughout the source papers) consistently flag the same gaps across the literature. Worth checking for these specifically, since they're common enough to be a reasonable default suspicion rather than a random guess:

- **Calibration reported thin or missing**, discrimination reported alone (item 12e/23a) — the single most consequential recurring gap.
- **Open science items (18a–f) incomplete**, especially data/code availability given only as a platitude rather than actual conditions.
- **Sample size adequacy not addressed** (item 10) beyond stating the raw N.
- **Fairness (item 14) present as a token sentence** rather than a described method with subgroup results to match (23a).
- **Health inequalities context (3c)** and **patient/public involvement (19)** — both new-ish emphases, frequently just absent rather than explicitly declined.
