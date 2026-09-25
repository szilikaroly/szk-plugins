---
name: presubmit
description: Scan a manuscript for the common submission mistakes that get papers desk-rejected or sent back — before a journal sees them. Checks missing IMRaD/case-report sections, incomplete author info (no corresponding email, no affiliation, no ORCID), abstract length and keyword count, reference problems (duplicates by DOI or text, missing years, malformed DOIs, in-text citations with no matching reference, references never cited), missing ethics/disclosure statements, and mechanical language/typography errors. Also catches what editors flag by hand: placeholders and unresolved tracked changes or comments left in the submitted .docx, a declared word count over the format's limit, more references than the format allows, effect estimates reported without a confidence interval, trials named only by acronym with no describing clause, the same study described twice, and the authors' own ongoing study promoted in the conclusion. Optionally (--online) asks PubMed whether any cited paper has been corrected or retracted. Use whenever the user is about to submit or is preparing a manuscript or a revision, asks to "check my paper before submission", "find mistakes", "am I ready to submit", "check my references", "did I forget any disclosures", "is anything left in the file", mentions a word or reference limit, mentions Cureus, Annals or another journal's submission requirements, or wants a pre-submission / submission-readiness review. Hungarian triggers — beadás előtti ellenőrzés, kézirat hibakeresés, hivatkozás-ellenőrzés, etikai nyilatkozatok, submission előtti review, mire figyeljek beadás előtt, szószám ellenőrzés, benne maradt korrektúra, visszavont hivatkozás.
---

# Presubmit

Catch the mistakes a journal's editorial office catches — reference duplicates,
citations that point nowhere, a missing conflict-of-interest statement, an
over-long abstract — while there is still time to fix them. Deterministic and
offline: no language model, no spell dictionary, so it never false-positives on
medical terminology.

## How to run

One CLI, subcommands:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" check MANUSCRIPT [--journal NAME] [--json OUT.json]
```

- `check` — everything (structure, authors, abstract, references, ethics,
  format, submission, claims)
- `refs` / `ethics` / `format` / `authors` / `abstract` / `submission` /
  `claims` — one category only
- `journals` — list built-in journal profiles (generic, Cureus, Annals)
- `--online` on `check` or `refs` — the one networked check: does any cited
  paper carry an erratum, a retraction or an expression of concern? Off by
  default. It resolves AMA-style references that print no DOI through
  PubMed's citation matcher, so it works on the reference styles that need
  it most. If it cannot run it says so rather than reporting a clean result.

Reads `.docx`, `.pdf`, `.tex`, `.txt`, `.md` (and `.doc/.odt/.rtf` via
doctotext). `.docx` gives the best structure detection because heading styles
are preserved.

## Two categories worth knowing about

`submission` and `claims` were reverse-engineered from a real editorial round at
a high-impact general medical journal. Every rule in them corresponds to
something an editor asked for by hand:

- A `.docx` carrying tracked changes or comments is an ERROR: the journal opens
  the uploaded file, not the view the author was working in, and python-docx
  would quietly accept the revisions. Presubmit reads the raw package.
- A declared word count is checked against the format's limit as plain
  arithmetic, which catches both an over-long manuscript and an
  order-of-magnitude typo on the title page.
- Effect estimates are checked **per parenthetical**, not per sentence — the
  failure editors actually flag is a headline estimate carrying its 95% CI next
  to subgroup values in the same sentence that do not.
- Trial acronyms are flagged only when the token is clearly introduced as a
  study and no describing clause follows. Gene symbols, degrees, approval
  numbers and self-defined abbreviations are excluded, so a clean paper stays
  quiet.

When both fire on a short format, say so together: adding descriptions and
confidence intervals costs words, and the word ceiling is fixed. That trade-off
is the substance of the revision, not a detail.

## What each severity means

- **ERROR** — commonly triggers desk rejection: duplicate references, a citation
  with no matching reference, a missing *required* disclosure, no abstract.
- **WARN** — should fix before submitting: missing section, no corresponding
  email, over-long abstract, uncited references, missing recommended statements.
- **INFO** — worth a glance, not blocking.

The CLI exits non-zero if any ERROR is present, so it can gate a submission
pipeline.

## Reporting to the user

Lead with the **VERDICT** line and the error/warn/info totals, then walk the
findings grouped by category, ERRORs first. Always add the honest caveat: a
clean report means "no *automatically detectable* problems", not a guarantee of
acceptance.

## Hand-offs

- Real grammar / register / native-English editing → the **academic-editor**
  skill (this plugin only catches mechanical typography).
- Tracking the submission, cover letter and reviewer points afterwards →
  **science-monitor**.
- The one common mistake this plugin can NOT check — *slow responses to
  editorial queries* — is exactly what science-monitor's inbox tracking is for.

## Journal profiles

Profiles live in `profiles/*.json` (abstract/keyword limits, required sections,
required disclosures). To support a new journal, ask the user for the numbers
from its author guide and add a small JSON file — no code changes needed.

## Self-test

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" selftest` plants ten known
mistakes and asserts every one is caught, and that a clean manuscript passes.
