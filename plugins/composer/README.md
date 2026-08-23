# The Composer

A literature-intake pipeline whose output you do not have to re-check.

Three scripts, none of which calls a language model:

| Script | Does |
|---|---|
| `scripts/collect` | PubMed search → records → Open Access full texts → per-search folder |
| `scripts/validate5d.py` | 5-dimension bibliographic validation against Crossref + PubMed + Europe PMC |
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
$S/prisma --project endo-diet ingest
$S/prisma --project endo-diet dedup --auto
$S/prisma --project endo-diet template          # decide, then screen --from-csv
$S/prisma --project endo-diet export --format all
```

## Self test

```bash
python3 scripts/selftest.py
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
Anaconda python3 its shebang points at. `validate5d.py`, `prospero.py` and
`prisma` are stdlib-only and run on any python3.
