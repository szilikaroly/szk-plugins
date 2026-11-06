# What referees actually write back about

The other check categories in this plugin are editorial-office checks: is the
disclosure there, is the abstract inside the limit, does every citation have a
reference. `reviewer` is a different kind of check. It asks whether a claim is
carried by what is in the paper, which is the question a referee asks, and it
was built by reading real reports and turning each recurring objection into a
rule that looks for a *missing guard* rather than for a wrong answer.

Every rule below names the report it came from. Thirteen cohorts and two later
rounds, 1,070 referee points, two languages:

| Cohort | Kind of manuscript | Readers | Points | Code prefix |
|---|---|---|---|---|
| 1 | Review | 3 referees | 29 | R1–R3 |
| 2 | Review | 2 referees | 52 | D-R1, D-R2 |
| 3 | Review | academic editor + 3 referees | 30 | M-AE, M-R1–R3 |
| 4 | Review, in Hungarian | editor + 2 referees | 43 | O-Ed, O-R1, O-R2 |
| 5 | Opinion piece | editors + 3 referees | 37 | A-Ed, A-R1–R3 |
| 6 | Long-form work, in Hungarian | 6-part report | 109 | T-A … T-F |
| 7 | Cross-sectional questionnaire survey, in Hungarian | 3 referees | 35 | G-R1 … G-R3 |
| 8 | Open peer review: 18 F1000Research + 20 PeerJ manuscripts, 2021–2026, with the version the referees read | 138 reports | 608 objections | O-<pair>:<reviewer> |
| 9 | Model paper evaluated in simulation only (see the cohort 9 section) | 1 referee | 10 | S-R1 |
| 10 | Evidence synthesis with pooled estimates, two rounds | 2 referees, then 1 | 39 | L-R1, L-R2, L2-R1 |
| 11 | Re-analysis with pooled estimates | 2 referees + academic editor | 24 | N-R1, N-R2, N-Ed |
| 12 | Narrative review with an embedded pooled analysis | 3 referees | 24 | W-R1–R3 |
| 13 | The cohort 9 paper: a second referee in round one, then the editor | 1 referee + editor | 16 | E-R1, E-Ed |
| 3b | Cohort 3, second round | 1 referee (points taken from the response letter) | 5 | M2-R2 |
| 2b | Cohort 2, two later rounds (points known only as restated in the response letters) | 1 referee | 9 | D2-R2 |

The points were read from the original letters. Internal pre-submission
critiques are not referees and were deliberately left out. The reports are
confidential: journals, manuscripts and referees are not named here, codes are
neutral and rules are paraphrases. When a new cohort is added, add its rules with the same
provenance line, and re-run the blind test described at the end.

## Cohort 1 — the first rules

| Code | Rule | Came from |
|---|---|---|
| `design-self-description` | A paper that calls itself a narrative review while running PRISMA, screening, eligibility and risk-of-bias machinery must say, early in the Methods, what it is *not*. | R1.8, R2.1 — both referees independently. |
| `absolute-title` | A title that denies rather than compares ("never", "proves") claims more than a corpus can carry. | R2.3 |
| `single-database-search` / `single-database-limitation-thin` | One database named in the Methods, and either no limitation admitting it or one that does not say what was *not* searched. | R1.11, R2.2 |
| `subset-share-unstated` / `subset-bias-direction` | A stratum appraised out of a larger eligible set, without the percentage and without the direction of the bias the selection rule creates. | R1.9 |
| `fulltext-availability-unreported` | A PRISMA flow that never says how many eligible records had no retrievable full text. | R1.10 |
| `undefined-load-bearing-term` / `definition-not-defended` | A term that carries the conclusions, used without a stated rule — or with a rule that is never weighed against the competing convention. Terms: *external validation*, *clinically significant*, *real-world*, and from cohort 2 two further terms (D-R1.1, D-R2.6, D-R1.7). | R1.2, R2.7 |
| `small-denominator-no-interval` | A striking categorical claim ("none of the N") without the interval that says how loose the bound is. | R1.3 |
| `demonstrated-uncited` | "Each of these has been demonstrated", in a paragraph that cites nothing. | R1.6 |
| `ranking-claim` | A rank ("among the leading causes of death") stated as though it were the estimate. | R1.4 |
| `figures-ambiguity` | "These figures" meaning numbers, in a paper with numbered Figures. | R1.5 |
| `gap-not-stated` | The Introduction never says what this work adds that the cited work does not. | R1.7, R3.2 |
| `prior-work-listed-not-described` | Comparable studies cited as bare markers rather than described and compared. | R3.2 |
| `discussion-novelty-absent` | Novelty stated as aims in the Introduction and never as findings in the Discussion. | R3.3 |
| `conclusions-without-perspective` | Conclusions that end on a principle instead of on what should be done next. | R3.4 |
| `proposal-unmarked` | A design described in the language of something that exists. | R2.4 |
| `no-analytical-pathway` / `endpoint-hierarchy-absent` | A proposal with no falsification path, or discrimination treated as the measure of success with no clinical endpoint above it. Now requires an assay / sequencing / biomarker context — it had fired on two papers with nothing to assay. | R2.5, R2.6 |
| `universal-interval` | A turnaround time given as though it were universal. | R2.10 |
| `terminology-relationship-undefined` | Artificial intelligence, machine learning and deep learning all used, with the nesting never stated. | R2.11 |
| `rob-assessors-unstated` / `rob-reliability-unmeasured` | A risk-of-bias tool named with no account of how many people applied it, or judgments that carry the conclusions with no reliability reported. | R2.8 |
| `abstract-missing-move` / `abstract-out-of-order` | An abstract that does not follow the manuscript's own sequence. | R3.1, R2.9 |

## Cohorts 2–6 — the rules added on 2026-09-12

Ordered by how many cohorts raised the objection. The first three were raised
in four or more of the six.

| Code | Rule | Came from |
|---|---|---|
| `search-not-reported` | A review whose search cannot be repeated: no database, no final search date, no terms, no selection criteria. ERROR when three or more are missing. | D-R1.3, D-R2.1, M-AE.1, M-R2.2, T-B-M6, R1.11 — **five of six cohorts**; the most-repeated objection in the corpus. |
| `abbreviation-undefined` | An abbreviation used two or more times with no "(ABBR)" definition, no abbreviation-list entry and not in the title. Tokens with digits, trailing-hyphen fragments and currencies are ignored; WARN only from three tokens. | M-R3.3, M-AE.4, D-R1.23, O-R1.17, O-R2.13, O-R2.14, T-A-m7 — five cohorts. |
| `limitations-absent` | A manuscript of 1000+ words that never names a limitation, caveat, or "cannot establish". | M-R2.3, M-R2.8, A-R2.2, D-R1.7, T-B-m6 — four cohorts. |
| `evidence-table-absent` | A review reporting six or more effect sizes or accuracies in prose with no table. | M-AE.3, M-R2.5, M-R3.6, M-R3.7, D-R1.1, D-R1.4, D-R2.5, T-E-M8 — three cohorts, eight points. |
| `editorial-placeholder` | "citation needed", "[authors to confirm…]", "[Affiliation to be completed]", "Word-ben frissül", "Error! Reference source not found". | D-R1.16, D-R2.2, T-A-M2, T-B-m4, T-F-M3. |
| `recommendation-outruns-evidence` | The text calls the approach unvalidated or hypothesis-generating and still says it *should be adopted*. | A-Ed.4, A-R3.0, A-R2.5, D-R1.2, D-R2.16, M-AE.2, M-R2.3. |
| `causal-verb-on-observational` | "Transmitted through", "protective effect", or *causes / prevents / drives* in an epidemiological sentence, uncited and unhedged, in a paper whose evidence is case-control or cohort. | D-R1.2, D-R1.5, D-R1.25, D-R2.4, D-R1.18, O-R2.6, O-R2.7.  |
| `numeric-target-unsourced` | A numeric target, threshold or cut-off with no citation, guideline or consensus behind it. WARN when hedged as provisional — the hedge did not stop the question. | A-Ed.4, A-R1.2, A-R2.1, A-R3.5, A-R3.6, A-R3.17 — six points from four readers of one short paper. |
| `classification-criteria-unstated` | Two or more prevention levels used and no sentence stating how an intervention is assigned to one. | D-R1.1, D-R1.12, D-R1.24, D-R2.3, D-R2.6. |
| `screening-harms-unstated` / `screening-metrics-absent` | "Screening" eight or more times with no overdiagnosis or false positives; or with no sensitivity, specificity or predictive value anywhere. | D-R1.12, D-R1.13. |
| `harms-not-weighed` / `absence-of-harm-as-safety` | Two or more recommendations with no harm, adverse effect or burden named; "no adverse events were reported, so it is safe". | D-R1.13, D-R1.31, A-R2.2, O-R2.9. |
| `novelty-unhedged` | "No previous review", "the first to", without "to our knowledge" or the search that would have found a competitor. | D-R1.17, D-R2.1; cohort 5. |
| `own-study-registration-unstated` | The authors' own trial or programme invoked with no registry identifier and no registration status. | A-R2.6, A-R3.9, D-R1.33. |
| `certainty-adjective-unscaled` | "Robust evidence", "promising signal", "clinically actionable" twice or more, with no certainty level or GRADE language anywhere. | D-R1.4, D-R1.7, D-R1.10, T-C-m5. |
| `relative-effect-as-prevention` | A risk ratio restated as a percentage prevented, with no absolute rate anywhere. | D-R1.5, D-R1.26. |
| `systematic-label-unsupported` | "Systematic" in the title or abstract with none of the machinery: no PRISMA, no databases, no eligibility, no screening. | Cohort 4, D-R1.3, T-B-M6. |
| `reference-entry-double-format` | Three or more entries carrying a second copy of themselves in another format (an export `{…}` block, or the first author repeated). | O-R1.5 — the referee read it as evidence about citation practice. |
| `ai-references-verification-unstated` / `ai-disclosure-vague` | AI assistance disclosed and nothing says the references were verified against Crossref or PubMed; or the disclosure names no model or version. Only a disclosure-shaped mention counts, not a paragraph about AI. | O-Ed, D-R2.11. |
| `domestic-literature-absent` | A Hungarian-language manuscript with 20+ references and none from a Hungarian journal, author group or guideline. | O-R1.1, O-R1.4 — both referees, one by name. |
| `references-not-current` / `references-mostly-old` | Nothing from the current year; or more than half of the references six or more years old. | O-R1.3, T-A-M5e. |
| `conference-abstract-cited` | Entries that look like congress abstracts or supplements. | O-R1.2. |
| `references-in-press` | "In press", "submitted", "DOI pending". | T-F-m4. |
| `stated-reference-count-mismatch` | A stated reference count against a list of a different length. | T-F-M1, T-B-M8, T-C-m6. |
| `mixed-citation-styles` | Numbered and author-year citations both used in the body. | T-F-M2. |
| `self-citation-share` | A quarter or more of the list carrying an author's surname. | T-C-M3. |
| `title-long` | Over 20 words; WARN from 30. | O-R2.1, T-A-M3. |
| `table-overload` | More than eight tables. | O-R1, O-R2.1, T-E-M9. |
| `long-sentences` | Sentences over fifty words, when there are five or more or they are five percent of the text. | A-R1.1, T-A-m3, T-C-m7. |
| `cross-reference-direction` / `figure-table-reference-dangling` | "Above" for something below; a figure cited past the last caption. | D-R2.15, T-D-m2, T-B-m2, T-E-M3. |
| `abstract-headline-number-missing` / `abstract-without-numbers` | AUCs in the body and none of them in the abstract; or effect sizes in the body and no number in the abstract at all. Reads the first long paragraph when no Abstract heading exists (some journal templates). | M-R3.5, M-AE.4. |
| `vague-quantifier` | "A significant proportion" with no number in the sentence. | T-B-m6, D-R1.4. |
| `figure-provenance-unstated` | Figures present and nothing says who made them, with what, or under what licence. | O-R1.19, D-R1.18. |
| `single-source-strong-verb` | "Proves" or "confirms" on a single citation that is not itself a synthesis. | O-R2.12, D-R1.10. |

## Cohort 7 — the first primary study

Every earlier cohort was a review or an opinion piece. This one is a
cross-sectional online questionnaire read by three referees, and before its
rules existed the module returned few findings on it, none of them a point a
referee raised. The rules are survey-methods guards.

| Code | Rule | Came from |
|---|---|---|
| `instrument-development-undescribed` / `instrument-validation-unexplained` | a self-built questionnaire, not validated, with nothing about how it was built. Two of three referees; one said the missing validation put every conclusion at risk, and could not find the questionnaire in the supplement the Methods pointed to. | G-R1.5, G-R1.7, G-R2.1 |
| `recruitment-undescribed` | online recruitment with no platform, no sampling method and no exclusion rule; neither referee could tell how respondents were reached. | G-R1.6, G-R2.2 |
| `response-rate-without-denominator` | a response rate in an open online survey, where no one knows how many people saw the invitation. | G-R1.8, G-R2.3 |
| `sample-skew-bias-unnamed` | a sample heavily skewed to one sex, and selection bias never named. A general remark on representativeness did not satisfy the referee. | G-R1.12, G-R2.2 |
| `fieldwork-over-holidays` | fieldwork across the winter holidays, not acknowledged. | G-R3.16 |
| `descriptive-statistics-inconsistent` | mean and SD promised in the Methods, medians in the Results, and no IQR anywhere. | G-R1.9 |
| `model-covariate-selection-unstated` | a multivariable model with no stated reason for its predictors. | G-R1.10 |
| `answer-key-unsourced` | a knowledge score whose wrong answers are declared wrong with no guideline beside them. The referee named one, scored wrong, that practice in fact uses. | G-R3.12 |
| `discussion-restates-statistics` | the Discussion re-reports test statistics instead of explaining them. | G-R1.13 |
| `supplement-carries-discussion` / `supplement-pointer-overload` | the argument moved into a supplement that the referee does not count as part of the paper. | G-R3.13 |
| `figure-table-overload` | many figures and tables for a small sample, most of them bar charts of numbers already in the text. | G-R3.11 |
| `abbreviation-list-incomplete` / `abbreviation-list-non-abbreviation` / `abbreviation-list-unused` | an abbreviation list with an entry the text never uses, statistical notation that is not an abbreviation, and an acronym the text uses but the list lacks. Both referees who read the list found something. | G-R1.15, G-R3.2–G-R3.6 |
| `sentence-left-unfinished` | a sentence that stops on a participle with its object and no complement. Both referees who read the Introduction picked out the same one, and it appeared twice. | G-R1.3, G-R3.8, G-R1.1, G-R3.1 |
| `telegraphic-sentences` | note-form sentences in the body, a label and a value with no verb. One referee read the paper as a condensed longer text; the other asked for subjects and predicates. | G-R1.1, G-R3.1 |
| `approval-number-without-year` | an ethics or permit number with no year. | G-R3.10 |
| `bilingual-abstract-mismatch` | a Hungarian and an English abstract that do not carry the same numbers. | G-R1.2 |

## Cohort 8 — open peer review (added 2026-09-13)

The first cohort whose referees are not the author's. 38 manuscripts whose
review history is public together with the version the referees read: 18 from
F1000Research (v1 JATS + reports), 20 from PeerJ (v0.1 submission PDF +
reports). Harvested with the composer plugin (PubMed, journal-restricted).
BMC/Springer and BMJ Open sit behind a browser challenge and were not fetched.
The 138 first-round reports were read into a fixed taxonomy, 608 objections,
and a rule exists only
where the same objection recurred on two or more manuscripts, or where one
referee's objection was a pure string check. These rules live in
`scripts/pc_reviewer_open.py` and are wired in from `pc_checks.py`.

| Code | Rule | Came from |
|---|---|---|
| `multiplicity-uncorrected` | many p-values, no correction. | O-f1000research.130700.2:R1, O-f1000research.53257.3:R1, O-peerj.18835:R1 |
| `test-named-not-reported` | Kruskal-Wallis in the Methods, never in the Results. | O-f1000research.130700.2:R1 |
| `significance-level-unstated` / `test-sidedness-unstated` | p-values with no stated alpha or sidedness. | O-peerj.18835:R1, O-peerj.17409:R1 |
| `marginal-p-called-significant` | p between 0.05 and 0.10 called significant or a trend. | O-peerj.18881:R1 |
| `normality-unassessed` | parametric tests with no distribution check. | O-peerj.18835:R1, O-peerj.14744:Ed |
| `over-precise-decimals` / `p-decimal-comma` | decimal commas in p-values, and three or more decimals outside p-values. | O-peerj.17409:R1 (twice), O-peerj.19505:R1 |
| `logistic-diagnostics-absent` | a logistic model with no diagnostics. | O-f1000research.129799.3:R1 |
| `fold-claim-without-interval` | 'N-fold higher' with nothing behind it in the sentence. | O-peerj.20076:R1 |
| `ci-spans-null-called-association` | an estimate whose interval includes 1 described as an association. | O-peerj.14744:Ed |
| `prediction-without-validation` | a predictive claim with no validation. | O-f1000research.129799.3:R1, O-peerj.19298:R2 |
| `cross-sectional-causal-language` | cross-sectional design, causal or 'strong' language in the conclusions. | O-peerj.14744:Ed, O-f1000research.146998.2:R1, O-peerj.18835:R1 |
| `software-without-version` | software with no version. | O-peerj.17486:R1, O-peerj.18835:R1, O-peerj.15245:R3 |
| `collection-period-unstated` | no data-collection period. | O-peerj.18835:R1, O-peerj.14744:Ed |
| `sample-size-unjustified` | six manuscripts, no sample-size justification anywhere. | O-peerj.15662:R1, O-peerj.19298:R1, O-peerj.20009:R2, O-peerj.18881:R1, O-peerj.19506:R1, O-f1000research.134328.2:R2 |
| `eligibility-criteria-absent` | no inclusion or exclusion criteria. | O-peerj.18835:R1, O-peerj.17525:R1 |
| `sequence-data-accession-absent` | sequencing data with no accession. | O-peerj.18881:R1, O-peerj.15245:R3, O-peerj.17486:R1 |
| `either-or-in-methods` | 'either DADA2 or Deblur': a method that was not decided. | O-peerj.19528:R1 |
| `participant-age-sex-absent` | human participants with no age or sex reported. | O-peerj.15662:R1, O-peerj.15245:R3 |
| `primary-outcome-unnamed` | a trial with no named primary outcome. | O-peerj.19506:R1 |
| `implications-absent` | no implication for practice or policy anywhere. | O-f1000research.130700.2:R1, O-peerj.17486:R1, O-peerj.18835:R1, O-peerj.19505:R1, O-peerj.14744:Ed, O-peerj.17525:R1 |
| `confounding-unaddressed` | observational human data with no word about confounding or alternative explanations. | O-peerj.14744:Ed, O-f1000research.146998.2:R1, O-peerj.18835:R1 |
| `self-report-bias-unmentioned` | self-reported data with no recall or social-desirability caveat. | O-peerj.17409:R1, O-f1000research.134328.2:R1, O-f1000research.146998.2:R1 |
| `aim-or-hypothesis-absent` | an empirical study whose Introduction states no aim or hypothesis. | O-f1000research.53257.3:R1, O-peerj.18835:R1, O-peerj.19528:R1, O-peerj.17520:R1 |
| `discussion-without-comparison` | a Discussion that never compares the findings with anyone else's. | O-peerj.17409:R1, O-f1000research.134328.2:R1 |
| `introduction-paragraphs-uncited` / `introduction-short` | an Introduction that is too short, or whose paragraphs cite nothing. | O-f1000research.139258.2:R1, O-peerj.17525:R1, O-peerj.15245:R3, O-peerj.18881:R1 |
| `conclusion-boilerplate` | 'provide insights', 'pave the way'. | O-peerj.18835:R1 |
| `single-centre-generalisability` | one site, no word on generalisability. | O-f1000research.172953.1:R1, O-f1000research.146998.2:R1 |
| `knowledge-label-without-cutoff` | 'good knowledge' with no cut-off. | O-f1000research.134328.2:R2, O-f1000research.172953.1:R1 |
| `pre-post-without-followup` | a before-after design with no follow-up. | O-f1000research.130700.2:R1 |
| `abstract-abbreviation-undefined` | an abbreviation in the abstract with no expansion in the abstract. | O-peerj.17486:R1, O-peerj.17520:R1, O-peerj.17525:R5, O-peerj.14744:Ed, O-peerj.17805:R1 |
| `abbreviation-defined-rarely-used` / `abbreviation-defined-twice` |  | O-peerj.17520:R1 (defined, used once more), O-peerj.14744:Ed (defined twice). |
| `spelling-variants-mixed` | 'diarrhea' and 'diarrhoea' in one manuscript. | O-f1000research.125549.4:R2 |
| `taxon-placeholder-labels` | database placeholder labels in prose. | O-peerj.15245:R3, O-peerj.17520:R1 |
| `sentence-ends-on-preposition` | sentences ending on a preposition. | O-peerj.15662:R1 |
| `methods-present-tense` | procedures in the present tense. | O-peerj.18835:R1 |
| `caption-too-short` / `display-item-uncited` |  | O-peerj.17525:R1 (figure cited once or never), O-peerj.17486:R1 (caption of four |
## Cohort 9 — the simulation-vs-validation gap

One report, on a model paper evaluated only in simulation. Ten points, and
every one of them is the same question asked in a different place:
**where did this number come from?**

The cohort exists because of a miss, not because of a gap. Cohort 8 already has
`prediction-without-validation`, and it stayed silent on this manuscript — that
rule exits as soon as the text contains `AUC`, `validat` or `calibrat`, and a
simulated evaluation produces those in quantity while being exactly the thing
the referee objected to. Cohort 8 asks *is validation mentioned*. The question
that mattered was *is this number from a patient*.

| Code | what it looks for | from |
|---|---|---|
| `simulation-metric-unlabelled` | an AUC, PPV, likelihood ratio or ICER stated in the Abstract, Results or Conclusion with no word saying the figure is simulated. Reads only those three places, because the manuscript *did* disclose it — in the limitations — and the referee asked anyway. | S-R1.3 |
| `simulation-caption-unlabelled` | the same, in a figure or table caption. Captions travel into slides without the sentence that qualified them. | S-R1.3 |
| `model-maturity-overclaimed` | "self-learning", "self-improving", "AI-driven" and the like in the title or abstract of a model with no patient-level cohort. | S-R1.1 |
| `development-cohort-absent` | a model is presented and no training, validation or independent test cohort is named anywhere; downgraded to WARN if the abstract or title already says "theoretical" or "simulation-based". | S-R1.1 |
| `parameter-population-mismatch` | a parameter taken from healthy volunteers or the general population and used for a different target population, with no note that it may not transfer. | S-R1.2 |
| `parameter-provenance-unseparated` | a parameterised model with almost no vocabulary (assumed / provisional / literature-derived / imputed) separating measured values from borrowed and assumed ones. | S-R1.2, S-R1.5 |
| `internal-validation-called-external` | one prospective cohort doing duty as both the fitting set and the "external" or "independent" validation, with no separate temporal or geographic cohort named. | S-R1.4 |
| `validation-roadmap-incomplete` | a prospective study proposed without saying which parameters are frozen before it opens — the middle of the three lists a referee needs to tell development from validation. | S-R1.4 |
| `reference-standard-unspecified` | a prospective accuracy study proposed with no reference standard named, or named without addressing verification bias. | S-R1.5 |

**What the gates cost.** All nine rules sit behind two tests — no patient-level
cohort anywhere, and simulation vocabulary used at least three times in the
Abstract, Results or Methods — plus an exclusion for reviews, judged on the
title *and* on a declared `Article type:` line. Each clause was added because
of a false positive on a real manuscript: bare "adaptive" matched *adaptive
immunity* in a title; "prospective" plus a
diagnostic word matched two narrative reviews that merely said prospective
studies are needed; and one narrative review that mentions simulation once was
treated as having run one. After the gates: nine findings on the manuscript the
cohort came from, zero on three unrelated manuscripts.

**Measured, not claimed.** The cohort has been run on exactly four manuscripts.
It has not been blind-tested the way cohorts 1–8 were, and the hit rates in the
table below do not include it.

## Cohorts 10–13 and two later rounds — when the authors pool 

Every earlier cohort was a review, an opinion, a survey or a simulated model.
Here the authors ran the pooling themselves, and the objections moved to how
the pooled number was made and how it was reported. The reports are
confidential, so this section names no journal, manuscript or referee; codes
are neutral and the rules are paraphrases. The rules are in
`scripts/pc_reviewer_synth.py`, wired in from `pc_checks.py`; two that need the
simulation gates are at the end of `scripts/pc_reviewer_sim.py`.

Most of the module sits behind one gate, `_own_meta_analysis`: named pooling
machinery in the Methods. "Pooled" alone is not enough, because a narrative
review says it every time it reports someone else's meta-analysis.

| Code | Rule | Came from |
|---|---|---|
| `effect-measures-mixed` | odds ratios and risk ratios in one pool, with no conversion. | N-R1.4, N-R2.4, L-R1.m1 |
| `heterogeneity-unexplored` | a high I² with no exploration, or attributed to study size. | L-R1.M2 |
| `egger-null-as-absence` | a non-significant small-study test with no word on its power. | L-R1.m6 |
| `few-studies-pooled-unqualified` | a pooled estimate from two to four studies with no qualifier nearby. | W-R1.1, W-R1.4, W-R3.4, L-R2.7, L-R1.M4 |
| `dl-estimator-few-studies` | DerSimonian-Laird on very few studies, no adjusted interval. | W-R3.4 |
| `meta-in-narrative-unjustified` | a pooled analysis inside a narrative review, missing eligibility, prespecified definitions or code. | W-R1.3, L-R2.7 |
| `outcome-definition-not-harmonised` | outcomes taken as each study defined them, or similar endpoints called identical. | N-R1.5, W-R1.4, W-R2.5, W-R3.4 |
| `pooling-minimum-unsupported` | a minimum study count with no source. | L-R1.m3 |
| `fragile-result-not-in-abstract` | a named sensitivity step undoes the result, and the abstract does not say so. Own pooling only. | N-R1.8, N-R2.5, L-R1.M4, L-R1.M5 |
| `ci-bound-false-precision` | a limit printed to a third decimal beside the null, the other limit to two. | N-R1.8 |
| `post-hoc-as-primary` / `post-hoc-unseparated-in-abstract` | a post hoc rule behind the principal analysis; many post hoc analyses and an abstract that does not separate them. | N-R1.7, N-R1.9, N-R2.m1, L-R1.m8 |
| `review-design-label-missing` | the abstract or Methods say what the review is, and the title or abstract do not. | L-R2.1, L-R2.9, N-R1.1 |
| `extraction-pipeline-unvalidated` / `ai-screening-independence-unstated` | machine screening or extraction with no measured check; nothing on whether humans decided independently. The machine has to be doing the work. | L-R2.5, N-R1.10, N-R2.2 |
| `rob-inherited-from-sources` | risk-of-bias judgments carried over from earlier reviews. | N-R1.6, N-R2.3 |
| `methods-limitation-not-carried` | single-reviewer screening or absent registration in the Methods, gone from the Discussion. | L-R2.2, N-R2.m5 |
| `narrative-standard-absent` | a declared narrative review with no reporting standard and no search string shown. | W-R3.1 |
| `impact-factor-eligibility` | journal metrics as an inclusion criterion. String check. | M2-R2.2 |
| `dedup-count-impossible` | more records after de-duplication than before, in one sentence. String check. | M2-R2.1 |
| `dose-response-threshold-underived` | a threshold or plateau with a number and no derivation. | L-R1.M12 |
| `evaluative-word-on-observational` | evaluative wording on observational data, two or more sentences. It came back in a second round. | L-R1.m2, L2-R1.2, W-R3.6 |
| `economic-model-unspecified` | a model result with no transition probabilities, uncertainty analysis or reporting standard. | W-R1.7 |
| `conclusion-mandate-language` | a mandate in the Conclusions of a paper that calls its evidence limited. | W-R3.9, W-R1.5 |
| `rhetorical-register` | two or more stock argumentative phrases. A fixed list; it cannot see an original turn of phrase, which is what the referees quoted. | L-R1.m7, L-R2.13 |
| `placeholder-doi-or-url` | template DOIs and unassigned URLs. Raised in round one, still there in round two. | L-R1.m9, L2-R1.1 |
| `introduction-citation-sparse` | a review's Introduction citing one reference per 120 words or fewer. Blind to superscript citations. | L-R2.3 |
| `display-items-out-of-order` | a figure or table first cited before a lower number that is cited later. | W-R2.6, W-R3.8, E-R1.7 |
| `bold-emphasis-in-body` | bold inside running text in five or more paragraphs; run-in headings excluded. Word files only. | L-R2.13, W-R3.7 |
| `equation-dense-main-text` | many equations in the main text. INFO: it depends on the readership. | E-Ed.1 |
| `abbreviation-before-definition` | an abbreviation used before its expansion in the main text. | E-R1.12 |
| `borrowed-parameter-no-sensitivity` | behind the simulation gates: a borrowed parameter with no sensitivity analysis. | E-R1.4 |
| `projection-language-unmarked` | behind the simulation gates: model output stated as fact, two or more uncited sentences. | E-R1.1 |

**Tried and removed, because they did not fire on the paper they came from.** A
rule for evidence carried over from another population (the paper said so and
the referees still objected: strength, not presence);
a rule for a missing statistics subsection (all three papers had one, the
objection was to its length); a rule for a running trial expected to confirm the
argument; an events-per-variable rule; a rule for a framework's research status
stated late.

**Not rules, because they need reading.** Whether a guideline is summarised
correctly; whether a reference supports a sentence; surrogate outcomes read as
hard ones; asymmetric update searches; a section that is peripheral or too
short; a legend that no longer matches its figure; a hypothesis whose direction
contradicts its source; a forest plot missing its weights (the plot is an
image). N-Ed.1 asked for an analysis that does not fit the design and has no rule. Nothing from cohort 2b became a rule: its table
point is already `figure-table-reference-dangling`, the rest are meaning-level.

**Not read.** A second-round letter on cohort 5 and several other decisions were
not available as text.

**What each first version got wrong** (measured on 13 unrelated manuscripts,
10 English and 3 Hungarian):

- `extraction-pipeline-unvalidated` fired on 4 of 14 on the disclosure sentence
  that a named author verified AI-assisted output. That sentence is the guard.
  Now 0 of 13.
- `bold-emphasis-in-body` fired on 7 of 14: affiliation marks, bold years in the
  reference list. Counting now starts at the Introduction and stops at the
  references. Now 3 of 13, and the same fix showed heading styles had been
  skipped before the start marker was seen, which silenced the rule on its
  own source papers.
- `dedup-count-impossible` paired the wrong two numbers in a sentence with
  several; the two numbers now have to be adjacent.
- `ci-bound-false-precision` fired on a per-unit odds ratio with three decimals
  on both limits. It now needs the two limits printed differently.
- `fragile-result-not-in-abstract` matched a bare "without" in a cited cohort;
  it now needs a named sensitivity step, and own pooling.
- `effect-measures-mixed` matched a sentence saying the measures were never
  merged. Denials are excluded.
- A revised cohort 11 file then showed four more false positives: a
  conversion by a named method, an abstract that already reported the sensitivity
  result with "without", a post hoc note far from "main analysis", and dual review
  discussed under another name. All four guards were widened. One rule still fires
  on that revision, and it may be right.

**Measured, 33 new rules.**

| Set | Files | Result |
|---|---|---|
| Unrelated manuscripts | 13 | `display-items-out-of-order` 5, `bold-emphasis-in-body` 3, `few-studies-pooled-unqualified` 1, `narrative-standard-absent` 1; the other 29 rules 0. Every display-order hit read in its sequence was a true order violation, so 5 of 13 says something about drafts, not about the rule; it stays INFO. |
| Open-review corpus | 39 | `abbreviation-before-definition` 6, `display-items-out-of-order` 5; the other 31 rules 0. |
| Source papers | 4 | 29 of 31 module rules and both simulation rules fire on at least one. `impact-factor-eligibility` and `dedup-count-impossible` are tested only on a synthetic fixture: the file the referee read is not on disk, only a later version. |

Hungarian manuscripts get nothing from these rules: the patterns are English.
Zero findings on the three Hungarian files is silence, not a pass.

**These cohorts are not blind-tested.** The rules were written with the reports
open and tuned on the same files, so firing on the source says only that a rule
can see what it was built for. In-sample coverage, by the author's reading of
which points a firing rule answers: 15 of 39, 10 of 24, 8 of 24, 5 of 16.

**The one blind result here.** Before any of these rules existed, the then 114
rules were run on the files the referees read. That is blind, and it is low. By
the same reading, findings that answered a referee's point: 4 of 39, 2 of 24, 5
of 24, 3 of 16. In one case the rule that looked right
(`recommendation-outruns-evidence`) fired on an unrelated sentence, so it is not
counted. The older rules were built on papers without pooling, and these
reports are mostly about pooling.

## What the rules deliberately do not do

- **No language model, no network.** Every rule is a pattern plus a guard, so the
  output is reproducible and the same file gives the same report a year from now.
- **They report a missing guard, never a wrong result.** `ranking-claim` does not
  know whether the ranking is true; `numeric-target-unsourced` does not know
  whether the number is right. Every message says which guard it looked
  for, so a deliberate omission can be dismissed in one read.
- **They do not fire on hedged, hypothetical or cited sentences** where the
  objection was to the authors' own framing. A cited mechanism is someone
  else's claim.
- **They do not judge scope.** Several of one referee's points asked for a section to be
  removed; nothing deterministic can tell an off-topic section
  from a thorough one. `title-long` and `table-overload` are the proxies.
- **They do not check arithmetic or internal consistency across numbers** (two
  totals for one quantity, two horizons for one forecast). That is
  the academic-editor plugin's deterministic check, and the handoff is
  deliberate.
- **They cannot see a fabricated reference.** A reference that does not exist
  can end a submission on its own. Offline, the nearest guards are
  `reference-entry-double-format` and `ai-references-verification-unstated`. Run
  a Crossref/PubMed audit before submitting anything with AI in its history.

## Known limitations

- `abstract-out-of-order` depends on clean section extraction; where a
  keyword block is absorbed into the abstract, the rule stays silent rather
  than guessing. Silence here is not evidence.
- `subset-bias-direction` reads a 400-character window either side of the
  selection sentence; a caveat three pages later is flagged on purpose.
- `search-not-reported` is satisfied by *any* database name, month-year and
  "search terms" phrase in the body. One submission passed it because a placeholder sentence contained the
  words; `editorial-placeholder` caught that file instead. A review can name PubMed in the Introduction and still have no
  search.
- `abbreviation-undefined` treats any capitalised token that recurs as an
  abbreviation; trial acronyms (SELECT, SURPASS) are reported and are usually
  fine to dismiss. Tokens with digits (T2DM, IL-6) are skipped
  entirely, so an undefined one of those is not seen.
- `causal-verb-on-observational` needs at least two observational-design
  words in the body. A review that never says "cohort" is not checked.
- The Hungarian rules (`domestic-literature-absent`, HU headings, HU
  placeholders) are calibrated on one manuscript. `is_hungarian` is a
  function-word count, not a language model.
- `sentence-left-unfinished` reports only a *repeated* ending. Hungarian ends
  sentences on an adverbial participle legitimately, and the unguarded pattern
  matched often on stored manuscripts, mostly sound prose, and on English text
  as well, where some endings have the same shape.
  A single dangling participle is now not reported at all.
- `telegraphic-sentences` counts note-form sentences only in word-processor
  files. In text extracted from a PDF, line-wrap debris ('et al.', 'Fig.',
  'group.') is indistinguishable from a two-word sentence: the unguarded
  branch fired on 19 of the 38 open-review PDFs, every hit noise.
- `recruitment-undescribed` reads a corresponding author's "E-mail:" line as a
  recruitment channel unless the address is excluded; the guard now wants a
  named platform, a mailing list or a Hungarian inflected form.
- The cohort 7 rules are calibrated on one survey manuscript, and `is_survey`
  needs questionnaire / kérdőív / survey twice in the body — a study that
  calls its instrument something else is not checked by any of them.
- Cohort weighting is still thin: the objections that recur across cohorts
  (search, abbreviations, limitations, tables) are evidence of something
  general; the single-cohort rules are one referee's habit until a second
  cohort confirms them.

## The blind test

The honest test of this module is whether it predicts, from the submitted file
alone, what the referees went on to write. Run it against a manuscript as
submitted and compare with the reports that came back:

```
python3 scripts/pc.py reviewer MANUSCRIPT_AS_SUBMITTED.docx
```

### The author's own cohorts (re-run 2026-09-13 with the then 105 rules)

| Cohort | File | ERROR | WARN | INFO | Total |
|---|---|---|---|---|---|
| 1 | revised | 2 | 11 | 13 | 26 |
| 1 | submitted | 5 | 10 | 12 | 27 |
| 5 | revised | 1 | 3 | 5 | 9 |
| 5 | submitted | 1 | 6 | 1 | 8 |
| 2 | revised | 6 | 12 | 8 | 26 |
| 2 | submitted | 6 | 9 | 7 | 22 |
| 3 | revised | 8 | 7 | 10 | 25 |
| 3 | submitted | 4 | 6 | 11 | 21 |
| 4 | submitted | 4 | 10 | 9 | 23 |
| 7 | submitted | 3 | 19 | 9 | 31 |
| 6 | corrected | 1 | 12 | 10 | 23 |

On the cohort 7 survey, as the referees read it, the module now reports the
unfinished sentences they picked out, the response rate, the unused list entry,
the approval number without a year, the figure count, the mean/SD-versus-median
inconsistency and the model with no covariate rule. Before cohort 7 it returned
few findings, none of them one of those.

### The open-peer-review corpus

38 submitted files, 35 revised files, 105 rules:

| | files | ERROR | WARN | INFO | mean per file |
|---|---|---|---|---|---|
| as submitted | 38 | 47 | 305 | 367 | 18.9 |
| as revised/accepted | 35 | 42 | 283 | 340 | 19.0 |

The revised files do **not** drop much, and the reason is structural: the rules
report missing guards, and a revision that answers a referee in the response
letter rarely adds the guarding sentence to the manuscript. That is a property
of revisions, not evidence that the rules are wrong — but it does mean the
module cannot be used to score a revision as "done".

**Category-level agreement of the cohort-8 rules.** For each cohort-8 finding on
a submitted file, was there at least one referee objection on that manuscript
in the same taxonomy category? 197 of 350 firings (56%). This is a loose
measure — a category, not the specific point — so it bounds precision from
above, and it is recorded so the next cohort can be measured the same way.

| Code | fired (files) | same-category objection | |
|---|---|---|---|
| `spelling-variants-mixed` | 25 | 18 | 72% |
| `abbreviation-defined-rarely-used` | 24 | 12 | 50% |
| `self-report-bias-unmentioned` | 20 | 11 | 55% |
| `abstract-abbreviation-undefined` | 18 | 9 | 50% |
| `abbreviation-defined-twice` | 17 | 8 | 47% |
| `test-sidedness-unstated` | 17 | 12 | 71% |
| `caption-too-short` | 17 | 9 | 53% |
| `software-without-version` | 16 | 7 | 44% |
| `introduction-paragraphs-uncited` | 16 | 6 | 38% |
| `confounding-unaddressed` | 16 | 6 | 38% |
| `sample-size-unjustified` | 12 | 8 | 67% |
| `cross-sectional-causal-language` | 12 | 6 | 50% |
| `implications-absent` | 12 | 5 | 42% |
| `marginal-p-called-significant` | 12 | 8 | 67% |
| `test-named-not-reported` | 11 | 7 | 64% |
| `collection-period-unstated` | 10 | 4 | 40% |
| `eligibility-criteria-absent` | 9 | 9 | 100% |
| `logistic-diagnostics-absent` | 8 | 7 | 88% |
| `participant-age-sex-absent` | 8 | 4 | 50% |
| `over-precise-decimals` | 8 | 6 | 75% |
| `multiplicity-uncorrected` | 7 | 6 | 86% |
| `normality-unassessed` | 7 | 6 | 86% |
| `sentence-ends-on-preposition` | 6 | 4 | 67% |
| `display-item-uncited` | 6 | 2 | 33% |
| `sequence-data-accession-absent` | 5 | 1 | 20% |
| `aim-or-hypothesis-absent` | 5 | 3 | 60% |
| `fold-claim-without-interval` | 5 | 5 | 100% |
| `knowledge-label-without-cutoff` | 4 | 0 | 0% |
| `taxon-placeholder-labels` | 3 | 1 | 33% |
| `prediction-without-validation` | 3 | 1 | 33% |
| `pre-post-without-followup` | 2 | 1 | 50% |
| `conclusion-boilerplate` | 2 | 2 | 100% |
| `discussion-without-comparison` | 2 | 1 | 50% |
| `significance-level-unstated` | 1 | 1 | 100% |
| `single-centre-generalisability` | 1 | 0 | 0% |
| `introduction-short` | 1 | 1 | 100% |
| `primary-outcome-unnamed` | 1 | 0 | 0% |
| `either-or-in-methods` | 1 | 0 | 0% |

Rules below 40% are the ones to read with the most suspicion; rules at 100%
fired rarely. None of these numbers is a score.
