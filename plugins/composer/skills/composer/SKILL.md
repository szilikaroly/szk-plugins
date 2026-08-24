---
name: composer
description: The Composer — build a citable literature corpus. Searches PubMed and, as a supplementary source, Google Scholar, downloads the Open Access full texts through the legitimate PMC OA / Europe PMC / Unpaywall routes, and admits a paper only if it has a readable full text AND survives 5-dimension bibliographic validation (DOI, first author, author list, journal, volume) against Crossref, PubMed and Europe PMC. Every search gets its own logged directory under PRISMA 2020 / PRISMA-S rules and a PROSPERO protocol record. Use whenever the user wants to find, collect, screen, download or verify papers — "keress cikkeket X-ről", "gyűjtsd össze az irodalmat", "töltsd le a teljes szövegeket", "ellenőrizd a hivatkozásokat", building a reference base for a manuscript, a systematic or narrative review, a grant, or a PRISMA flow diagram, or any PubMed / NCBI / Entrez / MEDLINE / Crossref / Google Scholar / scholarly request. Hungarian triggers — irodalomkutatás, szakirodalom gyűjtés, PubMed keresés, Google Scholar keresés, szürke irodalom, cikkek letöltése, teljes szöveg, hivatkozás-ellenőrzés, PRISMA folyamatábra, PROSPERO protokoll, keresési napló.
---

# The Composer

Retrieval, verification and logging are mechanical, so they are done by scripts
with no language model in them. Screening — deciding which papers answer the
question — is judgement, so it stays in the conversation where the user can see
and overrule it. That split is the whole design: it is what makes the harvest
reproducible and the screening auditable.

## The rule that governs everything else

**A paper enters the corpus only if it can be downloaded *and* it passes 5D
validation.** Never present a record as part of the corpus because it looked
right in a search result. If it is held, say it is held and why.

| Dimension | Checked against |
|---|---|
| DOI | resolves at Crossref, and returns *that* DOI |
| first author | surname agrees across authorities |
| author list | same head surnames in the same order ("et al." truncation allowed) |
| journal | full title, ISO abbreviation or ISSN agrees |
| volume | agrees; on article-number journals the e-locator is compared instead |

Three authorities, majority rule: Crossref is the counter-authority to PubMed,
and Europe PMC breaks ties. A mismatch on DOI or either author dimension is an
**identity** failure and rejects the record. A mismatch on journal or volume
while identity holds is a **label** difference — a renamed journal, a translated
title, an ahead-of-print volume — and is held as `variant`, not rejected.

## Workflow

### 1. Protocol first, always

```bash
P="${CLAUDE_PLUGIN_ROOT}/scripts"
python3 "$P/prospero.py" init --project <slug> --title "<review title>"
python3 "$P/prospero.py" check --protocol <slug>-protocol.json
```

`check` enforces two rules people get wrong, and it is worth reading its output
aloud to the user rather than summarising it:

- **PROSPERO does not register narrative, scoping or literature reviews.** Only
  systematic, rapid and umbrella reviews of health outcomes. If the user is
  writing a narrative review — which they often are — say so and point at OSF
  Registries. Writing "registered in PROSPERO" in a narrative review is a claim
  a reviewer can check and disprove.
- **Registration must precede data extraction.** Once extraction has started the
  window is closed; the honest move is then to state in the manuscript that the
  review was not registered, not to register it retrospectively.

If the user declines a protocol, run anyway — but the search log will record its
absence, and say that out loud once.

### 2. Harvest

```bash
"$P/collect" --outdir ~/Documents/PubMed_Downloads \
             --protocol <slug>-protocol.json \
             --query '<PubMed syntax>' --query-name <slug> \
             --raw --retmax 500 --xml-fallback
```

| Flag | Effect |
|---|---|
| `--query` / `--query-name` | raw PubMed syntax + the folder/label for it |
| `--raw` | the query goes to PubMed untouched — **required** to collect RCTs, meta-analyses or systematic reviews, which the default exclusion filter removes |
| `--all-types` | keep the exclusion filter, drop the review filter (original research) |
| `--topic <name>` | one of the built-in topics; repeatable |
| `--retmax N` | hits per query (default 50). Below the true hit count the search is a *sample*, and every log says so |
| `--years N`, `--strict` | last N years; require the literal phrase "narrative review" |
| `--no-pdf` | metadata only — a first look. Turns off the full-text half of the gate |
| `--xml-fallback` | keep JATS full text when no PDF exists |
| `--no-validate` | skip the gate entirely; the log records that it was skipped |

Start a new topic with `--strict --no-pdf --retmax 20` to see how thin the yield
is before committing to a full run.

**Two query facts that change what the user gets.** PubMed has no "narrative
review" publication type, so without `--strict` the filter falls back to
`review[pt]` — broad and noisy. And the `NOT` clause applies to the whole
record, so a genuine narrative review that merely *discusses* meta-analyses can
be excluded; that is usually why a known paper is missing.

### 2a. The Scholar question — asked on every search

`collect` finishes with a `DÖNTÉS KELL: Google Scholar` block unless the run
already carried `--scholar yes|no` (or `COMPOSER_SCHOLAR` is set). Put it to the
user as a real clickable question and record the answer either way: the search
log has a **Kiegészítő forrás — Google Scholar** section whose state is one of

| state | meaning |
|---|---|
| `felajánlva, még nem eldöntve` | the question was raised and is still open — the log says so rather than going quiet |
| `lefuttatva (külön mappában, kiegészítő forrásként)` | a sweep ran; `--after` linked the two logs |
| `megfontolva, elvetve` | deliberately not run — **this is a PRISMA-S requirement**, not bookkeeping |

A reviewer asking "did you search Scholar?" gets an answer from the log in all
three cases. A search that never mentions Scholar cannot answer it at all.

### 2b. Google Scholar — supplementary only

```bash
"$P/scholar" --outdir ~/Documents/PubMed_Downloads \
             --protocol <slug>-protocol.json \
             --query '"endometriosis" "economic burden" -mouse' --query-name <slug> \
             --retmax 100 --years 10 --min-citations 5 --xml-fallback
```

Reach for this when the question needs what MEDLINE does not index — theses,
book chapters, conference papers, regional or non-indexed journals, working
papers. That is its only job here. **Never run it as the primary search**, and
say why once, out loud, before the first run:

- **No API.** `scholarly` reads the public result pages. Google's terms do not
  allow that, and Google enforces it with a CAPTCHA and then an IP block. If a
  run dies with `MaxTriesExceededException`, that IS the block — waiting is the
  fix, retrying harder is not.
- **Not reproducible.** Personalised ranking, a rounded "About N results"
  estimate, and only ~1000 results reachable however large N looks. Cochrane and
  PRISMA-S treat Scholar as supplementary. The script therefore logs the number
  of records actually retrieved as the count, and reports Google's estimate
  separately, flagged.
- **Scholar's metadata is never trusted.** A snippet has no DOI, no volume, no
  ISSN and authors printed as "JA Smith" — every record would fail the gate as
  unverifiable. So each hit is resolved: DOI from its own link, or a Crossref
  match on title **and** year **and** first author; then DOI → PMID; then the
  record is rebuilt from MEDLINE or Crossref. Scholar contributes the discovery,
  the link and the citation count, nothing else.
- **Full texts still come from PMC OA, then Unpaywall.** Scholar's links are not
  followed.

| Flag | Effect |
|---|---|
| `--query` | **Scholar** syntax, not PubMed. `"phrase"`, `AND`/`OR`, `-excluded`, `intitle:`, `author:"Surname"`, `source:"Journal"`. PubMed field tags are rejected outright — Scholar would search for the literal bracket text and return confident nonsense |
| `--retmax N` | start at 20. A big first run is how the IP gets blocked |
| `--pause S` | politeness gap between hits (default 1.5s). Raise it, never lower it |
| `--min-citations N` | the cheapest cut through Scholar's grey-literature noise |
| `--years N`, `--year-from`, `--year-to`, `--sort-by date` | date limits |
| `--patents`, `--citations` | both **off** by default; `--citations` re-admits citation-only stubs that have no document behind them |
| `--proxy scraperapi` | needs `SCRAPERAPI_KEY`. `--proxy free` exists and rarely works |
| `--no-unpaywall`, `--no-pubmed-link` | narrow the resolution chain |
| `--dry-run` | print the query and settings, search nothing |

Report the resolution line — how many hits got a DOI from their link, how many
from a Crossref title match, how many stayed unidentified, how many are in
PubMed. A hit with no DOI cannot pass the gate; for a thesis that is the correct
outcome, not a bug, and chasing it by hand is the user's call.

A paper both sources found is **not** counted twice: the Scholar hit is dropped
and the existing corpus row is stamped `PubMed; Google Scholar`, keeping the
Scholar citation count. The search log records the duplicate count for PRISMA.

### 3. Read the result — never `cat` the CSV

The abstracts alone will flood the context.

```bash
python3 -c "
import pandas as pd, sys
df = pd.read_csv(sys.argv[1])
print(df[['pmid','cim','folyoirat','ev','statusz','validacio']].to_string(index=False))
" ~/Documents/PubMed_Downloads/befogadott_korpusz.csv
```

- `befogadott_korpusz.csv` — the admitted set. **This is the corpus.** Downstream
  tools read this one. It **grows** across runs and across sources, so a Scholar
  sweep does not erase the PubMed harvest and vice versa; `--fresh` restores the
  old overwrite behaviour when a corpus really should start over.
- the `forras` column says which database found each record (`PubMed`,
  `Google Scholar`, or both), and `idezetek` carries the Scholar citation count
  when there is one.
- `visszatartott.csv` — held records with the reason. Go through these with the
  user: a `fuggoben` on "nincs letöltött teljes szöveg" is usually a paywall,
  and the answer is interlibrary loan or dropping it — not quietly citing it.
- `keresesek/<stamp>_<slug>/NAPLO.md` — the methods-ready log of that one search.
- `keresesek/<stamp>_<slug>/validacio.csv` — the five dimensions per record.

### 4. Screen, then build the PRISMA trail

```bash
"$P/prisma" --project <slug> ingest        # search log + corpus + gate verdicts
"$P/prisma" --project <slug> dedup --auto  # by DOI, then by normalised title
"$P/prisma" --project <slug> template      # -> a decisions CSV of undecided records
"$P/prisma" --project <slug> screen --from-csv <...>-szures.csv
"$P/prisma" --project <slug> status
"$P/prisma" --project <slug> export --format all
```

`ingest` carries the 5D verdicts into the flow: a rejected record becomes an
eligibility-phase exclusion with its own stated reason. Single decisions work
without a CSV: `screen --include 111 222`, `screen --exclude 555 --reason
"off-topic" --phase screen`.

`export` writes `prisma-flow.md` (a methods paragraph), `search-strategy.md`
(the PRISMA-S appendix), `prisma.flowchart.json` (render it with `figure-forge`)
and `included.ris` / `included.csv`.

Screen on titles and abstracts in batches, only for rows still in play, and say
which ones were dropped and why — a screening decision the user cannot inspect
is worth nothing. Check the `licenc` column before reusing any figure or
passage: `CC BY` is permissive, `CC BY-NC-ND` forbids derivatives.

### 5. Validating a list you did not harvest

`validate5d.py` takes any CSV with `pmid` and/or `doi` columns, so it also
audits a manuscript's existing reference list:

```bash
python3 "$P/validate5d.py" --records refs.csv --out refs-validacio.csv \
        --cache .v5d-cache.json --no-fulltext-gate
```

`--cache` makes re-runs offline and instant, which matters when re-checking
after fixes. `--no-fulltext-gate` judges the five dimensions only. A single
reference: `--doi 10.xxxx/yyyy`.

**Confirm every flag against the actual reference text before editing anything.**
The traps that produced false positives before the normalisations existed are
documented at the top of `validate5d.py`: "et al." truncation, particle and
accented surnames, and article-number journals where PubMed leaves `pages` empty
while Crossref carries the e-locator.

## Why full texts come from where they do

Scraping `ncbi.nlm.nih.gov/pmc/articles/PMC…/pdf/` is what most example code
does, NCBI's policy forbids it, and they block IPs that do it. So the script asks
the **PMC OA Web Service** whether a paper is really in the Open Access subset
and under which licence, fetches from the OA link or Europe PMC's render
endpoint, and verifies the `%PDF-` header before keeping the file. Non-OA papers
stay metadata-only — that is the honest outcome. Do not add a scraping fallback.

For a DOI that PMC does not hold, `scholar` asks **Unpaywall** — the documented
API for "is there a legal free copy of this DOI, and where" — and downloads the
publisher's or repository's own deposit, header-checked the same way. Links that
Google Scholar prints are never followed. Scholar's own retrieval is the one
place in this plugin that touches a page it was not invited to, it is confined
to discovery, and the search log says so in writing.

Credentials resolve `--api-key`/`--email` → `NCBI_API_KEY`/`NCBI_EMAIL` →
`~/.config/ncbi/env` (already set up, mode 600), so normally pass nothing.

## Dependencies

`collect` needs `biopython`, `requests`, optionally `pandas`, on the Anaconda
python3 its shebang names. `scholar` needs all of that plus `scholarly`
(`pip install scholarly`); it imports `collect` as a module, so the Article
schema, the PMC OA download path, the search-folder writer and the 5D runner are
literally the same code, not a parallel copy. `validate5d.py`, `prospero.py` and
`prisma` are stdlib-only.
