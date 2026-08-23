# Academic Editor

Premium-level line editing for scientific English, delivered the way an editing service
delivers it: a `.docx` with real Word tracked changes and anchored editor queries, plus a
clean accepted copy.

## What makes the rules trustworthy

They were derived from a real AJE Senior Editor's Premium edit — 61 changed paragraphs, 979
insertions, 896 deletions, 11 comments — and every rule in `skills/academic-editor/references/` cites the operation
that produced it. Where the sample is internally inconsistent (`p` vs `P`, `±` spacing,
scale-name capitalization), the references say so instead of inventing a rule; the operative
principle there is local consistency plus a query.

## The four references

| File | Covers |
|---|---|
| `language-mechanics.md` | articles, agreement, tense, verb precision, prepositions, like-with-like comparisons, modifiers, parallelism, register, concision, claim strength, spelling |
| `structure-and-flow.md` | splitting and joining, colon/semicolon/comma, information order, connectives, paragraph architecture by IMRaD section, cohesion |
| `reporting-conventions.md` | numerals, time points, units and operators, statistics, tables and figures, abbreviations, headings, front matter |
| `editor-queries.md` | the prohibitions, when to query rather than edit, query templates |

## House style is measured, not assumed

```bash
scripts/housestyle.py --journal "Frontiers in Endocrinology" --n 12 --years 3 \
    --out profile.json --md profile.md
scripts/housestyle.py --profile profile.json --compare manuscript.docx
```

Sentence length and long-sentence share by section, hedge density, first-person density,
passive density, `p` vs `P`, `±` spacing, US/UK spelling, in-text citation form, heading
case, figure-caption length, structured-abstract share and its labels — all counted from
that journal's own recent Open Access papers.

Measured, not guessed, because the difference is checkable. *Nutrients* comes back US
spelling with numeric citations; *BJOG* comes back UK spelling. A journal's Methods run
around 28/1000 words passive while its Discussion runs around 11 — telling an author to
"reduce the passive voice" without knowing which section they are in is advice that damages
the Methods.

## The full pass

```bash
S=scripts
python3 "$S/housestyle.py"    --journal "<J>" --n 12 --out profile.json --md profile.md
python3 "$S/housestyle.py"    --profile profile.json --compare manuscript.docx
python3 "$S/manuscript_check.py" manuscript.docx --json check.json
#  ... edit, recording {find, replace, comment} triples into edits.json ...
python3 "$S/docx_tracked_edit.py"    manuscript.docx edits.json --dry-run
python3 "$S/docx_tracked_edit.py"    manuscript.docx edits.json -o ms_edited.docx
python3 "$S/docx_accept_changes.py"  ms_edited.docx -o ms_clean.docx
```

## The line the editor never crosses

Numbers, statistics, citations, the direction of a finding and the author's claims are
invariant. Ambiguity gets a query, not a guess. The sharpest demonstration in the corpus:
the editor corrected `SPSS, Inc` to `SPSS, Inc.` and still refused to write `USA` after
`Chicago, IL`, asking for it in a comment instead.

## Self test

```bash
python3 scripts/selftest.py
```

Offline. Asserts the checker's findings on a manuscript with planted defects, and
round-trips the two `.docx` writers on a paragraph whose target phrase is
deliberately split across three differently formatted runs — which is what Word
actually produces. `--reject` must reproduce the input text exactly and
`--accept` the intended output; anything less means an edit silently failed to
apply, which is invisible in the delivered file.

## Dependencies

`lxml` for the two `.docx` writers, `python-docx` for reading `.docx` in the checker.
`housestyle.py` is stdlib-only.
