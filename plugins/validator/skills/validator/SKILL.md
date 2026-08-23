---
name: validator
description: Critical appraisal of study quality, risk of bias and certainty of evidence with the correct instrument — RoB 2 (randomised trials), ROBINS-I (non-randomised interventions), ROBINS-E (exposures), QUADAS-2 (diagnostic accuracy), QUIPS (prognostic factors), PROBAST+AI and TRIPOD+AI (prediction models and their reporting), AMSTAR 2 and ROBIS (systematic reviews), Newcastle-Ottawa, JBI checklists (case reports, case series, cross-sectional, prevalence, qualitative) and GRADE (certainty per outcome). Use whenever a study, preprint, manuscript or body of evidence needs appraising — "is this study any good", "assess the risk of bias", "appraise these for my systematic review", "what will a reviewer flag", "rate the certainty of the evidence", "which tool should I use for this design", filling a risk-of-bias table for a review, or planning a study so it will not fail appraisal later. Hungarian triggers — torzítás kockázata, kritikai értékelés, evidenciaszint, bizonyítékbiztonság, minőségértékelés, RoB, GRADE-elés, melyik eszközzel értékeljem.
---

# Validator

Three failures make an appraisal worthless, and this skill is built against each of them:

1. **The wrong instrument.** An appraisal done with a tool that does not fit the design is not
   a weak appraisal, it is an inapplicable one. Route first.
2. **A missing answer.** A domain rated on two of its four signalling questions produces a
   confident-looking verdict, and nothing in the output says which question was never asked.
   Verify before presenting.
3. **A verdict that does not follow from the answers.** Where the instrument publishes a rating
   algorithm, the verdict is arithmetic. Compute it and show the arithmetic.

```bash
A="${CLAUDE_PLUGIN_ROOT}/scripts/appraise.py"
python3 "$A" --list
python3 "$A" --route "<study design in the user's own words>"
python3 "$A" --skeleton <tool> [--scope <variant>]     # every slot to fill
python3 "$A" --verify  draft.md --tool <tool>          # what was left blank
python3 "$A" --rollup  draft.md --tool <tool>          # what the answers force
```

## Choosing the instrument

| The study is… | Instrument | Answers |
|---|---|---|
| a randomised trial | **rob2** | risk of bias in **this result** |
| a non-randomised study of an intervention | **robins-i** | risk of bias vs. a target trial |
| an observational study of an exposure | **robins-e** | risk of bias vs. an ideal observational study |
| a diagnostic accuracy study | **quadas2** | risk of bias **and** applicability |
| a prognostic factor study | **quips** | quality across six domains |
| a prediction / risk model study | **probast-ai** | quality, risk of bias, applicability |
| a prediction model manuscript before submission | **tripod-ai** | reporting completeness, not quality |
| a systematic review, and you are deciding whether to trust it | **amstar2** | confidence in the review's results |
| a systematic review you are including as evidence | **robis** | risk of bias in the review |
| a cohort or case-control study, and a journal demands stars | **nos** | a star count, with its limits stated |
| a case report, case series, cross-sectional, prevalence or qualitative study | **jbi** | design-specific checklist |
| a whole body of evidence for one outcome | **grade** | certainty: High / Moderate / Low / Very low |

Two pairs are complements, not alternatives, and running only one leaves a gap the user will
be asked about:

- **PROBAST+AI answers "is the science trustworthy"; TRIPOD+AI answers "did the paper say
  enough to judge it".** A study can be exhaustively reported and low quality, or well
  conducted and badly reported. Someone heading toward submission usually needs both.
- **AMSTAR 2 rates the review's conduct; GRADE rates the certainty of the evidence it
  synthesised.** These are constantly conflated. A methodologically excellent review of four
  small biased trials is AMSTAR 2 High and GRADE Very low, and both statements are true.

When `--route` returns more than one instrument, say which question is being answered and run
that one — do not run all of them to be safe.

## Workflow

### 1. Fix the unit of assessment before anything else

This is where most appraisals go wrong, silently:

| Tool | Assessed per |
|---|---|
| rob2 | **one result** — one outcome from one trial. The same trial can be low risk for mortality and high risk for a patient-reported score |
| robins-i / robins-e | **one result** — one outcome, one comparison |
| quadas2 | one study, **per index test** |
| quips | one study, **per prognostic factor and outcome** |
| probast-ai | one **model**, in one study |
| amstar2 / robis | the **review** |
| nos / jbi | the **study** |
| grade | **one outcome**, across the whole body of evidence |

An appraisal that produces one RoB 2 verdict "for the trial" has used the wrong unit and is not
interpretable. Say which unit you are using in the first line of the output.

### 2. Write down what the appraisal is against

- **ROBINS-I**: the target trial — eligibility, the two interventions, the outcome and its
  timing, in three lines.
- **ROBINS-E**: the preliminary considerations — effect of interest, the confounders you will
  require, and the exposure window.
- **PROBAST+AI**: PICOTS.
- **QUADAS-2**: the review question, so the signalling questions can be tailored to it —
  QUADAS-2 is explicitly designed to be tailored, and an untailored application is a misuse.
- **All of them**: the confounder list, decided *before* reading the paper's adjustment table.
  Otherwise the study defines the standard it is judged by.

### 3. Print the slots, then fill them from the paper

```bash
python3 "$A" --skeleton rob2 --scope assignment > appraisal.md
```

Answer each signalling question from **what the paper actually says**, pointing at the specific
sentence, table or section. Do not infer past what is reported: **"No information" is a normal,
common, honest answer**, not a failure to find something. In the reference files each item
carries guidance and a polarity tag:

- **normal** — `No` is the problem;
- **reverse** — `Yes` is the problem (RoB 2's 1.3, 4.1, 4.2; QUIPS's 3.6; ROBIS's 1.4);
- **router** — the answer decides which question comes next and means nothing on its own
  (RoB 2's 2.1: every open-label trial answers Yes, and scoring that as a problem would rate
  every unblinded trial high risk).

### 4. Verify, then roll up

```bash
python3 "$A" --verify appraisal.md --tool rob2 --scope assignment
python3 "$A" --rollup appraisal.md --tool rob2 --scope assignment
```

`--verify` names every slot with no verdict on its line and exits non-zero. Do not hand over an
appraisal that fails it; fill the gaps or say why an item is genuinely N/A.

`--rollup` behaves differently depending on whether the tool publishes an algorithm:

- **AMSTAR 2, Newcastle-Ottawa, GRADE** — the rating *is* an algorithm, and it is reproduced
  exactly (AMSTAR 2's critical-flaw table, the star count, GRADE's start-and-adjust).
- **RoB 2, ROBINS-I, ROBINS-E, QUADAS-2, QUIPS, JBI, ROBIS** — the rollup reports what the
  recorded answers *force* and names the questions that forced it. It does **not** reproduce
  the official flowcharts, which branch on particular questions. For a borderline domain, run
  the answers through the source algorithm and say that you did.

### 5. Report it

**One row per signalling question**, never one row per domain:

| SQ | Question | Answer | Evidence |
|---|---|---|---|
| 1.1 | Was the allocation sequence random? | Yes | "computer-generated", Methods p.3 |

Collapsing a domain's questions into a single row produces appraisals where three questions
share one verdict and nobody can see which of them was actually assessed — and a domain
judgement resting on an unexamined question reads exactly like one resting on three.

Then per domain: the verdict plus one sentence of rationale, and for QUADAS-2 and PROBAST+AI
the separate applicability judgement. Then the overall, with a paragraph.

You may override the arithmetic — but only explicitly. "Domain 4 is High on the algorithm
because of the unblinded assessor, but the outcome is all-cause mortality from a national
registry, so I rate it Low" is a legitimate appraisal. Silently smoothing over the flag is not.

### 6. Never do these

- **Do not sum or average domains.** ROBINS-I, RoB 2, QUADAS-2, AMSTAR 2 and JBI have no total.
  A "ROBINS-I score" or "JBI score 7/8" is a misuse of the instrument.
- **Do not use a scale where a risk-of-bias tool exists.** Jadad is not a risk-of-bias
  assessment, and AMSTAR 2 item 9 fails a review that used one.
- **Do not apply quantitative criteria to qualitative research.** Sample size, blinding and
  confounding are not qualitative concepts; for certainty of qualitative evidence use
  GRADE-CERQual, not GRADE.
- **Do not report a Newcastle-Ottawa threshold without saying where it came from.** The
  7-9 / 4-6 / 0-3 cut-offs are an AHRQ conversion, not the scale authors'.

## PROBAST+AI and TRIPOD+AI run on their own engine

```bash
C="${CLAUDE_PLUGIN_ROOT}/scripts/checklist.py"
python3 "$C" --skeleton probast --scope both      # all 34 slots
python3 "$C" --skeleton tripod  --scope both
python3 "$C" --verify draft.md --tool probast --scope both
python3 "$C" --counts
```

PROBAST+AI is **16 signalling questions for development and 18 for evaluation — 34 in total**,
not 23. Domains 1–3 carry the *same question texts* in both halves and are **answered twice**
for a development-plus-evaluation study: once judging development *quality*, once judging
evaluation *risk of bias*. The same paragraph can support a Low on one pass and a High on the
other, because the two passes ask different things of it. Running domains 1–3 once and reusing
the verdict is the most common way such an appraisal silently under-counts — which is why this
instrument keeps its own engine rather than being flattened into the generic one.

The domain-by-domain guidance is in `references/probast-ai.md` and `references/tripod-ai.md`.

## Provenance

Every reference file ends with a provenance note naming the source paper and stating exactly
what is verbatim, what is paraphrased, and what is this file's own recommendation. Read it
before quoting an item in a manuscript. Where an item count could not be confirmed against the
published tool, `--counts` deliberately carries no expected total and the file says so — a
number asserted here that nobody can check would be worse than no number.
