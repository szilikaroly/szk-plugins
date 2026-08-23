---
name: composer
description: The Composer — build a citable literature corpus. Searches PubMed, downloads the Open Access full texts through the legitimate PMC OA / Europe PMC routes, and admits a paper only if it has a readable full text AND survives 5-dimension bibliographic validation (DOI, first author, author list, journal, volume) against Crossref, PubMed and Europe PMC. Every search gets its own logged directory under PRISMA 2020 / PRISMA-S rules and a PROSPERO protocol record. Use whenever the user wants to find, collect, screen, download or verify papers — "keress cikkeket X-ről", "gyűjtsd össze az irodalmat", "töltsd le a teljes szövegeket", "ellenőrizd a hivatkozásokat", building a reference base for a manuscript, a systematic or narrative review, a grant, or a PRISMA flow diagram, or any PubMed / NCBI / Entrez / MEDLINE / Crossref request. Hungarian triggers — irodalomkutatás, szakirodalom gyűjtés, PubMed keresés, cikkek letöltése, teljes szöveg, hivatkozás-ellenőrzés, PRISMA folyamatábra, PROSPERO protokoll, keresési napló.
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
  tools read this one.
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

Credentials resolve `--api-key`/`--email` → `NCBI_API_KEY`/`NCBI_EMAIL` →
`~/.config/ncbi/env` (already set up, mode 600), so normally pass nothing.

## Dependencies

`collect` needs `biopython`, `requests`, optionally `pandas`, on the Anaconda
python3 its shebang names. `validate5d.py`, `prospero.py` and `prisma` are
stdlib-only.
