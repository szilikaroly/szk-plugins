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
python3 $A --migrate old-1x.md --tool robins-i --scope adherence > appraisal.md
```

Exit codes: **0** complete and final; **1** unanswered, invalid, undecided (GRADE publication
bias) or in an old item numbering — the output says which; **2** usage error (an unknown
`--scope`, or a tool that runs on `scripts/checklist.py`).

## What the engine guarantees

**Item lists are parsed from `skills/validator/references/*.md`, never duplicated in code.** A
second copy drifts the moment either is edited, and two sources disagreeing silently is worse
than no script at all. `--counts` compares each parsed list against the published total and
exits non-zero on a mismatch — it has already caught two real bugs during development: a
regex that dropped AMSTAR 2's single-digit items 1–9 (7 of 16 parsed) and ROBIS's phase-3
items 3A–3C (21 of 24).

**Nothing is rated from a partial record.** A domain with a blank or invalid answer is
INCOMPLETE, not LOW, and the overall follows; GRADE gives no certainty while a domain is blank
or publication bias is undecided.

**Polarity is per item.** QUADAS-2, ROBINS and ROBIS items are tagged by which answer is the
problem; ROBINS-I's 1.2–1.3 only route to the next question. Treating every "No" as bad rated
a well-conducted study as high risk. A fourth tag, *middle*, marks answers that rule out the low
tier but cannot by themselves reach the top one — ROBINS-I's "is there potential for
confounding?" is Yes for nearly every observational study.

**Answer words are per instrument.** Each reference file declares its vocabulary, its
shorthands and any per-item restriction: *PY* is *Probably yes* in RoB 2 but *Partial yes* in
AMSTAR 2, the Newcastle-Ottawa scale gives a partial star only for comparability, and N/A is
accepted only where the instrument offers it (RoB 2's conditional questions, none in ROBIS or
the Newcastle-Ottawa scale).

**Published algorithms are reproduced where they exist** — RoB 2's per-domain algorithm (2019
guidance; the rollup prints the path it took), AMSTAR 2's critical-flaw table, the
Newcastle-Ottawa star count, GRADE's start-and-adjust, ROBIS's overall as the phase-3
judgement — and **not faked where they do not**. For the ROBINS family, QUADAS-2, QUIPS and
JBI the rollup reports what the recorded answers force and names the questions that forced
it, then says explicitly that this is not the official flowchart.

## What it refuses to do

- sum or average domains into a score (ROBINS-I, RoB 2, QUADAS-2, AMSTAR 2 and JBI have no total);
- report a Newcastle-Ottawa threshold as if the scale published one (it does not);
- flatten PROBAST+AI's two passes over domains 1–3 into one (34 slots, not 23) — that instrument
  keeps its own engine, `scripts/checklist.py`;
- assert an item count that cannot be checked against the published tool. Where the count could
  not be confirmed, `--counts` carries no expected total and the reference file says why.

## Self test

```bash
python3 scripts/selftest.py     # offline, deterministic
python3 scripts/appraise.py --counts
python3 scripts/checklist.py --counts
```

Every assertion corresponds to a bug that actually occurred while this engine was
built: the id regex that dropped AMSTAR 2's single-digit items and ROBIS's
phase-3 items, the line-wide answer search that read "N" out of RoB 2's own
question text, the polarity handling that rated every open-label trial high risk,
the unscoped rollup that reported "9/18 stars" for a Newcastle-Ottawa cohort, and
the GRADE substring test in which "not serious" contained "serious" and
downgraded every domain the assessor had explicitly cleared. The 2.0.0 block
adds one test per defect listed below; each of them fails against 1.0.0, and the
methodology-review block fails against the first 2.0.0 commit (60e290b).

## Provenance

Every reference file ends with a note naming the source paper and stating what is verbatim,
what is paraphrased and what is this repository's own recommendation. Item texts are working
paraphrases in each tool's vocabulary — use the published wording when an assessment appears
in a manuscript, and name the tool version in the methods section.

## Changes

### 2.0.0 — methodology review (same release)

A review of 2.0.0 against the published instruments found verdicts that the instruments do not
give. Each fix has regression tests in `scripts/selftest.py` (103 → 163 assertions; run against
the first 2.0.0 commit, 42 of them fail).

- **RoB 2 runs its published algorithm.** The generic tags cannot express a gate: 3.1 *No* with
  3.2 *Yes* (any result with a robustness sensitivity analysis) was rated HIGH, overall HIGH,
  exit 0; 2.3 *NI*, 2.4 *Yes* with 2.5 *Yes*, and 4.4 *Yes* with 4.5 *No* came out LOW; *NI* at
  2.5, 2.7 and 4.5, and at the adhering variant's 2.6, stayed at Some concerns; 1.1 *No* or
  1.3 *Yes* with concealed allocation, 2.6 *No* with 2.7 *No*, and 5.1 *No* were HIGH; *NI* at
  1.1, 1.3 and 4.1 ruled out Low. `--rollup` now walks each domain the way the 22 August 2019
  guidance routes it (criteria tables as reproduced in PMC8191126) and prints the path;
  N/A at a question the walk reaches makes the domain INCOMPLETE.
- **N/A only where offered.** RoB 2 (outside its conditional questions), ROBIS and PROBAST+AI
  (outside development 4.4, evaluation 4.4–4.6) accepted N/A everywhere: an all-N/A record
  verified complete and rolled up LOW. New meta key `not_applicable` (scope-qualified ids allowed).
- **ROBIS overall is the phase-3 judgement** (Whiting 2016, PMC4687950, section 3.3), not the
  worst of domains 1–4: a domain-4 concern addressed in the interpretation (3A *Yes*) ended
  HIGH at exit 0. New meta key `overall_from`.
- **Newcastle-Ottawa is one form per study.** Without `--scope` the cohort and case-control
  forms merged into 16 slots and "9/18 stars"; `--scope cohort|case-control` is now required
  (exit 2 otherwise; meta key `scope_required`), and `rollup_nos` refuses a mixed item set.
  N/A, which the scale does not offer, is rejected — an all-N/A record was a final "0/9 stars".
- **TRIPOD+AI for Abstracts** rows 1–13 answered main items 1–13, and a numbered gap list
  ("1. Item 18e — Missing") answered item 1: blank main items verified 52/52. Nothing under a
  heading that names the abstracts checklist is read; a prose line that names another item is
  skipped; a table's *Item* column is the id when it is not the first column. `appraise.py`
  had the same keying bug (an AMSTAR 2 gap list "1. Item 7 — No" answered item 1) and gets the
  same two rules.
- **GRADE 8.1** asked whether confounding "created a spurious null" — the reverse of GRADE's
  criterion (PMID 21802902), which rates up when all plausible biases would have suggested an
  effect where none is observed. Reworded.
- **AMSTAR 2 Partial yes** counted as a weakness on critical items but was silently "met" on
  item 8; it is now a non-critical weakness on every item that offers it, and the rollup states
  that this is the tool's convention (the paper does not fix one) and that Box 2 is advisory.
  The skeleton and the rollup say that items 9 and 11 hold the worse of the RCT and NRSI
  judgements in a mixed-design review.

### 2.0.0 — the defects a real workbench found

Found while building a meta-analysis workbench on top of 1.0.0; every item has a regression
test in `scripts/selftest.py`, and the sources each fix was checked against are named in the
reference files' provenance notes.

- **Incomplete domains.** A domain with an unanswered question was rated LOW from the answered
  ones, unanswered domains were left out, and the overall read LOW with exit 0. Every in-scope
  domain is now listed, a blank makes it INCOMPLETE, and `--rollup` exits 1. GRADE no longer
  starts from High when 0.1 is blank or prints a certainty for a partial table;
  Newcastle-Ottawa names its unanswered items.
- **Polarity.** QUADAS-2 1.2 and 1.3, ROBIS 4.6 and 3C, ROBINS-E 2.3 and 6.2, and ROBINS-I 6.3
  and 1.x 4.4 (co-interventions balanced, now 4.3) were tagged reverse although *Yes* is the
  good answer; ROBINS-E 5.2 and ROBINS-I 5.2 were not, although *Yes* is the problem. An ideal study came out high risk. ROBINS-I 1.1 forced
  Serious on every observational study; it, 2.1–2.4, 3.2, 4.1, 4.3–4.5 and 5.1–5.3 are now
  *middle* (the 2016 tool's Tables B–C rate them Moderate unless a later question fails), 1.3
  routes. The reason text names the answer actually given ("'Yes' … (reverse-worded)").
- **QUIPS *Partly*** counted as no problem; it is the middle level now.
- **Newcastle-Ottawa** gave a star for *Partial yes* on one-star items, and accepted *PY*; only
  the comparability items earn a partial star, and *PY* is rejected.
- **Per-instrument shorthands (H4).** A global table read *PY* as *Probably yes* everywhere, so
  an AMSTAR 2 critical item marked PY counted as a full Yes. Each reference file now declares
  its own shorthands.
- **GRADE (H3).** Publication bias *Suspected* and *Strongly suspected* both counted as no
  downgrade. *Strongly suspected* is −1; *Suspected* and the new *Could not be assessed* are
  UNRESOLVED until decided. *Very large* (+2) is a new answer. Each domain accepts only its own
  answers.
- **AMSTAR 2** counted *N/A* (no meta-analysis) on 11, 12 and 15 as a flaw — a narrative review
  rated Critically low. It is now neither flaw nor weakness, and N/A elsewhere is rejected.
- **Reading answers.** A blank AMSTAR 2 skeleton verified 1/16 (item 16 read from the header
  line); prose answers were read out of "If Y/PY to 2.4" clauses. Answers come from the Answer
  column, and prose lines count only when they start with the item id.
- **checklist.py (H1, H2).** TRIPOD+AI's status was searched line-wide, so item 11's title
  ("How missing data …") answered it: a blank template verified 1/52. PROBAST+AI's passes
  answered each other (development only gave 32/34) and an evidence note's "no" counted. The
  status/answer cell is read, per pass.
- **Scopes.** An unknown `--scope` silently selected nothing (`--scope cohorts` verified an empty
  file "0/0 complete"); it is now a usage error. RoB 2 `--scope adherence` printed no domain 2
  at all; it now has the published six questions for the effect of adhering, and `all` means
  `assignment` for RoB 2, because the two variants are alternatives.
- **Smaller.** ROBIS phase 3 was merged into domain 3; QUADAS-2 had one applicability slot for
  three domains (RoB 2 had one it should not have); the TRIPOD+AI redirect told you to run
  `--skeleton probast`; "non-randomised study" was routed to RoB 2.

**Why 2.0.0 and not 1.1.0.** Two instruments are renumbered to their published form. ROBINS-I
follows the 2016 tool's Table A — 34 items, with 1.x's 4.3–4.6, 5.2 and 5.3 moved or split and
5.5 and 6.4 added — and QUIPS the 31 published prompting items 1a–6d instead of 1.x's own
1.1–6.5. In a 1.x ROBINS-I file the same id can name a *different* question, so no alias can
make old files read correctly; that is a breaking change for stored appraisals. The engine
refuses to score a file it recognises as 1.x numbering (exit 1, with the reason) and
`--migrate` converts it explicitly — every carried answer is tagged with its 1.x id in the
evidence column, and the new and split questions are left blank for `--verify` to name. The
other breaking change is deliberate: `--rollup` exits 1 whenever its verdict is not final, and
`--verify` rejects answers an item does not offer. For the tools whose ids did not change, a
1.x file still verifies and rolls up as it is — with the corrected tags and the stricter
answer checks.

