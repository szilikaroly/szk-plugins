---
name: probast-tripod-ai
description: Assess quality, risk of bias, and applicability of clinical prediction model studies using PROBAST+AI, and check reporting completeness against the TRIPOD+AI checklist. Use whenever a paper, preprint, protocol, or manuscript develops, validates, or evaluates a diagnostic or prognostic prediction model or algorithm — regression or AI/ML-based — and the person asks about its quality, trustworthiness, risk of bias, or reporting completeness, even without naming PROBAST or TRIPOD. Trigger on requests like "is this model any good", "appraise this for my systematic review", "what's my risk of bias here", "does my methods section cover everything before I submit", "what will a reviewer flag", or any mention of a prediction/risk model, algorithm validation, external validation, calibration/discrimination, or an AI diagnostic/prognostic tool in healthcare. Also use proactively when the person is designing or writing up a prediction-model study, to catch gaps before peer review.
---

# PROBAST+AI & TRIPOD+AI

## What these two tools are, and how they differ

Both come from the same working group (Moons, Collins, van Smeden, Riley, Damen, Dhiman et al.) and are meant to be used together, but they answer different questions. Keep them separate — conflating them is the single most common way this kind of appraisal goes wrong.

- **PROBAST+AI** asks: *is the science trustworthy?* It rates **quality** of the model-development process and **risk of bias** in the model-evaluation process, plus **applicability** to a stated question. Four domains, signalling questions, domain judgments, an overall judgment.
- **TRIPOD+AI** asks: *did the paper tell us enough to judge it?* It's a **reporting completeness** checklist — 27 items, 52 subitems. It is explicitly *not* a quality tool. A study can be reported in exhaustive detail and still be low quality; a good study can be badly reported. Don't let a complete TRIPOD+AI checklist stand in for a PROBAST+AI judgment, or vice versa.

Source documents: Moons et al., "PROBAST+AI," *BMJ* 2025;388:e082505 (CC BY-NC 4.0) and Collins et al., "TRIPOD+AI statement," *BMJ* 2024;385:e078378 (CC BY 4.0). See the provenance note at the bottom of this file for exactly what's drawn from where.

## Three modes

Work out which mode (or modes) the person needs from context. Most requests make this obvious; ask only when it genuinely isn't (e.g., someone pastes a manuscript with no framing at all — then a single clarifying question is worth it, since Mode A and Mode B produce very different outputs). State which mode(s) you're running before you start, in a sentence, not as ceremony.

**Mode A — Appraise a study (quality / risk of bias)**
Trigger: an existing paper, preprint, or draft — someone else's or the person's own — and they want a judgment on how trustworthy it is (systematic review, journal club, deciding whether to trust/implement a model, evaluating a PhD student's work).
→ Use `references/probast-ai.md`.

**Mode B — Pre-submission / peer-review reporting check**
Trigger: the person's own manuscript, and they want to know what's missing before submitting, resubmitting, or responding to reviewers.
→ Use `references/tripod-ai.md`.

**Mode C — Design-stage planning**
Trigger: no data yet, or a protocol/analysis plan in progress — they want to design the study so it won't fail appraisal or draw reporting complaints later.
→ Reuse the *development* half of `references/probast-ai.md`, reframed prospectively, plus flag the `references/tripod-ai.md` items that are cheap to plan for now and expensive to retrofit later (see the Mode C workflow below).

A request to "review this study" from someone heading toward submission often means A *and* B together — say so and run both rather than picking one arbitrarily.

## Shared vocabulary

Both tools use near-identical terminology (TRIPOD+AI's glossary is explicitly harmonised with PROBAST+AI's). The essentials:

- **Development/training data** — used to fit the model. **Evaluation/test data** — used to estimate its performance; ideally no participant overlap with development data (overlap = data leakage).
- **Apparent performance** — evaluated on the same data used to develop the model (always optimistic). **Internal validation** — resampling on the development data (bootstrap, cross-validation) to estimate and correct for that optimism. **External validation** — evaluated on genuinely separate data (different time period, centre, or population).
- **Calibration** — do predicted probabilities match observed frequencies? (plot: observed vs. predicted, not just a Hosmer–Lemeshow p-value). **Discrimination** — does the model separate those with/without the outcome? (c-statistic / AUC for binary; c-index for time-to-event).
- **Fairness** — the model doesn't systematically disadvantage a subgroup (age, sex/gender, race/ethnicity, socioeconomic status); assessed via subgroup performance, not just overall metrics.
- **Class imbalance** — outcome frequency is skewed; correction methods (SMOTE, under/oversampling) distort calibration if not corrected for afterward.
- **Hyperparameters** — settings that control model fitting (not fitted from data the same way as model parameters); tuning them needs its own internal-validation loop, nested inside any outer evaluation loop, or it leaks information.

## Workflow — Mode A (PROBAST+AI appraisal)

**Step 1 — PICOTS.** One sentence each: Population, Index model, Comparator (if any), Outcome, Timing, Setting/intended use. If the person hasn't stated their review question or intended use, infer it from context and state the assumption; ask only if the appraisal would go in a materially different direction depending on the answer.

**Step 2 — Classify the study.** Development only / development + evaluation / evaluation only — and for evaluation, apparent / internal / external (a study can report more than one). This matters because the signalling questions differ between the development and evaluation halves of domain 4 (see reference file). Updating an existing model (new predictors, recalibration) counts as development.

**Step 2b — Get the skeleton, and count the slots.** PROBAST+AI is **16 signalling questions for development and 18 for evaluation — 34 in total**, not 23. Domains 1–3 carry the *same question texts* in both halves but are **answered twice** for a development-plus-evaluation study: once judging development *quality*, once judging evaluation *risk of bias*. The same paragraph of a paper can support a Low on one pass and a High on the other, because the two passes ask different things of it. Running domains 1–3 once and reusing the verdict is the most common way an appraisal silently under-counts.

Print the slots rather than working from memory:

```bash
python3 scripts/checklist.py --skeleton probast --scope both   # or development / evaluation
```

**Step 3 — Domain by domain**, in order (Participants & data sources → Predictors → Outcome → Analysis), **once per pass**:
- Answer each signalling question **Yes / Probably yes / No / Probably no / No information**, grounded in what the paper actually says — point to the specific sentence or section. Don't infer past what's reported; "No information" is a normal, common, honest answer, not a failure to find something.
- Give the domain judgment (**Low / High / Unclear** concern) with a sentence of rationale. A single "No" does not automatically mean High, and an all-"Yes" domain isn't automatically Low if the "Yes" answers are themselves thin — use judgment and show your work rather than mechanically rolling up the signalling answers.
- For domains 1–3, also give an **Applicability** judgment (Low/High/Unclear) against the PICOTS from Step 1.

**Step 4 — Overall judgment.** Combine the four domain ratings into one Quality (development) or Risk-of-bias (evaluation) rating, and one Applicability rating, each Low/High/Unclear with a paragraph of rationale. You're allowed to override a domain-level flag at this stage — e.g., a High risk-of-bias flag from "no external validation" in domain 4 can become an overall Low if development used a large dataset with rigorous internal validation and domains 1–3 are all Low — but *only* when you say so explicitly and explain why; never silently smooth over a red flag.

**Step 5 — Verify before you present it.** Save the draft and run:

```bash
python3 scripts/checklist.py --verify <draft>.md --tool probast --scope both
```

It names every slot with no verdict on its line. **"No information" is an
answer; an empty row is not.** The failure mode of a 34-slot instrument is not
a wrong judgment — it is a missing one, because a domain assessed on two of its
four questions still produces a confident-looking rating and nothing in the
output admits which question was never asked. Do not hand over an appraisal
that fails this check; fill the gaps or say why an item is genuinely N/A.

Output using the Mode A table in "Output format" below.

## Workflow — Mode B (TRIPOD+AI reporting check)

1. Confirm scope: development, evaluation, or both — this fixes which items apply (D / E / D;E tags in `references/tripod-ai.md`). Then print the in-scope list rather than working from memory:
   ```bash
   python3 scripts/checklist.py --skeleton tripod --scope both
   python3 scripts/checklist.py --verify <draft>.md --tool tripod --scope both
   ```
2. Go through all 27 items / 52 subitems, ideally in the order the manuscript presents them. For each: **Present / Partial / Missing**, with either where it's covered or a one-line note on what to add.
3. Summarise as a short prioritised list — genuinely missing items likely to draw reviewer pushback, separated from nice-to-have polish. Weight the open-science block (18a–f) and fairness (item 14) heavily: these are the items the literature these tools cite repeatedly flags as weakest, and they're also the fastest for a reviewer to check and complain about.
4. Say explicitly that this checks *completeness of reporting*, not whether the underlying methods were sound. If that hasn't been checked yet, suggest running Mode A too before submission.

Output using the Mode B table in "Output format" below.

## Workflow — Mode C (design-stage)

1. Run the PICOTS + Step 2 classification from Mode A prospectively — force these decisions into words before data collection starts. "We'll define the outcome later" is exactly the drift that shows up as a High-quality-concern domain once the study exists.
2. Turn each *development*-side signalling question from `references/probast-ai.md` into a forward-looking planning prompt. For example, 4.1 ("was there evidence sample size was reasonable") becomes: what's the target events-per-predictor or sample size, and is there an actual prediction-model sample-size calculation behind it (not a hypothesis-testing power calculation — different framework, commonly misapplied here)?
3. Flag which TRIPOD+AI items are cheap to decide now and expensive to retrofit: pre-registration (18d), protocol (18c), the planned missing-data and class-imbalance approach, planned fairness/subgroup evaluation (14, 23a), and how internal validation will be structured (nested correctly if hyperparameters are being tuned).
4. Keep this lightweight — a forward-looking checklist, not a full retrospective appraisal of a study that doesn't exist yet. Don't force every Mode A nuance in here.

## Output format

**Mode A table** — **one row per signalling question**, never one row per domain:

| SQ | Question | Answer | Evidence |
|---|---|---|---|
| 1.1 | Were appropriate data sources used? | Y/PY/N/PN/NI | quote or section pointer |
| 1.2 | Was an appropriate study design used? | … | … |
| 1.3 | Did inclusions/exclusions give a representative dataset? | … | … |

Do not collapse a domain's questions into a single row with one answer. That
template produced appraisals where three questions shared one verdict and
nobody could see which of them was actually assessed — and a domain judgment
resting on an unexamined question reads exactly like one resting on three.

then: **Domain judgment:** Low/High/Unclear — rationale. **Applicability:** Low/High/Unclear — rationale (domains 1–3 only).

Repeat for domains 2–4 (development *or* evaluation column, per Step 2 — or both if the paper covers both), then close with:

**Overall quality / risk of bias:** Low/High/Unclear — rationale. **Overall applicability:** Low/High/Unclear — rationale.

**Mode B table:**

| Item | Section | D/E | Status | Note |
|---|---|---|---|---|
| 3c | Introduction | D;E | Missing | No mention of sociodemographic health inequalities in target population |

Close with the prioritised gap list from Step 3 of the Mode B workflow.

Both tables can also be rendered as a compact traffic-light summary (colour per domain/item) if the person wants something to paste into a manuscript or slide — ask if that's the goal, since it's a different, denser format than the working table above.

## Provenance — what's sourced from where

- PROBAST+AI's four domains, all 34 signalling questions, the four-step procedure, and the glossary: directly from the BMJ 2025 paper's Table 2, Box 1, and main text (as uploaded).
- The per-question Yes/No/NI rating criteria in `references/probast-ai.md` for items that carried over unchanged or with only wording changes from PROBAST-2019: adapted from the PROBAST-2019 Explanation & Elaboration (Moons et al., *Ann Intern Med* 2019;170:W1-33) — which the PROBAST+AI authors themselves say remains the pedagogical background document for these items.
- A handful of PROBAST+AI evaluation-domain items are genuinely new (apparent-performance-only flag, both class-imbalance items, data leakage, resampling replication) and PROBAST+AI's own item-by-item supplementary guidance for these wasn't available when this skill was built. Guidance for these in the reference file is synthesised from the question wording itself, the official PROBAST-2019-to-PROBAST+AI comparison table, and the closely analogous TRIPOD+AI items covering the same concerns (class imbalance item 13, partitioning/leakage item 12a, internal validation item 12c). Flag this provenance gap out loud when a judgment call on one of these specific items is close, and suggest the person check the answer against PROBAST+AI's own supplementary Explanation & Elaboration Light at probast.org if it matters for something high-stakes.
- TRIPOD+AI's full checklist, subitem tags, and the Expanded Checklist (Explanation & Elaboration Light) guidance in `references/tripod-ai.md`: directly from the BMJ 2024 paper and its supplementary Expanded Checklist document.
