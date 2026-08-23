# PROBAST+AI — domain-by-domain reference

<!--
tool: probast-ai
name: PROBAST+AI (prediction model risk of bias, quality and applicability)
engine: checklist.py
answers: Yes|Probably yes|Probably no|No|No information
verdicts: Low|High|Unclear
published_items: 34
unit: prediction MODEL, in one study
use_for: studies that develop, validate or evaluate a diagnostic or prognostic prediction model, regression or AI/ML based
scopes: development, evaluation, both
applicability: domains 1-3
note: domains 1-3 carry the SAME question texts in both passes and are answered TWICE — once judging development quality, once judging evaluation risk of bias. The generic parser in appraise.py cannot express that, which is why this instrument keeps its own engine.
-->


Use this alongside the workflow in the main SKILL.md. Four domains, each with its own signalling questions — **development** and **evaluation** share the same questions for domains 1–3 but diverge in domain 4 (5 items for development, 7 for evaluation). Always check which block applies before answering.

Signalling questions are answered **Yes / Probably yes / No / Probably no / No information (NI)** — phrased so Yes/Probably yes = low concern. NI means the paper genuinely doesn't say, not that you couldn't find it on a quick read.

---

## Domain 1: Participants and data sources

*Same three questions for development and evaluation.*

**1.1 — Were appropriate data sources used?**
- Low concern: prospective cohort (including an RCT arm) or registry data with prespecified, consistently-applied criteria; OR a nested case-control/case-cohort design **with** correct adjustment for the original sampling fraction in the analysis (this recovers correct baseline risk).
- High concern: a non-nested case-control design, or a nested design *without* that adjustment — baseline risk and absolute probabilities can't be correctly recovered, which biases calibration even if discrimination looks fine.
- NI: sampling/recruitment method isn't described clearly enough to tell.
- Note if RCT data are used: treatment allocation should generally be included as a predictor, since an effective treatment is itself a predictor of outcome.

**1.2 — Was an appropriate study design used?**
- Prognostic studies: a prospective longitudinal cohort is low concern. Retrospective reuse of routine-care/EHR data is higher concern by default (inconsistent recording, no protocol) unless the paper demonstrates the data quality was checked and adequate.
- Diagnostic studies: cross-sectional, with predictors and the reference standard measured contemporaneously (or with a justified, bounded follow-up window when the reference standard requires it), is low concern.
- This question was split out from 1.1 in the PROBAST+AI update specifically to separate "was the *source* appropriate" from "was the *design* appropriate for a diagnostic vs. prognostic question" — a good data source can still be paired with an inappropriate design.

**1.3 — Did inclusions/exclusions result in a representative dataset?**
- Low concern: no participants were included who already had the outcome at the point predictors were assessed (this inflates apparent performance and biases toward finding the wrong predictors); no exclusions that quietly narrow the case-mix away from the population the model is meant to serve, without that narrowing being stated as a limitation.
- High concern: e.g., a diagnosis-prediction model developed on people already diagnosed; a study that excludes complex/comorbid patients without flagging that the model therefore doesn't apply to them.
- This is **not** about loss to follow-up after enrolment — that's a domain 4 (analysis) question, not a domain 1 question.

**Domain 1 judgment:** Low / High / Unclear, with rationale. **Applicability:** does the population and setting actually reported match the PICOTS from Step 1 — not whether the study itself was well done (that's the judgment above), but whether it's the *right* study for the question being asked.

---

## Domain 2: Predictors

*Same four questions for development and evaluation.*

**2.1 — Were predictors defined and assessed in a similar way for all participants?**
- Low concern: consistent definitions/instruments across all participants and (if multi-site) across sites.
- High concern: the same nominal predictor measured with different instruments/thresholds for different participants (e.g., "blood in stool" assessed by visual inspection for some, faecal occult blood test for others, pooled as one variable) — especially risky for anything requiring subjective interpretation.

**2.2 — Was any preprocessing of predictors similar for all participants?** *(new relative to PROBAST-2019 — separated out because tree-based and neural-network pipelines routinely apply scaling, encoding, imputation, or embeddings as distinct pipeline steps, and these need to be fit only on training data and applied identically at evaluation.)*
- Low concern: preprocessing/transformation steps (scaling, encoding, imputation, feature engineering) are documented and applied consistently; any parameters of the preprocessing (e.g., normalisation constants) are fit on training data only, not re-derived on evaluation data.
- High concern: preprocessing parameters were refit on the evaluation set, or preprocessing differed between development and evaluation in a way that isn't just "apply the same transform."

**2.3 — Were predictor assessments made without knowledge of outcome data?**
- Low concern: predictors were measured/recorded before outcome status was known, or the paper states outcome information was unavailable to whoever assessed predictors — this is usually structurally true in prospective cohorts (predictors measured before the outcome occurs) even if not explicitly stated as "blinding," and it's reasonable to infer low risk here with a stated rationale.
- High concern: predictor assessment clearly used outcome information (e.g., re-reading imaging with the diagnosis already known).
- NI is common and often still compatible with an overall low-concern domain judgment if the design makes blinding structurally likely (say so in the rationale).

**2.4 — Were the predictors included in the model available at the time the model was intended to be used?**
- Low concern: every predictor in the final model would genuinely be on hand at the point of use (e.g., available to a clinician at triage, or in the record at admission).
- High concern: a model meant for pre-operative use that includes an intra-operative variable; a validation study that dropped predictors unavailable at validation time and validated a *different*, reduced model while calling it the same one.

**Domain 2 judgment + applicability**, same pattern as domain 1 — applicability here means the predictor definitions/timing match what the reviewer's question actually needs, not a general quality judgment.

---

## Domain 3: Outcome

*Same four questions for development and evaluation.*

**3.1 — Were outcomes defined and assessed appropriately?** *(this merges three separate PROBAST-2019 questions — appropriateness of the determination method, use of a standard/prespecified definition, and exclusion of predictors from the outcome definition — into one question in PROBAST+AI.)*
- Low concern: an accepted/guideline-based or previously-validated outcome definition and measurement method; no predictor variable forms part of how the outcome itself was determined (that circularity is "incorporation bias" and inflates apparent performance); no evidence of testing multiple outcome thresholds and reporting the most favourable one.
- High concern: an ad hoc or post hoc outcome definition, especially one chosen after looking at what improves model performance; a predictor variable double-counted inside the outcome definition (e.g., a biomarker used both as a predictor and as part of a composite outcome).

**3.2 — Were outcomes defined and assessed in a similar way for all participants?**
- Same logic as 2.1, applied to the outcome side — consistent thresholds/composite-outcome rules/adjudication method across all participants and sites.

**3.3 — Were outcome assessments made without use or knowledge of predictor data?**
- Mirror of 2.3 in the other direction. Especially important when the explicit aim is comparing models or assessing one predictor's incremental value — then blinding of outcome assessment to predictor data matters more, not less.

**3.4 — Was the time interval between predictor assessment and outcome assessment appropriate?**
- Diagnostic studies: ideally simultaneous, or a follow-up window that's justified by how long it takes the reference standard to become positive.
- Prognostic studies: too short a horizon under-captures the outcome; too long risks capturing a different underlying process. Needs clinical judgment about what's appropriate for the specific outcome, not a fixed rule.
- NI here (no interval reported at all) is a real and common gap.

**Domain 3 judgment + applicability**, same pattern.

---

## Domain 4: Analysis

This is the domain most likely to need a second, statistically-literate pair of eyes on a genuinely borderline case — the PROBAST-2019 authors explicitly recommend involving someone with prediction-modelling statistical expertise here. **Development and evaluation have different question sets.**

### Domain 4 — Development (5 items)

**4.1 — Was there evidence that the sample size was reasonable?**
- Background heuristic (carried over from PROBAST-2019, since PROBAST+AI's own updated numeric guidance for this item isn't available to this skill — treat as a starting point, not gospel): for regression-type models, events-per-predictor-parameter (EPP/EPV) ≥ 20 is comfortable, 10–20 is borderline (judge using outcome prevalence, overall model performance, and predictor distribution), below 10 is a real concern. Count *candidate* predictors considered at any modelling stage, not just those in the final model, and count degrees of freedom (a 6-category predictor costs 5, not 1).
- ML models (random forests, neural networks, gradient boosting) typically need substantially larger effective sample sizes than this to avoid overfitting — flag as a concern if a paper doesn't address sample size adequacy at all, and be more skeptical of "we used all available data" as a sufficient justification for anything beyond simple models.
- Low concern requires an actual justification, not just a large-sounding raw N.

**4.2 — Were continuous and categorical predictors handled appropriately?**
- Low concern: continuous predictors kept continuous, with nonlinearity examined (splines, fractional polynomials) rather than assumed away; where categorisation is used, cut points were prespecified (clinically standard, not data-driven) and there are ≥3–4 categories rather than a single dichotomisation.
- High concern: continuous predictors dichotomised at a data-derived "optimal" cut point (this loses information and inflates apparent associations — a well-documented problem, not a stylistic preference).

**4.3 — Were participants with missing or censored data handled appropriately in the analysis?**
- Low concern: multiple imputation, done separately for development and evaluation data (no leakage); or a clear statement that there was no missingness.
- High concern: unexplained complete-case analysis, single imputation without justification, "missing indicator" method, or last-value-carried-forward used inappropriately; no mention of missingness handling at all despite it being plausible.

**4.4 — If methods to address class imbalance were used, was the model or the model predictions recalibrated?** *(new item)*
- Rebalancing methods (SMOTE, over/undersampling) shift the outcome frequency the model sees during training, which distorts predicted probabilities upward if not corrected for afterward. Low concern requires an explicit recalibration step after any such rebalancing; if no imbalance-correction method was used at all, this item is not applicable.

**4.5 — Were methods used to address potential model overfitting?**
- Low concern: internal validation (bootstrap or cross-validation) that replays *every* development step inside each resample — including any hyperparameter tuning or predictor selection, not just the final fit — with optimism-adjusted performance reported.
- High concern: no internal validation at all; a single random train/test split presented as validation (this is a weak, high-variance substitute, not a real check); cross-validation/bootstrapping that only refits the final chosen model and skips re-doing tuning/selection inside each fold (this understates optimism, sometimes substantially).

### Domain 4 — Evaluation (7 items)

**4.1 — Was model evaluation based on only apparent performance avoided?** *(new item — arguably the single most important gate in this domain)*
- If the *only* performance figure reported is on the same data the model was fit on, with no internal or external validation at all, this is an automatic high-concern flag — apparent performance is essentially always optimistic and on its own tells you little about real-world performance.

**4.2 — Was there evidence that the sample size was reasonable?**
- Background heuristic: evaluation studies are conventionally underpowered below roughly 100 outcome events (from PROBAST-2019 methodology) — below that, performance estimates (especially calibration) get unstable and confidence intervals get wide even before considering bias.

**4.3 — Were participants with missing or censored data handled appropriately in the analysis?**
- Same standard as development 4.3.

**4.4 — If methods to address class imbalance were used, was the evaluation done in a dataset without imbalance correction?** *(new item)* — the evaluation set should reflect the real-world outcome prevalence the model will actually face; evaluating on an artificially rebalanced set gives a misleadingly rosy (or just wrong) picture of real-world performance.

**4.5 — If data splitting was done to create training and test datasets, was there evidence that data leakage was avoided?** *(new item)* — check for: any shared participants/records between train and test (including multiple records per person, e.g. repeated scans); preprocessing/imputation/feature-selection parameters fit on the full dataset before splitting rather than on training data alone; hyperparameter tuning that touched the test set even indirectly.

**4.6 — If resampling methods were used to evaluate model performance, were all model development steps replicated in the resampling process?** *(new item)* — same nested-validation logic as development 4.5, now applied on the evaluation side: if cross-validation is being used to *evaluate* an existing model-building pipeline, every step of that pipeline needs to be redone inside each fold, not just applied once and then evaluated fold-by-fold.

**4.7 — Was the predictive performance of the model evaluated appropriately — e.g., calibration, discrimination, and net benefit?**
- Low concern: both calibration (ideally a smoothed calibration plot, not just a Hosmer-Lemeshow p-value or calibration-in-the-large alone) *and* discrimination reported, with confidence intervals; for time-to-event outcomes, methods that properly account for censoring (Harrell's c-index or similar, not a naive AUC that ignores censoring).
- High concern: discrimination (AUC/c-statistic) reported alone with no calibration assessment at all — this is one of the most common and most consequential gaps in prediction-model evaluation, and worth calling out explicitly whenever you see it, since a well-discriminating but poorly-calibrated model can still give badly wrong absolute risk estimates.

**Domain 4 judgment:** Low / High / Unclear. No applicability rating for domain 4 — analysis-domain concerns are about the study's internal validity, not about matching the reviewer's question, so PROBAST+AI doesn't ask for one here.

---

## Domain-level and overall judgment rules (all domains)

- **Low concern:** all or nearly all signalling questions answered Yes/Probably yes. A domain with one No/Probably no can *still* be rated Low if there's a specific, stated reason the issue isn't expected to introduce meaningful bias here — state that reason explicitly rather than letting the rating imply the answers were all clean.
- **High concern:** any No/Probably no that plausibly distorts the model's estimated performance, unless specifically reasoned to be low-impact (see above). Name which signalling question(s) drove the rating.
- **Unclear concern:** reported information is genuinely insufficient to judge, and none of the answered questions independently justify a High rating on their own.
- **Overall judgment (Step 4)** is not a mechanical roll-up of the four domain ratings — it's a holistic call that can override a single domain's flag when the full picture supports it (e.g., no external validation, by itself, often flags domain 4 evaluation as High — but if development used a large, well-designed dataset with rigorous internal validation and domains 1–3 are all Low, an overall Low risk-of-bias judgment can be defensible). Always make that reasoning explicit when overriding a flag; never silently launder a red flag into a clean-looking summary.
