# Presubmit

**Catch the common manuscript submission mistakes before a journal does.**

Inspired by the "avoidable mistakes" every journal editorial office sees —
duplicate references, citations that point nowhere, a missing conflict-of-interest
statement, an over-long abstract, a forgotten Methods section. Presubmit scans a
manuscript and reports every automatically-detectable problem, ranked by
severity, with a fix hint for each.

Deterministic and offline: **no language model, no spell dictionary**, so it
never false-positives on medical terminology.

## What it checks

| category | catches |
|----------|---------|
| **structure** | missing IMRaD / case-report sections (profile-driven) |
| **authors** | no corresponding email, no affiliation, no ORCID in the author block |
| **abstract** | missing abstract, over/under length, wrong keyword count |
| **references** | duplicates (by DOI *and* by near-identical text), missing years, malformed DOIs, incomplete entries, in-text `[n]` citations with no matching reference, references never cited |
| **ethics** | missing required disclosures — conflict of interest, funding, human subjects, informed consent (profile-driven) |
| **format** | repeated words, double spaces, space before punctuation, missing space after a sentence, mixed quote/dash styles |

## Commands

| command | scope |
|---------|-------|
| `/ps:check` | full scan (all categories) |
| `/ps:refs` | references + in-text citation cross-check |
| `/ps:ethics` | disclosure / ethics statements |
| `/ps:format` | language & typography |
| `/ps:journals` | list built-in journal profiles |

The bundled **presubmit skill** auto-triggers on "check my paper before
submission", "find mistakes", "check my references", and similar (English and
Hungarian).

## Usage

```bash
python3 scripts/pc.py check manuscript.docx --journal cureus --json report.json
```

Reads `.docx`, `.pdf`, `.tex`, `.txt`, `.md` (and `.doc/.odt/.rtf` via
doctotext). `.docx` gives the best structure detection (heading styles are
preserved). Exits non-zero if any ERROR is found, so it can gate a pipeline.

### Severity

- **ERROR** — commonly triggers desk rejection.
- **WARN** — should fix before submitting.
- **INFO** — worth a glance, not blocking.

A clean report means "no *automatically detectable* problems" — not a guarantee
of acceptance.

## Journal profiles

Profiles are small JSON files in `profiles/` (abstract/keyword limits, required
sections, required disclosures). **Cureus** and a **generic IMRaD** profile ship
built in. Adding a journal is a data change, not a code change.

## Fits with the rest of the toolkit

- Grammar / register / native-English editing → **academic-editor** skill.
- Tracking the submission and reviewer points afterwards → **science-monitor**.
- Slow responses to editorial queries — the one common mistake Presubmit can't
  see in a file — is exactly what science-monitor's inbox tracking handles.

## Self-test

```bash
python3 scripts/pc.py selftest
```

Plants ten known mistakes and asserts every one is caught, and that a clean
manuscript passes.

---

Part of the **szk-plugins** marketplace · MIT · Dr. Szili Károly
