---
name: presubmit
description: Scan a manuscript for the common submission mistakes that get papers desk-rejected — before a journal sees them. Checks missing IMRaD/case-report sections, incomplete author info (no corresponding email, no affiliation, no ORCID), abstract length and keyword count, reference problems (duplicates by DOI or text, missing years, malformed DOIs, in-text citations with no matching reference, references never cited), missing ethics/disclosure statements (conflict of interest, funding, human subjects, informed consent), and mechanical language/typography errors. Use whenever the user is about to submit or is preparing a manuscript, asks to "check my paper before submission", "find mistakes", "am I ready to submit", "check my references", "did I forget any disclosures", mentions Cureus or another journal's submission requirements, or wants a pre-submission / submission-readiness review. Hungarian triggers — beadás előtti ellenőrzés, kézirat hibakeresés, hivatkozás-ellenőrzés, etikai nyilatkozatok, submission előtti review, mire figyeljek beadás előtt.
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

- `check` — everything (structure, authors, abstract, references, ethics, format)
- `refs` / `ethics` / `format` / `authors` / `abstract` — one category only
- `journals` — list built-in journal profiles (Cureus + generic)

Reads `.docx`, `.pdf`, `.tex`, `.txt`, `.md` (and `.doc/.odt/.rtf` via
doctotext). `.docx` gives the best structure detection because heading styles
are preserved.

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
