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
problem; gateways (*router*) only open the next question — ROBINS-I's 1.2–1.3, 2.1–2.2 and
5.1–5.3. Treating every "No" as bad rated a well-conducted study as high risk. *Middle* marks
answers that rule out the low tier but cannot by themselves reach the top one — ROBINS-I's "is
there potential for confounding?" is Yes for nearly every observational study — and *joint*
marks answers that count only together (ROBINS-I 6.1 with 6.2, 5.4 with 5.5). For ROBINS-I and
ROBINS-E the rollup follows each question's "If … to …" routing condition, read from the
question text.

**Answer words are per instrument.** Each reference file declares its vocabulary, its
shorthands and any per-item restriction: *PY* is *Probably yes* in RoB 2 but *Partial yes* in
AMSTAR 2, the Newcastle-Ottawa scale gives a partial star only for comparability, ROBINS-E's
graded *Weak no* / *Strong no* exists only on its first confounding question, and N/A is
accepted only where the instrument offers it (the conditional questions of RoB 2, ROBINS-I and
ROBINS-E, QUADAS-2 2.2, QUIPS 3f and 5e; none in ROBIS or the Newcastle-Ottawa scale).

**Published algorithms are reproduced where they exist** — RoB 2's per-domain algorithm (2019
guidance; the rollup prints the path it took), AMSTAR 2's critical-flaw table, the
Newcastle-Ottawa star count, GRADE's start-and-adjust, ROBIS's overall as the phase-3
judgement — and **not faked where they do not**. For the ROBINS family, QUADAS-2, QUIPS and
JBI the rollup reports what the recorded answers force and names the questions that forced
it, then says explicitly that this is not the official flowchart. QUADAS-2's applicability
judgements, which no signalling question feeds, are read and required per domain 1–3.

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
adds one test per defect listed below; each of them fails against 1.0.0, the
methodology-review block fails against the first 2.0.0 commit (60e290b), the ROBINS-I
gateway block against 1b2c906, and the engine-agreement block against 84363b0.

## Provenance

Every reference file ends with a note naming the source paper and stating what is verbatim,
what is paraphrased and what is this repository's own recommendation. Item texts are working
paraphrases in each tool's vocabulary — use the published wording when an assessment appears
in a manuscript, and name the tool version in the methods section.

## Changes

### 2.0.0 — agreement with the metaANAL engine (same release)

Every answer combination of every domain was enumerated — RoB 2 (both variants), ROBINS-I (both),
ROBINS-E, QUADAS-2, QUIPS, NOS (per form), GRADE and AMSTAR 2 — and this rollup, run on the
generated Markdown records, was compared with the metaANAL engine's `appraisal.check`. Two
disagreement classes were this side's; each fix has regression tests (`[agreement …]` in
`scripts/selftest.py`, 230 → 254 assertions; 10 of the new ones fail against 84363b0):

- **RoB 2 3.2 offered *No information*.** The 2019 template has no NI option at 3.2 (evidence
  that the result is not biased is shown or it is not); `item_answers` now restricts it, so
  `--verify` rejects it and domain 3 is INCOMPLETE instead of a verdict.
- **No information at a gateway, settled later.** NI at a gateway kept the domain at the middle
  tier even when another answer opened the question that gateway feeds and that question was
  answered — ROBINS-E 5.1 NI with 5.2 *Yes* and 5.3 *Yes*, ROBINS-I 5.1 NI with 5.2 *Yes* and
  5.4 or 5.5 *Yes* rolled up SOME CONCERNS; they are Low now, as RoB 2's 3.1 NI with 3.2 *Yes*
  is. A gateway whose dependent questions are not reached still leaves the domain unclear.

The selftest also checks every RoB 2 domain of both variants, for every answer each question
offers, against an independent implementation written from the 2019 criteria table (as
reproduced in PMC8191126, Table 2): no difference.

What still differs from the engine is deliberate on both sides and documented there (the
metaANAL bridge prints a note for each): N/A at a question the routing reaches is INCOMPLETE
here and counted as *No information* by the engine; where the ROBINS-I/-E answers do not decide
between the middle and the top tier (No information at a correction question such as ROBINS-I
2.5 or ROBINS-E 3.3/4.2/5.3, or ROBINS-I 5.4 and 5.5 both *No*) this rollup reports the tier the
answers force and the engine's conservative rule the stricter one; a blank question the routing
does not reach is INCOMPLETE here; and AMSTAR 2 here is the engine's 'weakness' convention
(*Partial yes* is a weakness on every item that offers it), while the engine's default is 'meets'
and it reports both. GRADE agrees on every combination of the shared vocabulary; *N/A* on the
upgrading domains and *Could not be assessed* for publication bias exist only here.

### 2.0.0 — ROBINS-I 2.1 is a gateway; ROBINS-E, QUADAS-2 and QUIPS review (same release)

Decision: ROBINS-I 2.1 routes, it does not rate. Selection based on characteristics observed
after the start of intervention opens 2.2 and 2.3; the bias in domain 2 is judged from 2.2–2.3
(selection related to both intervention and outcome) and, for the timing of follow-up against
the start of intervention, from 2.4–2.5 — the logic of the 2016 tool's Tables A–C
(PMC5062054). The rest of the methodology review, skipped in the previous commit, was run on
constructed records; every fix has a regression test (`[ROBINS-I 2.1 gateway …]` and the blocks
after it in `scripts/selftest.py`, 163 → 230 assertions; run against commit 1b2c906, 40 of the
67 new ones fail). Random records give identical rollups for RoB 2, AMSTAR 2, GRADE, NOS, ROBIS
and JBI apart from the reworded closing note.

- **ROBINS-I domain 2.** 2.1 *Yes* with 2.2 *No* was SOME CONCERNS at exit 0; it is Low-capable
  now. 2.1 and 2.2 are gateways (`router`), 2.3 and 2.4 are middle, 2.5 decides Serious. *No
  information* at a gateway leaves the domain unclear.
- **Routing is followed (ROBINS-I, ROBINS-E).** Conditions are parsed from the question text.
  A stray answer at a question the routing skips was scored (2.1 *No* with 2.5 *No* was
  Serious at exit 0); it is listed and ignored now. N/A at a reached question (1.4 after 1.2
  *No*) was skipped; it is INCOMPLETE now, and `--verify` names it — for RoB 2 as well, whose
  rollup already said INCOMPLETE there. N/A at an unconditional question (an all-N/A record)
  is rejected (`not_applicable`).
- **ROBINS-I domains 5 and 6 (Table C).** Missing data with 5.4 or 5.5 *Yes* is Low (it was
  Moderate, or Serious with one of them *No*); 5.1–5.3 are gateways and 5.4/5.5 a `joint`
  pair (both *No*: at least Moderate, Serious left to a stated judgement). 6.1 *Yes* with
  6.2 *No* (or the reverse) was Serious; 6.1/6.2 are a `joint` pair — Serious only together.
- **ROBINS-E (PMC11098530).** The graded *Weak no* / *Strong no* of its first confounding
  question was rejected as unrecognised; it is accepted there (middle / top tier) and only
  there (meta `restricted_answers`). A correction recorded at 3.3 or 4.2 was overridden by a
  top-tier flag at 3.1/3.2/4.1, and 5.3 *Yes* (no bias from missing data) was High; those
  questions are middle or gateways now. Domain 3 carries its full name (study *or analysis*);
  a Low domain 1 prints the tool's standing caveat about uncontrolled confounding.
- **QUADAS-2.** A record with no applicability judgement verified complete; `--verify` and
  `--rollup` read the three per-domain judgements and exit 1 while one is missing. N/A is
  offered only at 2.2 (no threshold); an all-N/A record rolled up Low.
- **QUIPS.** N/A only at 3f and 5e (nothing missing / nothing imputed); an all-N/A record
  rolled up Low. The overall line states that QUIPS publishes no combination rule.
- **`--migrate` (ROBINS-I).** With `--scope assignment` the 1.x adhering-analysis answer (4.3,
  now 4.6) and 4.4–4.6 were reported as "moved" and silently dropped; with `--scope adherence`
  4.1–4.2 were counted as carried. Answers whose question the chosen variant does not ask are
  now listed as not carried.

Checked and unchanged: ROBINS-I ids, routing conditions and counts (34; 30 assignment, 32
adherence); QUADAS-2's 3/2/2/4 signalling questions, all Yes-is-good; QUIPS's 31 prompting
items 1a–6d, four-level scale (*Partial* / *Unsure* accepted as shorthands) and *Partly* as
the middle level; the QUIPS legacy map.

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
  Serious on every observational study; it, 2.3, 2.4, 3.2, 4.1 and 4.3–4.5 are now *middle*
  (the 2016 tool's Tables B–C rate them Moderate unless a later question fails), and 1.3
  routes. (This entry first tagged 2.1–2.2 and 5.1–5.3 *middle* as well; they are gateways —
  see the entry above.) The reason text names the answer actually given ("'Yes' …
  (reverse-worded)").
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

