# Presubmit

**Catch the common manuscript submission mistakes before a journal does.**

Inspired by the "avoidable mistakes" every journal editorial office sees —
duplicate references, citations that point nowhere, a missing conflict-of-interest
statement, an over-long abstract, a forgotten Methods section. Presubmit scans a
manuscript and reports every automatically-detectable problem, ranked by
severity, with a fix hint for each.

Deterministic and offline: **no language model, no spell dictionary**, so it
never false-positives on medical terminology. One opt-in exception: `--online`
additionally asks PubMed whether any cited paper carries an erratum, a
retraction or an expression of concern — resolving AMA-style references that
print no DOI through PubMed's citation matcher.

The `submission` and `claims` categories were reverse-engineered from a real
editorial round: every rule in them
corresponds to something an editor asked for by hand.

## What it checks

| category | catches |
|----------|---------|
| **structure** | missing IMRaD / case-report sections (profile-driven) |
| **authors** | no corresponding email, no affiliation, no ORCID in the author block |
| **abstract** | missing abstract, over/under length, wrong keyword count |
| **references** | duplicates (by DOI *and* by near-identical text), missing years, malformed DOIs, incomplete entries, in-text `[n]` citations with no matching reference, references never cited |
| **ethics** | missing required disclosures — conflict of interest, funding, human subjects, informed consent (profile-driven) |
| **format** | repeated words, double spaces, space before punctuation, missing space after a sentence, mixed quote/dash styles |
| **submission** | placeholders (`TBD`, `[insert …]`, a stranded `…,`), unresolved tracked changes and comments still in the .docx, a declared word count over the format limit, more references or figures than allowed, disclosures that belong on the form rather than in an opinion piece |
| **claims** | effect estimates without a confidence interval (checked per parenthetical, not per sentence), trials named only by acronym with no describing clause, the same reference described twice, the authors' own ongoing study promoted in the closing |
| **reviewer** | what a referee writes back about rather than what an office bounces. 147 rules, every one from a real report across thirteen cohorts — twelve of the author's own (462 referee points, kept anonymous) and 38 open-peer-review manuscripts from PeerJ and F1000Research (138 reports, 608 objections): a narrative review running systematic machinery, a review with no reproducible search, 'systematic' in the title with none of the machinery, editorial placeholders left in the file, effect sizes in prose with no table, no limitations anywhere, causal verbs on observational data, prevention levels with no assignment rule, screening with no harms, a numeric target with no source, a recommendation the text itself calls unvalidated, the authors' own trial with no registration, an absolute novelty claim, undefined abbreviations, reference entries doubled in a second format, AI use disclosed with no reference verification, a Hungarian manuscript citing no Hungarian literature, stale or conference-abstract references, an over-long title, too many tables; for primary studies a questionnaire with no validation or recruitment account, a 100% response rate, no sample-size statement, no eligibility criteria, no data-collection period, ten p-values with no correction, a p of 0.07 called a trend, an interval spanning 1 called an association, causal verbs in a cross-sectional study, software with no version, sequencing data with no accession, an abbreviation used in the abstract without expansion; and for a model evaluated only in simulation, an AUC quoted in the abstract with no word saying it was simulated, maturity vocabulary in the title of a model that has never met a patient, a parameter borrowed from another population, and one prospective cohort doing duty as both the fitting set and the 'external' validation, and for a review that pools its own numbers, odds and risk ratios in one pool, a high I² with no exploration, a two-trial estimate with no qualifier, a sensitivity result the abstract leaves out, post hoc analyses the abstract does not separate, machine screening with no measured check. Each rule carries the report it came from — see `skills/presubmit/references/reviewer-patterns.md` |
| **style** *(advisory, not in `check`)* | the tells of an AI-assisted draft, adapted from academic-humanizer: AI vocabulary (delve, pivotal, tapestry…), significance hype (paves the way, sheds light on), empty intensifiers, novelty padding (to the best of our knowledge, for the first time, 'novel' twice in a section), formulaic openers (In recent years…), boilerplate emphasis, vague hedges, copula avoidance, participle tails, filler, over-claiming verbs, 'significantly' with no test, runs of Moreover/Furthermore, citation dumps, sentences over 40 words, and em-dashes in English text. Never an ERROR; English only |

## Commands

| command | scope |
|---------|-------|
| `/presubmit:check` | full scan (all categories) |
| `/presubmit:refs` | references + in-text citation cross-check |
| `/presubmit:ethics` | disclosure / ethics statements |
| `/presubmit:format` | language & typography |
| `/presubmit:submission` | placeholders, tracked changes, word and reference limits |
| `/presubmit:claims` | how the evidence is presented |
| `/presubmit:reviewer` | what a referee will ask for |
| `/presubmit:style` | AI-draft tells (advisory; does not change the verdict) |
| `/presubmit:humanize` | rewrite the chosen sections to remove those tells, keeping the author's voice — then prove with `pc.py invariants` that no number, citation, cite key, DOI, equation or Table/Figure reference was lost or invented |
| `/presubmit:journals` | list built-in journal profiles |

The bundled **presubmit skill** auto-triggers on "check my paper before
submission", "find mistakes", "check my references", and similar (English and
Hungarian).

## Usage

```bash
python3 scripts/pc.py check manuscript.docx --journal cureus --json report.json
```

Reads `.docx`, `.pdf`, `.tex`, `.txt`, `.md` (and `.doc/.odt/.rtf` via
doctotext). `.docx` gives the best structure detection (heading styles are
preserved). Section headings are recognised in English and Hungarian
(Összefoglalás, Bevezetés, Módszerek, Eredmények, Megbeszélés,
Irodalomjegyzék …), so a Hungarian manuscript is checked section by section too. Exits non-zero if any ERROR is found, so it can gate a pipeline.

### Severity

- **ERROR** — commonly triggers desk rejection.
- **WARN** — should fix before submitting.
- **INFO** — worth a glance, not blocking.

A clean report means "no *automatically detectable* problems" — not a guarantee
of acceptance.

## Journal profiles

Profiles are small JSON files in `profiles/` (abstract/keyword limits, required
sections, required disclosures). **Cureus**, **Annals**, **Orvosi Hetilap** and a **generic IMRaD** profile ship
built in. Adding a journal is a data change, not a code change.

## Style and humanize

`/presubmit:humanize` is the academic-humanizer editing pass
([AIScientists-Dev/academic-humanizer](https://github.com/AIScientists-Dev/academic-humanizer)
v0.3.3, MIT, building on [blader/humanizer](https://github.com/blader/humanizer), MIT)
wired into presubmit's deterministic machinery: `pc.py style` measures the
tells first, the rewrite follows the six layers in
`skills/presubmit/references/academic-humanizer.md`, and `pc.py invariants`
checks the one promise a prompt can only make — that the rewrite changed no
number or citation. Where a claim has no evidence in the manuscript the
rewrite inserts an `⟦AUTHOR: …⟧` query instead of inventing a pointer, and the
`submission` check treats that query as a placeholder until it is answered.
The upstream licence is in `licenses/academic-humanizer-LICENSE`.

It is an editing aid for clarity and voice, not a way to evade AI-use
detection; disclose AI assistance as the journal requires.

```bash
python3 scripts/pc.py style manuscript.docx
python3 scripts/pc.py text manuscript.docx --section introduction > original.txt
python3 scripts/pc.py invariants original.txt rewrite.md
```

## Fits with the rest of the toolkit

- Grammar / register / native-English editing → **academic-editor** skill.
- Tracking the submission and reviewer points afterwards → **science-monitor**.
- Slow responses to editorial queries — the one common mistake Presubmit can't
  see in a file — is exactly what science-monitor's inbox tracking handles.

## Self-test

```bash
python3 scripts/pc.py selftest
```

Plants known mistakes in every category and asserts each is caught, plants the
referee-cohort omissions (seventeen from the author's own cohorts, twenty from
the open-peer-review corpus, the simulation and synthesis cohorts) and asserts the
reviewer rule behind each fires,
and checks that a clean manuscript passes.

---

Part of the **szk-plugins** marketplace · MIT · Dr. Szili Károly
