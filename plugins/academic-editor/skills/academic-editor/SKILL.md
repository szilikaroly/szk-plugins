---
name: academic-editor
description: Edit scientific manuscripts into academic or high-academic English at professional editing-service standard (American Journal Experts "Premium Editing" level), matched to the TARGET JOURNAL's measured house style, and deliver the result the way an editing service does — a .docx with real Word tracked changes plus anchored editor queries, and a clean accepted version alongside it. Rules were reverse-engineered from a real AJE Senior Editor's ~1900 tracked operations and adversarially verified. Use whenever a manuscript, abstract, cover letter, grant text, thesis chapter or response-to-reviewers needs its English raised, polished, proofread, or brought to native academic register — including "make this publication-ready", "fix my English", "the reviewers complained about the language", "elevate the register", "line edit this", "make it sound like this journal", or a non-native draft that needs to read as though written by a native academic. Hungarian triggers — nyelvi lektorálás, angol szöveg javítása, akadémiai angol, szövegellenőrzés, stilizálás, kézirat csiszolása, korrektúra, nyelvhelyesség, publikálásra kész angol, folyóirat stílusához igazítás.
---

# Academic Editor

A line editor for scientific English at professional editing-service standard. Not a grammar
checker: it does what a Senior Editor does on a paid Premium edit — raises register,
re-architects sentences, enforces reporting conventions, matches the target journal's
measured practice, and *queries the author* wherever meaning is at stake instead of guessing.

The rules are not invented. They were derived from a real AJE Premium Editing sample (a
sleep-medicine manuscript: 61 changed paragraphs, 979 insertions, 896 deletions, 11 editor
comments), then each derived rule was checked back against the corpus and either confirmed,
narrowed, or dropped. Every rule in the reference files cites the operation that produced it.

## The one rule that outranks the others

**You edit language. You never edit science.** Numbers, statistics, results, the direction of
a finding, citations, and the author's claims are not yours to change. When a sentence is
ambiguous, the professional move is a query, not a guess. `references/editor-queries.md`
states the boundary in full — read it before your first substantive edit on any manuscript.

## Workflow

### 1. Intake

Establish three things before editing a word:

| Question | Why it changes the edit |
|---|---|
| Target journal? | Governs the house-style profile in step 2, reference style, US vs. UK spelling, word limits |
| Editing intensity? | Light proofread / standard copyedit / premium substantive line edit — see `references/editor-queries.md` |
| Word limit in force? | Determines whether concision edits are cosmetic or load-bearing |

If the user does not say, default to **premium substantive line edit** and US spelling, ask
nothing, and state the assumptions in the final report so they can be corrected.

Extract the text with the `doc-tools` skill
(`doctotext manuscript.docx -f md --tables --comments`). If the manuscript already carries
tracked changes or reviewer comments, read those first: they tell you what is contested and
must not be quietly overwritten — and the tracked-changes writer will refuse to touch text
inside an existing revision.

### 2. Measure the target journal — before reading for style

```bash
S="${CLAUDE_PLUGIN_ROOT}/scripts"
python3 "$S/housestyle.py" --journal "<journal name>" --n 12 --years 3 \
        --out journal-profile.json --md journal-profile.md
python3 "$S/housestyle.py" --profile journal-profile.json --compare manuscript.docx
```

This measures that journal's own recent Open Access papers: sentence length and long-sentence
share by IMRaD section, hedge density, first-person density, passive density, `p` vs `P`,
`±` spacing, US/UK spelling, in-text citation form, heading case, figure-caption length,
whether abstracts are structured and with which labels.

Use it as follows, and no further:

- **The two numbers that drive the edit are mean sentence length and hedge density.** If the
  manuscript's Discussion runs at 38 words per sentence and the journal's at 24, splitting
  sentences is *fit*, not taste — and say so to the author with both numbers.
- **First person is the most revealing.** In a journal measuring ~0, every "we found" stands
  out; in one measuring 8/1000, deleting them is what makes the text read foreign.
- **Apply a mechanical convention only where the sample is unambiguous (≥90%).** Where the
  profile says "vegyes", the journal is not consistent either, so there is nothing to match —
  ask the author.
- If the journal has too little Open Access full text (`n_papers_sampled` under 3), the tool
  says so. Then say so too, and edit without a profile. Do not substitute an impression of
  the journal for a measurement.

The profile is **not** correctness. Language first, fit second.

### 3. Deterministic pass

```bash
python3 "$S/manuscript_check.py" manuscript.docx --json check.json
```

Reports word counts by section, abbreviations defined-but-unused and used-before-defined,
sentence-length outliers, passive density by section, `p`/`P`, `±` and operator-spacing
splits, missing unit spaces, run-together ordinals, lowercase `table 2`/`figure 3`, US/UK
spelling mixes, and the register markers the reference edit removed on sight. Fix these
mechanically; they are not judgement calls.

The three consistency findings (`p`/`P`, `±`, operator spacing) are deliberately reported as
*splits*, not verdicts: the reference edit was internally inconsistent on all three, and its
operative rule was local consistency plus a query. If you do unify one globally, **tell the
author you did** — in tracked changes a silent global case change to a statistical symbol
looks exactly like an edit to a result.

### 4. Edit

Work section by section in document order — Abstract, Introduction, Methods, Results,
Discussion — because tense and claim-strength conventions differ by section, and editing out
of order produces inconsistency.

Consult, in this order of frequency:

- `references/language-mechanics.md` — articles, number and agreement, tense, verb precision,
  prepositions, comparisons between like categories, modifiers, parallelism, register,
  concision, claim strength, spelling. The core line-editing reference. Its §13 lists the
  three places where the reference edit was inconsistent, so you do not manufacture a rule
  from them.
- `references/structure-and-flow.md` — sentence splitting and joining, colon/semicolon/comma
  decisions, information order, connectives and what each signals, paragraph architecture by
  IMRaD section, cohesion.
- `references/reporting-conventions.md` — numerals, study time points, units and operators,
  statistics, tables and figures, abbreviations, headings and front matter.
- `references/editor-queries.md` — the prohibitions, when to query rather than edit, and the
  query templates.

Record every edit as a `{find, replace, comment}` triple **as you go**, into `edits.json`.
Do not batch this at the end; reconstructing edits from memory is how spurious changes get
introduced. `find` must match the manuscript byte for byte — curly quotes, en dashes and
double spaces included.

### 5. Query

Every substantially restructured sentence gets a meaning-maintenance query. Every genuine
ambiguity gets an A/B query offering the author explicit options. Every global change applied
across a passage gets a single note explaining it. Templates and voice are in
`references/editor-queries.md`.

Queries are not padding — an edit that needed a query and did not get one is a worse failure
than a missed comma. In the reference sample, 11 comments accompanied ~1900 operations: they
are scarce because each one marks a decision only the author can ratify.

### 6. Deliver

```bash
python3 "$S/docx_tracked_edit.py" manuscript.docx edits.json -o manuscript_edited.docx \
        --author "Academic Editor" --initials AE
python3 "$S/docx_accept_changes.py" manuscript_edited.docx -o manuscript_clean.docx
python3 "$S/manuscript_check.py" manuscript_clean.docx --only counts
```

Run `docx_tracked_edit.py --dry-run` first: it reports which `find` strings did not match, and
a non-matching edit is silently absent from the delivered file otherwise.

Hand back both files plus a short report:

1. what changed at the level of **patterns**, not a list of commas — "articles added before
   specified nouns (14×)", "comparisons repaired where a quantity was being compared with a
   disease (3×)";
2. the **queries raised**, each with why the author has to answer it;
3. the **new word count** from the clean file;
4. the **house-style fit** — the two or three rows from `--compare` that still differ, with
   both numbers;
5. anything you could not resolve without the author.

Never recalculate a word count stated in the manuscript's own front matter. You cannot know
it after the author accepts a subset of the changes; query for it, exactly as the reference
edit did.

## Scope notes

Works on plain text, Markdown and LaTeX too — the tracked-changes step simply does not apply,
so deliver the edited text with queries as inline `[EDITOR: ...]` notes plus a separate query
list.

`housestyle.py` needs the journal's Open Access full texts, so it works for OA and hybrid
journals and not for fully paywalled ones. When it cannot sample, say so rather than
substituting a guess.
