# Reporting Conventions

Numerals, time points, units, statistics, tables and figures, abbreviations, headings and
front matter. These are the rules a copy editor applies mechanically; the deterministic
checker (`scripts/manuscript_check.py`) finds most of the violations, and this file says
what to do about each. Corpus as before: the AJE Premium reference edit.

---

## 1. Numerals

**Spell out a number that opens a sentence, or recast the sentence so it does not.** The
sample used both strategies:

```
✓  Fifty-five patients with major depressive disorder were initially enrolled   [spelled out]
✓  Thirty-second Epoch                    (from `30-second Epoch`)              [spelled out]
✗  50 mg of sertraline was administered at 8 am on the 1st day.
✓  On the 1st day, 50 mg of sertraline was administered at 8 am.                [recast]
```

Recasting is preferred when spelling out would produce something unreadable
(`Fifty milligrams of sertraline`). Never spell out a dose.

**Use numerals for everything measured**: `n=31`, `4 visits`, `8 weeks`, `3 patients`,
`200 mg/day`, `18%`.

**A count and its noun agree in specificity.** `Among these 38 patients` →
`Among the 38 remaining patients`; `Nine patients discontinued ... Of these 9, 5 patients
discontinued before the 14th day` — the inserted `Of these 9` makes the arithmetic
checkable.

---

## 2. Study time points

Two conventions coexist, and the sample chose between them by context:

| Context | Form | Example |
|---|---|---|
| Enumerated list of visits | `days 1, 14, 28, and 56` | `At baseline and during 4 visits (days 1, 14, 28, and 56)` |
| Running prose about one time point | ordinal, with `the` | `on the 14th day of treatment`, `the 1st day vPSG assessment` |
| A span | `between the Xth and Yth day` | `discontinued between the 14th and 28th day` |
| Axis labels and legends | `days 1, 14, 28, and 56` | `x axis: baseline and days 1, 14, 28, and 56` |

`during the 14th - 28th day` → `between the 14th and 28th day`. A hyphen or dash is not a
range preposition in prose.

**Close up the ordinal:** `the 14thday` → `the 14th day`. **Times keep their format:**
`8 am`, `4 pm`, `8 pm` (unspaced-lowercase in this sample; whatever the journal uses,
be consistent).

---

## 3. Units and operators

```
✗  200mg/dayof sertraline           ✓  200 mg/day of sertraline
✗  100mg at 8 am                    ✓  100 mg at 8 am
✗  (> 18%)                          ✓  (>18%)
✗  (r =0.56, p=0.004)               ✓  (r=0.56, p=0.004)
```

- **A space between the value and the unit**, always: `50 mg`, `180 seconds`, `30 minutes`.
- **Comparison operators inside parentheses are closed up**: `(>18%)`, `(<30 minutes)`,
  `(HRSD-sleep disturbance score <3)`.
- **Outside parentheses the sample left `≥` spaced**: `scores ≥ 18`, `PLMI ≥ 15`,
  `(≥ 3 groups)`. This is an inconsistency in the corpus, not a rule — see
  `language-mechanics.md` §13. Make a passage internally consistent and query the global
  choice; do not sweep the whole manuscript on your own authority.
- **`±` is set closed in the passage the editor rewrote** (`216.4%±53.9%`) and left spaced
  elsewhere (`32.7±9.2 years old`, `12.0%±4.3%`). Same treatment: local consistency, global
  query.

---

## 4. Statistics

**Terminology.** `statistical difference` → `significant difference`, everywhere. A
difference is *significant*; the test is *statistical*.

**Test names.** Article + lowercase common noun, hyphen where the eponym is compound:

```
✗  Chi-square test was used            ✓  The chi-square test was used
✗  Kruskal Wallis Test                 ✓  Kruskal-Wallis test
✗  independent t-test                  ✓  the independent t-test
✗  A one-way analysis of variance (ANOVA) and Kruskal Wallis Test were performed
✓  One-way analysis of variance (ANOVA) and Kruskal Wallis tests were performed
```

**`p` vs `P`.** The sample wrote `adjusted P-values (significant at P=0.005)` in one
sentence while leaving `p=0.004` elsewhere. Pick the journal's convention, apply it
throughout, and *tell the author you did* — a silent global case change to a statistical
symbol looks, in tracked changes, exactly like an edit to a result.

**Never touch a reported value.** Not the numeral, not the unit, not the rounding, not the
sign. `r=0.56`, `p=0.004`, `216.4%±53.9%`, `n=31`, `χ2=1.44` are invariants. You may
re-space them, re-attach them to the noun they quantify, and repair the grammar around them:

```
✗  The reducing score rate of tonic RSWA s(216.4% ± 53.9%) correlated positively with ...
✓  The change in tonic RSWA score (216.4%±53.9%) was positively correlated with ...
```

Every digit survived. Only the words moved. Where a *label* for the values had to change —
`reducing score rates` → `changes`, because some of the values were increases — the editor
made the change **and raised a query about it**. Relabelling a quantity is the boundary
case: do it only with a query attached (`references/editor-queries.md`).

**Descriptions of the statistic go in the present tense** when they describe the paper:
`The data are presented as the mean ± standard deviation`.

---

## 5. Tables and figures

**Cite them capitalized and numbered**: `table 2` → `Table 2`, `figure 2 a-c` →
`Figure 2 a-c`, `(table 3 & figure 2 a-c)` → `(Table 3 & Figure 2 a-c)`.

**Caption verbs are present tense and specific**: `This recruitment process was shown in
Figure 1` → `The recruitment process is illustrated in Figure 1`; `Flow diagram documenting
recruitment` → `Flow diagram illustrating the recruitment`.

**A caption names what changed, over what, in whom:**

```
✗  Table 2. Clinical and polysomnographic measures across the sertraline treatment in
   depressed patients
✓  Table 2. Changes in clinical and polysomnographic measures during sertraline treatment
   of depressed patients

✗  Table 4. Percentages of epochs with tonic and phasic RSWA between single type and
   recurrent type across the sertraline treatment in of depressed patients
✓  Table 4. Percentages of epochs with tonic and phasic RSWA in patients with single and
   recurrent depression undergoing sertraline treatment
```

`across the treatment` → `during treatment`; `between single type and recurrent type` →
`in patients with single and recurrent depression` (the comparison is between *patients*,
not between *types* — see `language-mechanics.md` §6).

**Row and column labels**: sentence case, capital initial.
`% stage 3` → `% Stage 3`; `REM Latency (min)` → `REM latency (min)`;
`clinical characteristics` → `Clinical characteristics`; `Single type` → `Single`.

**Notes and footnotes are sentences and take a full stop**:
`RSWA: REM sleep with atonia` → `RSWA: REM sleep with atonia.`;
`F: ANOVA, KW: Kruskal Wallis Test` → `F: ANOVA, KW: Kruskal-Wallis test.`

**Footnote definition lists are made internally consistent**, not globally reformatted. In
the Table 2 footnote only `SE: Sleep Efficiency` → `sleep efficiency` and `SL: Sleep
Latency` → `sleep latency` changed — the two entries that disagreed with their fourteen
neighbours. The neighbours were left alone.

**Axis descriptions take a colon, not a comma:**
`(x axis, baseline, the 1st day, the 14th day, ...)` →
`(x axis: baseline and days 1, 14, 28, and 56)`.

**Heading for the legend block**: `Legend of the figures` → `Figure legends`.

---

## 6. Abbreviations

- **Expand at first use in the abstract and again at first use in the body**, then use the
  abbreviation exclusively.
- **The expansion is lowercase unless it is a proper name**:
  `Electroencephalograph [EEG]` → `electroencephalograph [EEG]`;
  `Computed Tomography [CT]` → `computed tomography [CT]`;
  but `Diagnostic and Statistical Manual of Mental Disorders, Fourth Edition (DSM-IV)` and
  `Hamilton Rating Scale for Depression (HRSD)` keep their capitals — they are titles.
- **A named instrument becomes a technique when it names a recording**:
  `an electrooculograph (EOG)` → `electrooculography (EOG)`,
  `a submental electromyograph (EMG)` → `submental electromyography (EMG)`.
- **An abbreviation defined but never used again is a defect**, and so is one used before it
  is defined. The checker reports both; fix by deleting the unused definition or expanding
  at the true first use.
- **Do not invent an abbreviation** the author did not define.

---

## 7. Headings and front matter

- **Section headings take title case** when the manuscript's other headings do:
  `2.4. Data analysis` → `2.4. Data Analysis`; `3.1. Recruitment process` →
  `3.1. Recruitment Process`; `3.2. Demographic and clinical characteristics` →
  `3.2. Demographic and Clinical Characteristics`. Match the manuscript's own dominant
  pattern rather than imposing one.
- **`REFERENCE` → `REFERENCES`.**
- **Word-count statements are never recalculated by the editor.** The sample's word-count
  line was left byte-identical and carried a query instead: *"Please perform a new word
  count after our edits and suggestions have been considered."* Do the same — you cannot
  know the count after the author accepts a subset of the changes.
- **Funding statements name the instrument and the recipient**:

```
✗  The work was supported by the Investigator-Initiated Research (IIR) from Pfizer Pharma,
   (Study Code: WS458774) to Dr. Bin Zhang and the National Natural Science Foundation of
   China (Grant No: 30800303) to Dr. Bin Zhang.
✓  The work was supported by an Investigator-Initiated Research (IIR) Program grant from
   Pfizer Pharma (Study Code: WS458774) and a grant from the National Natural Science
   Foundation of China (Grant No: 30800303), both awarded to Dr. Bin Zhang.
```

The repeated recipient was collapsed to `both awarded to`; the grant numbers, the funder
names and the study code are untouched.

- **Ethics and consent statements use the conventional verbs**:
  `Written informed consents were signed prior to participation` →
  `Written informed consent was obtained from each patient prior to participation`.
  Do not add an approval number, a country or a date the manuscript does not contain —
  query for it. The sample's missing ethics-approval number drew no comment and no
  invention.

- **Manufacturer attributions**: correct the format of what is present
  (`SPSS, Inc` → `SPSS, Inc.`) and **query** for what is missing (`Chicago, IL` was left
  without `USA`, with a comment asking for full location information). This is the sharpest
  line in the whole corpus: the editor knew the country and still refused to write it.
