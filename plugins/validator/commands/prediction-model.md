---
description: PROBAST+AI és TRIPOD+AI — prediktív modell minősége és jelentésének teljessége
allowed-tools: Bash, Read, Write
---
Appraise a prediction-model study. Target: $ARGUMENTS

```
C="${CLAUDE_PLUGIN_ROOT}/scripts/checklist.py"
python3 "$C" --skeleton probast --scope both     # 34 slots: 16 development + 18 evaluation
python3 "$C" --skeleton tripod  --scope both     # 27 items / 52 subitems
python3 "$C" --verify draft.md --tool probast --scope both
```

Decide which mode(s) apply and say so in one sentence before starting:

- **Appraising someone's study** (systematic review, journal club, deciding whether to trust a
  model) → PROBAST+AI.
- **Own manuscript before submission or resubmission** → TRIPOD+AI.
- **Design stage, no data yet** → the development half of PROBAST+AI, reframed prospectively,
  plus the TRIPOD+AI items that are cheap now and expensive to retrofit: pre-registration,
  protocol, the planned missing-data and class-imbalance approach, planned fairness/subgroup
  evaluation, and how internal validation will be nested if hyperparameters are tuned.

"Review this study" from someone heading toward submission usually means **both** — say so and
run both rather than picking one arbitrarily.

**The counting trap.** PROBAST+AI is 34 slots, not 23. Domains 1–3 carry the same question
texts in both passes and are answered **twice** for a development-plus-evaluation study — once
judging development *quality*, once judging evaluation *risk of bias*. The same paragraph can
support Low on one pass and High on the other. Run domains 1–3 once and reuse the verdict and
the appraisal silently under-counts.

Guidance is in `references/probast-ai.md` and `references/tripod-ai.md`. Report one row per
signalling question, never one per domain.
