---
description: Hivatkozásjegyzék ellenőrzése Crossref és Europe PMC ellen
allowed-tools: Bash, Read, AskUserQuestion
---
Resolve every DOI in a manuscript's reference list and compare the first author
and year against the registries.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" refaudit SLUG
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" refaudit --file path/to/manuscript.md
```

It reads Vancouver-style numbered entries ending in `doi: 10.…`, so a `.docx`
has to be converted first — use the **doc-tools** skill (`doctotext`) and pass
the text file with `--file`.

## A kimenet három szintje

- **✗ hiba** — the DOI does not resolve, the year is off by more than a year, or
  the first author is a different person from the one MEDLINE lists. Report
  these with the exact replacement text.
- **? döntést kér** — see below. **Never resolve these yourself.**

  A year that differs by one is *not* automatically a question. The tool first
  asks Europe PMC: if the manuscript's year equals MEDLINE's `pubYear` while
  Crossref reports the next year, that is a volume-year vs actual-publication
  gap — Frontiers and others assign an article to a volume and put it online in
  January of the following year — and it becomes a note, not a question. It
  stays a question only when MEDLINE does not settle it.
- **· megjegyzés** — Crossref and Europe PMC disagree while the manuscript
  matches MEDLINE, and the two names are clearly different people or forms.
  Crossref carries the publisher's deposit, which is sometimes partial (one
  journal deposits only the last author). A Vancouver list is checked against
  MEDLINE, so the manuscript is right. Mention it; change nothing.

## ? A one- or two-character difference is ALWAYS a question, never a decision

When the tool marks a reference `?`, you **must** put it to the user before any
edit. This is not a preference — it is a hard rule, and it exists because
acting on one alone here turned a correct author name into an incorrect one:
`Sachedina` looked exactly like a typo for the registered `Sachedin`, and was
in fact the MEDLINE spelling, i.e. the correct one.

A difference of one or two characters — a doubled letter, a missing vowel, an
accent, a year off by one — is exactly the case where "obviously a typo" and
"genuine registry variance" are indistinguishable from the outside. The cost of
guessing wrong is a wrong name in a published reference list.

So, per flagged item:

1. Show both spellings side by side, with the source of each (manuscript vs
   Crossref vs Europe PMC/MEDLINE) and the DOI or PMID.
2. Ask with **AskUserQuestion** — one question per item, or one question with
   the items as options when there are several. Offer at least: keep the
   manuscript's form, take the registry's form, and check the publisher's PDF.
3. Only then edit, and only what was chosen.

Do not batch these into a summary and proceed. Do not pick "the more likely
one". Do not treat a Hungarian accent difference (`Szilagyi` / `Szilágyi`) as
obviously the accented one — MEDLINE strips accents, the manuscript may not,
and which belongs in the reference list depends on the journal's style.

If the user is away and cannot answer, leave every `?` item untouched, say
explicitly which references are unresolved, and stop. An unanswered question is
a better outcome than a silent wrong edit.

## Jelentés

Errors first with their reference numbers and exact replacement text, then the
questions, then the notes. Never edit the manuscript without showing the user
the change first.
