---
description: Clean the AI-draft tells out of a manuscript section while keeping every number, citation and the author's voice — then prove nothing was lost
allowed-tools: Bash, Read, Write, AskUserQuestion
---
Run an academic-humanizer pass on: $ARGUMENTS

The rules are in `${CLAUDE_PLUGIN_ROOT}/skills/presubmit/references/academic-humanizer.md`
(adapted from academic-humanizer v0.3.3, MIT — see `licenses/`). Read that
file before rewriting anything. This is an editing aid for clarity and voice;
it is not for evading AI-use detection, and it never removes the obligation
to disclose AI assistance.

## 1. Settle the scope — ask, do not assume

Use AskUserQuestion for whatever the arguments did not already say:

- **which part** — whole body, or named sections (abstract, introduction,
  discussion are where the tells concentrate; Methods and Results are usually
  better left alone);
- **document type** — research paper / review, or funding proposal (Layer 6
  applies only to proposals);
- **voice sample** — a path to one or two of the author's own accepted papers,
  or none;
- **target journal or funder**, if known.

## 2. Measure first (deterministic)

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" style MANUSCRIPT --json STYLE.json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" text MANUSCRIPT [--section NAME ...] > HUMANIZE_original.txt
```

`style` is advisory and English-only; on a Hungarian manuscript it says so and
stops — offer the hu-academic-style or academic-editor skill instead. The
`text` output is the exact original the rewrite will be checked against; use
the section names `style`/`check` report.

## 3. Audit — and let the author decide

List, per section: each `style` finding with its location, plus what needs
reading for meaning (Layers 3–5: over-claimed verbs on observational data,
unbacked claims, elegant variation, contribution clichés). For each empirical
claim give its evidence status: carried / pointer exists elsewhere in the text
/ **no evidence in the manuscript**.

Then ask with AskUserQuestion which categories to apply (all recommended /
choose categories / audit only, no rewrite). Do not rewrite before the answer.

## 4. Rewrite

Apply the reference file's layers to the chosen text only. Hard rules:

- same structure and coverage: N paragraphs in, N paragraphs out;
- no number, unit, equation, citation marker, cite key, DOI or
  Table/Figure reference is added, dropped, rounded or moved to another claim;
- evidence pointers only if they already exist in the manuscript; otherwise
  insert `⟦AUTHOR: …⟧` and list it in the report (presubmit's `submission`
  check treats it as a placeholder until the author answers);
- evidence-tied hedging stays; never strengthen a verb;
- em-dashes are recast in English text only; en-dash ranges stay.

Write the result to `HUMANIZE_rewrite.md` (the rewritten text only, same
section headings), never over the manuscript itself.

## 5. Prove nothing was lost

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" invariants HUMANIZE_original.txt HUMANIZE_rewrite.md --json HUMANIZE_invariants.json
```

Exit status 1 means the rewrite lost or invented something. Fix the rewrite
and run it again until it reports PRESERVED. Never present a rewrite as final
while this fails; if a difference is intended (e.g. the author asked for a
number to be corrected), name it explicitly in the report.

Then re-run `style` on `HUMANIZE_rewrite.md` and give the before/after counts.

## 6. Report

Write `HUMANIZE_report.md`: the change log by pattern type (use the finding
codes), claims softened, author queries inserted, voice/venue notes, the
before/after `style` counts, and the `invariants` verdict verbatim. In chat,
lead with the invariants verdict and the counts, then the author queries.

For a tracked-changes `.docx` of the accepted rewrite, hand off to the
academic-editor skill; for the full readiness verdict afterwards, run
`/presubmit:check`.
