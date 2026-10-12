---
name: prereg
description: Reference for registering a systematic review on PROSPERO or OSF Registries — the registry rules that decide where a review can go, the live PROSPERO field structure and the OSF systematic-review form, how to search for similar registrations, and what each check catches. Loaded by the prereg agent; also useful on its own when someone asks whether a review is eligible for PROSPERO, when registration must happen, or what a registration form asks. Hungarian triggers — PROSPERO regisztráció, OSF regisztráció, protokoll regisztráció, prospektív regisztráció, hasonló regisztráció, regisztrációs űrlap.
---

# Registering a review — reference

Everything here is checked against a public source on 2026-10-12. Where the live
registry form could not be seen (PROSPERO's form is behind login), the file says so.

## 1. Where a review can go

| Review | PROSPERO | OSF Registries |
|---|---|---|
| Systematic, rapid, umbrella review with a health-related outcome | yes | yes |
| Scoping, narrative, literature or mapping review | **no** | yes — but the *Generalized Systematic Review* form is built for systematic reviews; a general form (*Open-Ended Registration*, id `5df83f7dd28338001ac0ab0d`) fits better, and this plugin does not map it yet |
| Systematic review with no health-related outcome | no | yes |
| Animal systematic review, directly relevant to human health | yes — the live form offers it as a separate option (checked 2026-10-12) | yes |
| Animal systematic review without that relevance | no | yes |
| In-vitro-only review | no — CRD suggests OSF | yes |
| Cochrane protocol | not separately — PROSPERO imports it automatically | — |

Sources: PROSPERO's inclusion criteria page and CRD's *Guidance for registering human studies*, found by web search on 2026-10-12. CRD revises its guidance, so check the live PROSPERO site before any submission.

A PROSPERO record that calls a narrative review "registered in PROSPERO" is a claim a reviewer can check and disprove. The manuscript must match the registry the review actually used.

## 2. When registration must happen

- **PROSPERO:** submit before data extraction starts. This rule has applied since October 2019. Scoping the literature, preliminary searches and reading around the topic do not disqualify a review. PROSPERO has no retrospective registration category.
- **OSF:** no timing rule of its own. A registration made after work has begun is not prospective, and the form's *Current review stage* answer has to say so.
- **Permanence (OSF, per OSF's help pages, found by web search 2026-10-12):** a registration cannot be deleted. It can be *withdrawn*: the content goes, the record and its DOI remain. Withdrawal is irreversible and needs every admin's approval, or it happens automatically after 48 hours. An embargo can last up to four years and cannot be reapplied once the registration is public. Corrections go through the update feature, which keeps the original timestamp.
- **PROSPERO versions:** a changed record is a new version, and the old one stays visible. The public record shows *Version 1.0, 1.1…* and a *Show differences* link.

## 3. The stage table — what it is and how it misleads

PROSPERO's *Current review stage* table has six rows, each with *Started* and *Completed* ticks:

pilot work · formal searching / study identification · screening · data extraction or receipt of IPD · risk of bias / quality assessment · data synthesis.

A *Completed* tick implies *Started*. The stage table is the place where a registration says whether it was prospective. A registration whose table shows data extraction as completed was made after extraction, whatever its title or date says.

## 4. The PROSPERO form

`references/prospero-form.json` lists 48 fields as displayed on live registrations (CRD420261486377 and CRD420251001515, public view pages, read 2026-10-12): 36 marked required, 9 optional, and 3 that PROSPERO itself generates (first submission date, registration date, similar-reviews check). The *required* flags are inferred from which fields the public records show filled. *Review type* is the least certain: it appears on one record (as "None") and is absent from the other, so the live form must confirm it. The live form is behind login, so the first real run must confirm them.

Sections, in form order: Review title and basic details · Eligibility criteria · Timeline of the review · Availability of full protocol · Searching and screening · Data collection process · Outcomes to be analysed · Planned data synthesis · Current review stage · Review affiliation, funding and peer review · Additional information.

Two things PROSPERO's public record shows that matter here:

- **Language.** The record is in English. Affiliations and names are exempt.
- **Similar reviews.** PROSPERO checks for similar records and shows them on the record with the team's reason for proceeding. A duplicate with no stated reason looks bad to the next reader.

## 5. The OSF form

`references/osf-sr-form.json` is generated from OSF's public schema API: *Generalized Systematic Review Registration*, schema version 6, schema id `69cbc587cd7e8b69fa11ab52`. It has six pages and 61 required text questions. Two optional file uploads (screening and extraction materials) are not mapped.

| Page | Questions |
|---|---|
| Review Methods | type of review, review stages, current review stage, start and end date, background, primary and secondary research questions, expectations, outcomes, interventions or exposures, covariates, software, funding, conflicts of interest, overlapping authorships |
| Search Strategy | databases, interfaces, grey literature, inclusion and exclusion criteria, query strings, search validation, other strategies, contacting authors and its results, search expiration and repetition, justification, miscellaneous |
| Screening | stages, screened fields and blinding, exclusion criteria, screener instructions, reliability, reconciliation, sampling and sample size, justification, data management and sharing, miscellaneous |
| Extraction | entities, stages, extractor instructions, masking, reliability, reconciliation, justification, data management and sharing, miscellaneous |
| Synthesis and Quality Assessment | planned transformations, missing data, data validation, quality assessment, synthesis plan, inference criteria, synthesist blinding, reliability, reconciliation, publication bias, sensitivity analyses, justification, data management and sharing, miscellaneous |

Every answer is a long-text box, and every one is required, so an empty answer blocks the check.

## 6. Searching for similar registrations

**OSF — public API, no login.** The script wraps it, one call per term:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prereg.py" similar "gestational diabetes; dose-response; protein intake"
```

The OSF title filter is a **phrase match** on the whole term, so a multi-word query returns almost nothing. Separate the terms with `;` and the script runs each one and merges the results. Single generic words are noisy: "dose-response" alone returns many unrelated quantum-physics preregistrations. Read the titles, and treat the `SR` flag (the systematic-review schema) as the first filter. A title-only search misses reviews worded differently, so the result is a floor, not a census.

**PROSPERO — no API. Use the search page in the browser pane:** `https://www.crd.york.ac.uk/PROSPERO/search`. Field tags go in the search box:

Field codes are a colon suffix on the term, not a separate word. Tested live on 2026-10-12: `"gestational diabetes" CS` returns *Error: Invalid search string*; `"gestational diabetes":CS` returns 1801 results.

| Tag | Field | Tag | Field |
|---|---|---|---|
| `TI` | title | `IV` | intervention |
| `CS` | condition studied | `CM` | comparator |
| `PA` | population | `OP` | main outcomes |
| `OS` | additional outcomes | `KW` | keywords |
| `RQ` | review question | `NC` | named contact |
| `OA` | organisational affiliation | `FU` | funding source |
| `CO` | country | `AN` | PROSPERO registration number |

Syntax from the search help: `NEAR` / `NEAR3` for proximity (word order is respected), `ADJ` as a synonym for `NEAR`, `*` for truncation (`nurs*`), and `withdrawn:es` / `living:il` to find withdrawn and living reviews, which do not appear in normal searches. Example: `"dose-response":TI` restricts to titles (1858 results on 2026-10-12). `withdrawn:es` returned 299 withdrawn records.

## 7. What the checks catch

| Check | Catches | Blocks? |
|---|---|---|
| Routing | narrative/scoping review on PROSPERO; animal review without human-health relevance; in-vitro review; no health outcome; Cochrane protocol; data extraction already started | yes (PROSPERO) |
| Required fields | empty required answers, unknown field names, invented fields | yes |
| Placeholders | `TBD`, `TODO`, `XXX`, `???`, `[AUTHOR-VERIFY …]`, `{{…}}`, `<<…>>` anywhere in the content | yes |
| Dates | not ISO, or end before start | yes |
| End date | PROSPERO wants the end at least 28 days ahead (the live form said so on 2026-10-12) | yes |
| Word limits | each PROSPERO free-text field below its minimum or above its maximum (live counts in `PROSPERO_WORDS`; a 4-word placeholder fails rationale, objectives, population, context, outcomes, certainty, synthesis) | yes |
| Team | fewer than two members, no guarantor, or a member without `consent: true` (names may not be added without consent) | yes |
| Search-strategy field | a URL where the form takes a choice (`not_available`, `upload_pdf`, `in_protocol`) | yes |
| OSF metadata | title, description, licence and subject, which the Register dialog and the review page require | yes |
| OSF retrospective | data extraction started, but the *Current review stage* answer does not say the registration is retrospective | yes |
| Boolean grouping | a query with AND and OR and no parentheses: PubMed reads it in its own order (run `pubmed-count` on both forms) | warns |
| Stage table | invalid states; data extraction started; formal searching or screening already run | extraction yes, the rest warns |
| ORCID | check digit (ISO 7064 MOD 11-2) — a mistyped ORCID is the most common silent error | yes |
| E-mail | malformed contact address | yes |
| Similar records | a hit with no stated reason to proceed; no search done at all | hit yes, no-search warns |
| Language | Hungarian accents in an English-only field | warns |
| Title | no design word (`systematic review`, `meta-analysis`, …) for a systematic review | warns |
| Read-back | the live form differs from the plan (any field, any checkbox, any missing value) | yes |

The reviewer pass (Pass 2) covers what a script cannot: whether the question, population, outcomes, synthesis and search describe the same review, and whether the stated timing contradicts the stage table. Its findings are checked by the agent before they are acted on.

## 8. Handoff targets, and what they expect from the registration

| Target | Takes from the registration | Plan contains |
|---|---|---|
| `composer` | the registered search string, verbatim; the registered sources; the stage claims | protocol init, the harvest command with the registered query, the user's Scholar and supplementary-source decisions, PRISMA after screening |
| `validator` | the risk-of-bias instruments the registration names | `/validator:route` per design; slot list for each instrument |
| `metaANAL` | the registered synthesis: models, effect measures, heterogeneity, sensitivity analyses | an R analysis plan that names which steps `metaanal_modul.R` covers (`fit`, `zy`, `evalue`, `bayes`) and which it does not (for example dose-response two-stage) |
| `praxist` | only if the review contains an executable model needing an evaluation harness | a praxist task via `praxist-interactive-task-init`; otherwise none |

If the registered analysis changes after registration, record the change as an amendment (PROSPERO new version, or OSF update). A registered plan that quietly differs from the executed analysis is the thing the registration exists to prevent.
