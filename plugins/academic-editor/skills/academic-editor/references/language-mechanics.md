# Language Mechanics

Every rule below is followed by the operation in the reference edit that produced it —
a real AJE Premium edit of a sleep-medicine manuscript, 61 changed paragraphs, 979
insertions and 896 deletions. Where the sample is *internally inconsistent*, this file says
so rather than inventing a rule the editor did not apply. That distinction matters: an
invented rule applied confidently across a manuscript does more damage than a missing one.

---

## 1. Articles

English marks whether a noun is already identified. Non-native drafts drop the article on
identified nouns and add it to generic ones; both are corrected, in both directions.

**Add `the` when the noun is specified by what follows or by prior mention.**

```
✗  may induce or exacerbate RSWA and increase risk of developing RBD
✓  may induce or exacerbate RSWA and increase the risk of developing RBD

✗  None of patients included in the study fulfilled any other criteria
✓  None of the patients included in the study fulfilled any other criteria

✗  Because of first night effect, the first night was regarded as an adaptation night
✓  Because of the first night effect, the first night was regarded as an adaptation night

✗  According to AASM-2007 criteria, tonic muscle activity was defined as
✓  According to the AASM-2007 criteria, tonic muscle activity was defined as

✗  Chi-square test was used to analyze the differences
✓  The chi-square test was used to analyze differences
```

Named tests, named criteria and named instruments take `the` when used as things
(`the chi-square test`, `the AASM-2007 criteria`, `the HRSD`, `the MSLT`).

**Remove the article when the noun is generic, and pluralize instead.**

```
✗  A one-way analysis of variance (ANOVA) and Kruskal Wallis Test were performed
✓  One-way analysis of variance (ANOVA) and Kruskal Wallis tests were performed
```

This is the pairing to internalize: the fix for a wrong article is often a number change,
not an article change. `A ... test were performed` was ungrammatical in *two* ways at once.

**Table and figure captions take the article too**, because they refer to the specific
patients of this study:

```
✗  Table 1. Demographic and clinical characteristics of depressed patients (n=31)
✓  Table 1. Demographic and clinical characteristics of the depressed patients (n=31)
```

---

## 2. Number and agreement

**A measure reported for many subjects is plural.** This is the single most frequent
grammatical repair in the sample.

```
✗  the lifetime and 1-year prevalence of RBD ... are 5.8% and 3.8% respectively
✓  the lifetime and 1-year prevalences of RBD ... were 5.8% and 3.8%, respectively

✗  There were no significant differences in the TRT during the trial
✓  There were no significant differences in TRTs during the trial

✗  the REM latency was prolonged significantly on the 1st day
✓  the REM latencies were significantly prolonged on the 1st day

✗  Gender (male/female)
✓  Gender (males/females)
```

**Negative coordination takes `or` and a singular verb.** Not `and ... were`:

```
✗  no abnormal movement, behavior and vocalization were observed
✓  no abnormal movement, behavior or vocalization was observed
```

But when the list is *inclusive* rather than negated, `and/or` is the precise form:

```
✓  examined by the sleep technician to identify any abnormal movement, behavior and/or
   vocalization during REM sleep
```

The two sentences are three lines apart in the manuscript and were edited differently, on
purpose. Read the logic before choosing the conjunction.

---

## 3. Tense

| Where | Tense | From the sample |
|---|---|---|
| What the study did | past | `patients received sertraline for 8 weeks` |
| What the study found | past | `the SL and WASO scores decreased significantly` |
| What *this paper* does with its data | **present** | `The data were presented` → **`The data are presented`** |
| Pointers to this paper's own figures/tables | **present** | `This recruitment process was shown in Figure 1` → **`The recruitment process is illustrated in Figure 1`** |
| A relation that still holds | present | `It was consistent with` → **`This result is consistent with`** |
| Established background knowledge | present | `RBD and RSWA are strongly, but not linearly, linked` |
| Prior studies' actions | past / present perfect | `Previous studies suggested` → `Previous studies have suggested` |

The distinction that trips up most drafts: *the experiment happened* (past) but *the paper
presents* (present). A Results section that says "the data were presented as the mean ± SD"
is describing a presentation the reader is looking at right now.

**Delete conditional `would` from Methods and Results.** What happened, happened:

```
✗  subjects with significant PLMS would be excluded from the study
✓  Subjects with significant PLMS ... were excluded from the study

✗  Sertraline would be administered at 8 pm for patient with significant sedation
✓  Sertraline was administered at 8 pm for patients who were significantly sedated

✗  by chances, it was not happened in the current study
✓  this did not occur in the current study
```

---

## 4. Verb precision

Weak verbs get replaced by the verb that names the actual action. The replacement is never
a fancier synonym — it is a more *specific* one.

```
had repeated vPSG            →  were assessed by vPSG
took 200mg/day of sertraline →  received a sertraline dose of 200 mg/day
find out that                →  revealed that
was shown in Figure 1        →  is illustrated in Figure 1
Flow diagram documenting     →  Flow diagram illustrating
correlations ... were performed using the Pearson test
                             →  Correlations ... were determined using the Pearson test
performed by using SPSS      →  performed using SPSS
```

**A verb can also be wrong in logic, not only in register.** The clearest instance in the
sample:

```
✗  A two-sided 5% level of significance was considered statistically significant.
✓  A two-sided 5% level of significance was applied.
```

A significance *level* cannot itself be significant. Fixing this is language editing, not
science editing — the threshold, the sidedness and the value are all untouched.

---

## 5. Prepositions

```
✗  diagnostic criteria of DSM-IV Axis I disorders     ✓  criteria for DSM-IV Axis I disorders
✗  diagnosed as significant OSA                       ✓  diagnosed with significant OSA
✗  characteristic for antidepressants                 ✓  characteristic of antidepressants
✗  not consistent within Winkelman's study            ✓  inconsistent with those described by ...
✗  the sleep disturbance factor score in HRSD         ✓  HRSD-sleep disturbance factor scores
✗  a mechanism about 5-HT neurotransmission           ✓  the mechanisms of 5-HT neurotransmission
✗  RBD being greater prevalent in patients with the usage of antidepressants
✓  the increased prevalence of RBD in patients using antidepressants
```

---

## 6. Comparisons must be between like categories

The most consequential class of edit in the sample, because a mismatched comparison is a
*meaning* error that looks like a style problem.

```
✗  It is ten times more common than the prevalence of RBD in the general population
✓  These prevalences are ten times higher than the prevalence of RBD in the general population
```
(`It` — a disorder — was being compared with a prevalence.)

```
✗  RSWA amounts are higher in multiple systemic atrophy than in PD or idiopathic RBD
✓  RSWA was more common in patients with multiple systemic atrophy than in those with PD
   or idiopathic RBD
```
(A quantity was being located "in" a disease rather than in patients.)

```
✗  Unlike to most antidepressants, the percentage of REM sleep kept stable
✓  Unlike the effects observed with most antidepressants, the percentage of REM sleep was
   stable throughout this trial
```
(A percentage was being contrasted with drugs.)

```
✗  the TST and SE became longer and higher than the baseline or 1st day respectively
✓  the TSTs and SEs became longer and higher, respectively, compared with those at baseline
   or on the 1st day
```
(`than the baseline` compares a duration with a time point; `than those at baseline`
compares durations with durations.)

Check every `than`, `compared with`, `similar to`, `unlike` and `higher/lower in` for what
sits on each side. Compare patients with patients, scores with scores, prevalences with
prevalences.

---

## 7. Modifiers

**Attach the modifier to what it modifies, and move it there physically.**

```
✗  To exclude the disruption of physiologic events for REM sleep, REM epochs in which ...
✓  To exclude the disruption of REM sleep by physiologic events, REM epochs in which ...

✗  Because of daytime MSLT, the third night was not suitable for vPSG assessment
✓  Because the MSLT was conducted during the day, the third night was not suitable

✗  At the first night of baseline vPSG assessment, subjects with significant PLMS ... would
   be excluded from the study
✓  Subjects with significant PLMS ... on the first night of the baseline vPSG assessment
   were excluded from the study
```

**Collapse a relative clause into an adjective when it carries one attribute:**

```
✗  edited by an experienced PSG technologist, and this technologist was blinded to the study
✓  edited by an experienced blinded PSG technologist
```

**Drop the possessive from an attributive noun:**

```
✗  a bilateral leg's EMG (anterior tibialis muscles)
✓  bilateral leg EMG (anterior tibialis muscles)
```

---

## 8. Parallelism

A list whose members do not share a grammatical shape is rebuilt so that they do. The
sample's clearest case rebuilt four members at once:

```
✗  these patients are of younger age, female predominance, being associated with
   antidepressants usage, and no less concurrent neurodegenerative diseases compared to
   the RBD patients in the general population
✓  compared with RBD patients in the general population, psychiatric outpatients with RBD
   were younger in age, were predominantly female, were more likely to be using
   antidepressants, and had fewer concurrent neurodegenerative diseases
```

Note the second repair in the same sentence: the comparison basis (`compared with ...`) was
moved to the front, so the reader knows what the four attributes are being measured against
before reading them. See `structure-and-flow.md` §Information order.

---

## 9. Register

**Delete list-closers and discourse filler.** `and so on` was deleted twice; `In this
direction,` was deleted.

```
✗  significant sleep disorder (e.g., RBD, OSA, PLMS, RLS, and so on)
✓  a significant sleep disorder (e.g., RBD, OSA, PLMS, RLS)
```

**`Firstly / Secondly / Thirdly` → `first / second / third`,** and the enumerated fragments
become one semicolon-chained sentence:

```
✗  It might be due to these following reasons. Firstly, some subtle behaviors might be
   ignored ... Secondly, the clinical meaning for RSWA was elusive ... Thirdly, RSWA could
   develop into RBD, but, by chances, it was not happened ...
✓  This result might have occurred due to the following reasons: first, some subtle
   behaviors might have been ignored ...; second, because the clinical significance of RSWA
   is still unclear, RSWA might simply be an unusual PSG finding ...; third, it is possible
   that RSWA can develop into RBD, but this did not occur in the current study ...
```

**Use the statistical term, not the loose one.** `statistical difference` → `significant
difference` throughout; `latter 3 visits` → `last 3 visits` (`latter` means the second of
two, not the last of several).

**Generic drug names are lowercase mid-sentence:** `Sertraline` → `sertraline`.

---

## 10. Concision — and what it is not

Concision here means removing words that carry no information, never removing content.

```
✗  the extent of increased PLMI increment      ✓  the extent to which the PLMI scores increased
✗  the percentages of in each stage            ✓  the percentages of time spent in each stage
✗  blood analysis, and urinary analysis        ✓  blood and urine analyses
✗  Written informed consents were signed prior to participation
✓  Written informed consent was obtained from each patient prior to participation
```

The last one is *longer* than the original. It was still the right edit: `consents were
signed` obscures who consented, and the reporting convention is that consent is *obtained*.
Do not treat word count as the objective — see `references/editor-queries.md` on editing
intensity when a word limit is genuinely binding.

---

## 11. Claim strength

Adjust hedging in **both** directions, and let the evidence decide which:

| Original | Edited | Why |
|---|---|---|
| `these results supported that SSRIs could induce` | `these results support the notion that SSRIs can induce` | a result supports a *notion*, not a clause; present tense for the standing claim |
| `so the mechanisms should be different` | `the mechanisms are likely different` | `should` misused as inference; `likely` states the actual epistemic status |
| `It might be supported by some risk factors` | `This notion might be supported by certain risk factors` | dangling `It` given a referent |
| `SSRIs-related RBD is usually ignored by most physicians` | `SSRI-related RBD is ignored by most physicians` | **hedge removed** — `usually` + `most` double-hedges the same claim |
| `should be serious public problem` | `should be considered a serious public health problem` | a recommendation, marked as one |

The fourth row is the one that surprises people: raising register sometimes means deleting
a hedge, because two hedges on one claim read as evasion, not caution.

---

## 12. Spelling, and the words this sample actually got wrong

US spelling throughout (`Centre` → `Center`). Genuine misspellings corrected silently:
`sepctrum` → `spectrum`, `Boferrroni` → `Bonferroni`, `postsysnaptic` → `postsynaptic`,
`ploysomnography` → `polysomnography`, `standard derivation` → `standard deviation`,
`non non-REM` → `non-REM`, `out-patient` → `outpatient`, `bed-partners` → `bed partners`,
`cut-offs` → `cutoffs`, `REFERENCE` → `REFERENCES`.

`standard derivation` → `standard deviation` is worth pausing on. It looks like a science
edit and is not: `derivation` is not a statistic, so the word was simply wrong. The value it
labels was not touched.

---

## 13. Where the sample is inconsistent — do not manufacture a rule

Three places where the editor did **not** apply a global rule. Copying a "rule" from these
would mean making changes the reference edit did not make:

1. **`±` spacing.** `216.4% ± 53.9%` was closed to `216.4%±53.9%` in one body paragraph,
   while dozens of mixed-spacing table cells were left untouched.
2. **`p` vs `P`.** `adjusted p values (significant at P=0.005)` became `adjusted P-values
   (significant at P=0.005)` — consistent *within that sentence* — while `p=0.004` and
   `p=0.03` elsewhere stayed lowercase.
3. **Scale-name capitalization.** `Hamilton Rating Scale for Depression` was capitalized in
   the Figure 1 legend but left lowercase in the Table 2 footnote list.

The operative rule in all three is **local consistency**: make a passage internally
consistent, and raise the global choice as a query rather than sweeping it. The
deterministic checker (`scripts/manuscript_check.py`) reports these splits precisely so
that the decision reaches the author instead of being made silently.
