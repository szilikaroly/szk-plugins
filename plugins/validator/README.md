# Validator

Critical appraisal with the right instrument, every slot answered, and the verdict computed
from the answers.

## Instruments

| Key | Instrument | Answers |
|---|---|---|
| `rob2` | RoB 2 | risk of bias in one **result** of a randomised trial |
| `robins-i` | ROBINS-I | risk of bias vs. a target trial, non-randomised intervention studies |
| `robins-e` | ROBINS-E | risk of bias vs. an ideal observational study, exposures |
| `quadas2` | QUADAS-2 | diagnostic accuracy — bias **and** applicability |
| `quips` | QUIPS | prognostic factor studies, six domains |
| `probast-ai` | PROBAST+AI | prediction models — quality, bias, applicability |
| `tripod-ai` | TRIPOD+AI | prediction models — reporting completeness |
| `amstar2` | AMSTAR 2 | confidence in a systematic review's results |
| `robis` | ROBIS | risk of bias in a systematic review |
| `nos` | Newcastle-Ottawa | stars, with their limits attached |
| `jbi` | JBI checklists | case report, case series, cross-sectional, prevalence, qualitative |
| `grade` | GRADE | certainty of a body of evidence, per outcome |

```bash
A=scripts/appraise.py
python3 $A --list
python3 $A --route "prospective cohort of dietary exposure and endometriosis"
python3 $A --skeleton rob2 --scope assignment > appraisal.md
python3 $A --verify appraisal.md --tool rob2 --scope assignment
python3 $A --rollup appraisal.md --tool rob2 --scope assignment
```

## What the engine guarantees

**Item lists are parsed from `skills/validator/references/*.md`, never duplicated in code.** A
second copy drifts the moment either is edited, and two sources disagreeing silently is worse
than no script at all. `--counts` compares each parsed list against the published total and
exits non-zero on a mismatch — it has already caught two real bugs during development: a
regex that dropped AMSTAR 2's single-digit items 1–9 (7 of 16 parsed) and ROBIS's phase-3
items 3A–3C (21 of 24).

**Polarity is per item.** RoB 2's 1.3, 4.1 and 4.2 are worded so that *Yes* is the problem, and
2.1–2.4 only route to the next question. Treating every "No" as bad rated a well-conducted
open-label trial as high risk on three domains at once.

**Published algorithms are reproduced where they exist** — AMSTAR 2's critical-flaw table, the
Newcastle-Ottawa star count, GRADE's start-and-adjust — and **not faked where they do not**.
For RoB 2 and the ROBINS family the rollup reports what the recorded answers force and names
the questions that forced it, then says explicitly that this is not the official flowchart.

## What it refuses to do

- sum or average domains into a score (ROBINS-I, RoB 2, QUADAS-2, AMSTAR 2 and JBI have no total);
- report a Newcastle-Ottawa threshold as if the scale published one (it does not);
- flatten PROBAST+AI's two passes over domains 1–3 into one (34 slots, not 23) — that instrument
  keeps its own engine, `scripts/checklist.py`;
- assert an item count that cannot be checked against the published tool. Where the count could
  not be confirmed, `--counts` carries no expected total and the reference file says why.

## Self test

```bash
python3 scripts/selftest.py     # 40 assertions, offline
python3 scripts/appraise.py --counts
python3 scripts/checklist.py --counts
```

Every assertion corresponds to a bug that actually occurred while this engine was
built: the id regex that dropped AMSTAR 2's single-digit items and ROBIS's
phase-3 items, the line-wide answer search that read "N" out of RoB 2's own
question text, the polarity handling that rated every open-label trial high risk,
the unscoped rollup that reported "9/18 stars" for a Newcastle-Ottawa cohort, and
the GRADE substring test in which "not serious" contained "serious" and
downgraded every domain the assessor had explicitly cleared.

## Provenance

Every reference file ends with a note naming the source paper and stating what is verbatim,
what is paraphrased and what is this repository's own recommendation. Item texts are working
paraphrases in each tool's vocabulary — use the published wording when an assessment appears
in a manuscript, and name the tool version in the methods section.
