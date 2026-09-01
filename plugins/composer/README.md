# The Composer

A literature-intake pipeline whose output you do not have to re-check.

Five scripts, none of which calls a language model:

| Script | Does |
|---|---|
| `scripts/collect` | PubMed search → records → Open Access full texts → per-search folder |
| `scripts/scholar` | Google Scholar sweep → resolved to DOI/PMID → the same full-text routes and the same gate |
| `scripts/lookup` | Supplementary sources — OpenAlex, Semantic Scholar, arXiv preprints, ClinicalTrials.gov |
| `scripts/validate5d.py` | 5-dimension bibliographic validation against Crossref + PubMed + Europe PMC + OpenAlex |
| `scripts/prospero.py` | PROSPERO protocol record — scaffold, eligibility check, export |
| `scripts/prisma` | PRISMA 2020 flow, PRISMA-S search appendix, screening decisions, exports |

## The gate

A record is **admitted** only when both hold:

1. the full text is on disk (PDF, or JATS XML with `--xml-fallback`), and
2. all five dimensions agree between the authorities: **DOI · first author ·
   author list · journal · volume**.

Anything else is *held*, with the reason recorded — never silently dropped.
`visszatartott.csv` and the PRISMA eligibility branch keep it auditable.

### Why three authorities, not two

Two authorities can tell you *that* they disagree. Three can tell you *which one
is wrong*. Crossref's deposit for `10.1186/s12916-024-03503-y` lists 18 authors
because four consortium members' given names were deposited as family names;
PubMed and Europe PMC both have the correct 14. On a two-way check that paper is
rejected on a publisher's metadata bug. The majority rule keeps it, and flags
`Crossref-adathiba gyanú` in the report instead.

### What is *not* a rejection

A mismatch on **journal** or **volume** while the DOI and both author dimensions
agree means the same work is *labelled* differently — a renamed journal
(*Biopolymers* → *Peptide Science*), a translated title (*Bratislavske lekarske
listy* / *Bratislava Medical Journal*), an ahead-of-print volume. These are held
as `variant` with the discrepancy named. Only an identity mismatch — DOI, first
author, author list — rejects.

## Layout it writes

```
<outdir>/
  osszesitett_lista.csv        every retrieved record, with its verdict
  befogadott_korpusz.csv       the admitted set — this is what downstream tools read
  visszatartott.csv            held records + reason
  kereses_naplo.jsonl          machine-readable search log (PRISMA-S source)
  <topic>/<pmid>.pdf|.xml      the full texts, stored once
  keresesek/<stamp>_<slug>/
      kereses.json             query, date, counts, filters, protocol, gate
      NAPLO.md                 the same, readable, for the methods appendix
      talalatok.csv            all records from this search
      befogadott.csv           admitted
      visszatartott.csv        held, with reasons
      validacio.csv            5 dimensions × every record
      teljes_szoveg/           symlinks to the full texts (no bytes duplicated)
  prisma/<project>.json        screening state
```

## Typical run

```bash
S=scripts
$S/prospero.py init --project endo-diet --title "Diet and endometriosis: a systematic review"
$S/prospero.py check --protocol endo-diet-protocol.json
$S/collect --outdir ~/Documents/PubMed_Downloads --protocol endo-diet-protocol.json \
           --query '"endometriosis"[mh] AND diet[tiab]' --query-name endo-diet \
           --raw --retmax 500 --xml-fallback
# supplementary only, never on its own:
$S/scholar --outdir ~/Documents/PubMed_Downloads --protocol endo-diet-protocol.json \
           --query '"endometriosis" diet -mouse' --query-name endo-diet \
           --retmax 100 --years 10 --min-citations 5 --xml-fallback
$S/prisma --project endo-diet ingest
$S/prisma --project endo-diet dedup --auto
$S/prisma --project endo-diet template          # decide, then screen --from-csv
$S/prisma --project endo-diet export --format all
```

## Google Scholar

Scholar indexes what MEDLINE does not — theses, book chapters, conference
papers, regional and non-indexed journals. That is the only reason it is here,
and the limits are logged with every search rather than mentioned once in a
README:

- **No API.** `scholarly` reads the public result pages. Google's terms do not
  allow it and Google blocks IPs that keep doing it. `MaxTriesExceededException`
  is that block, not a network error — wait, do not retry harder.
- **Not reproducible.** Personalised ranking, a rounded "About N results"
  estimate, ~1000 results reachable at most. Cochrane and PRISMA-S treat Scholar
  as supplementary, so `count_total` in the log is the number of records
  actually retrieved and Google's estimate is reported separately, flagged as an
  estimate. The PRISMA-S appendix carries the footnote automatically.
- **Scholar's metadata never enters the corpus.** A snippet has no DOI, no
  volume, no ISSN and authors printed as "JA Smith" — the gate would mark every
  record unverifiable. Each hit is resolved instead: DOI from its own link, or a
  Crossref match that has to agree on title **and** year **and** first author;
  then DOI → PMID; then the record is rebuilt from MEDLINE or Crossref. Scholar
  contributes discovery, the link and the citation count.
- **Full texts stay on the legitimate routes.** PMC Open Access first, then
  **Unpaywall** for DOIs PMC does not hold. Scholar's own links are not
  followed.

A paper both sources find is not counted twice: the Scholar hit is dropped and
the existing corpus row is stamped `PubMed; Google Scholar`, keeping the Scholar
citation count. The corpus CSVs **grow** across runs and sources — `--fresh`
overwrites instead, for when a corpus really should start over.

### The Scholar question is asked on every search

Because Scholar is a source you must *account for* whether or not you use it,
`collect` ends every run with a decision block, and the search log carries the
answer:

| `--scholar` | log says |
|---|---|
| `ask` (default) | `felajánlva, még nem eldöntve` |
| `yes` | `lefuttatva (külön mappában, kiegészítő forrásként)` |
| `no` | `megfontolva, elvetve` |

PRISMA-S asks which sources were searched **and** which were considered and
dropped; a log that simply never mentions Scholar cannot answer either. Set
`COMPOSER_SCHOLAR=no` in the environment to stop being asked.

When a sweep does run, `scholar --after <search folder>` writes the
back-reference: the parent log gains a `## Kiegészítő Scholar-keresés` section
pointing at the sweep's directory, and the parent `kereses.json` flips to
`lefuttatva`. Running it twice does not duplicate the entry.

## Self test

```bash
python3 scripts/selftest.py
```

## Supplementary sources

```
$S/lookup --outdir ~/Documents/PubMed_Downloads --sources openalex \
    --query 'endometriosis cost of illness' --query-name endo-cost --retmax 50 \
    --after ~/Documents/PubMed_Downloads/kereses_<stamp>_<slug>
```

| Source | For | Gate |
|---|---|---|
| `openalex` | the fields PubMed does not index — health economics, informatics, engineering | ordinary 5D |
| `semanticscholar` | metadata and citation graph; heavily rate-limited without a key | ordinary 5D |
| `arxiv` | preprints; requires `--preprints` | preprint gate → `preprintek.csv` |
| `clinicaltrials` | registered but never published | none → `regiszter_clinicaltrials.csv` |

`collect` ends every run with a second decision block, `DÖNTÉS KELL: kiegészítő
források` (suppress with `--lookup yes|no` or `COMPOSER_LOOKUP`), and the search
log records the answer either way — including a deliberate rejection, which is
what PRISMA-S asks for.

Preprints never enter `osszesitett_lista.csv`. They have no journal and no
volume, so the ordinary 5D gate would reject every one of them by definition
rather than by suspicion; the preprint gate checks what they can be held to
instead — arXiv ID, version, submission date, first author, author list, title.

OpenAlex is also the **fourth authority** in the gate itself (Crossref → PubMed
→ Europe PMC → OpenAlex), consulted only for a dimension the first three left
unsettled, and never able to overturn a dimension already outvoted 2:0.
```

Offline and deterministic — the three authorities are stubbed with the exact
records that produced each real false positive and false negative found while
building the gate: the "et al." truncation, the particle and accented surnames,
the article-number journals with no volume, the renamed and translated journal
titles, and the malformed Crossref deposit whose four extra "authors" are
consortium members' given names. If one of those regresses, the gate starts
either admitting references it cannot vouch for or rejecting real papers — and
both failures look like success in the summary line.

## Dependencies

`collect` needs `biopython`, `requests` and (optionally) `pandas` on the
Anaconda python3 its shebang points at. `scholar` needs those plus `scholarly`
(`pip install scholarly`); it imports `collect` as a module, so the Article
schema, the PMC OA download path, the search-folder writer and the 5D runner are
the same code rather than a parallel copy. `validate5d.py`, `prospero.py` and
`prisma` are stdlib-only and run on any python3.
