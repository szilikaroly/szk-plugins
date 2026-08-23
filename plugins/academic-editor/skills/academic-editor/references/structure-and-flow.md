# Structure and Flow

Sentence architecture, punctuation that carries logic, and how paragraphs are built section
by section. Same corpus as `language-mechanics.md`: the AJE Premium reference edit, 61
changed paragraphs. Examples are the actual before/after pairs.

---

## 1. Splitting and joining

Neither is automatic. The sample splits a sentence when it carries two propositions, and
joins two when they carry one.

**Split a sentence that has smuggled in a second claim:**

```
✗  The selective serotonin (5-HT) reuptake inhibitors (SSRIs) are the first-line
   antidepressants; in recent decades, and their potential effect on RSWA can be suspected
   from basic knowledge on muscle atonia during REM sleep.
✓  In recent decades, selective serotonin (5-HT) reuptake inhibitors (SSRIs) have become
   first-line antidepressants, and they are suspected to exert effects on RSWA based on
   basic knowledge of muscle atonia during REM sleep.
```

**Split when a subordinate clause has grown its own subject and verb:**

```
✗  Serotonergic neurons descending to the nuclei of cranial nerves and to the lower motor
   neurons reduce their firing, the disfacilitation of the neurons during non-REM sleep,
   and cease firing during REM sleep
✓  During non-REM sleep, the firing of serotonergic neurons descending to the nuclei of the
   cranial nerves and to the lower motor neurons is reduced, leading to disfacilitation;
   during REM sleep, the firing of serotonergic neurons ceases
```

Two time frames, two clauses, one semicolon. The original tried to hold both in a single
predicate and lost the second one.

**Join when two sentences state one fact:**

```
✗  All computerized sleep data were further edited by an experienced PSG technologist, and
   this technologist was blinded to this study.
✓  All computerized sleep data were further edited by an experienced blinded PSG technologist.

✓  Some caution should be exercised in interpreting the results reported here. First, a
   placebo control group was not used in this study. Second, the sample size in this study
   was small.
```

The second example was *not* joined — three short sentences survived intact, because
limitations are read as a list. Sentence length is not the criterion; propositional load is.

---

## 2. Colons, semicolons, commas

**Colon introduces the list or definition that follows.** A full stop between the
introduction and the list is the error:

```
✗  Phasic muscle activity during REM sleep was defined by following criteria. In a 30-second
   epoch of REM sleep divided into 10 sequential, 3-second mini-epochs, at least 5 (50%) ...
✓  Phasic muscle activity during REM sleep was defined by following criteria: in a 30-second
   epoch of REM sleep divided into 10 sequential, 3-second mini-epochs, at least 5 (50%) ...

✗  The nocturnal vPSG basic recordings included a standard EEG (F4-A1, ...), an
   electrooculograph ...
✓  The nocturnal vPSG included the following basic recordings: standard EEG (F4-A1, ...),
   electrooculography (EOG: LE-A2, RE-A1), ...
```

Note what else changed there: once the colon carries "the following", the repeated `a/an`
before each list member goes, and the instrument names shift from the device
(`electrooculograph`) to the technique (`electrooculography`) — the thing a recording is
actually made *by*.

**Semicolon joins two independent clauses that belong to one thought**, and separates list
members that already contain commas:

```
✓  Then, the dose was titrated according to the clinical efficacy and side effects; the
   maximum dosage was 200 mg/day.
✓  The percentage of stage 1 sleep decreased during the trial; it was significantly lower on
   the 28th and 56th days than on the 1st day and at baseline.
✓  ... first, some subtle behaviors might have been ignored ...; second, because the
   clinical significance of RSWA is still unclear ...; third, it is possible that ...
```

**Comma before `respectively`, and place it where the correspondence is readable:**

```
✗  the TST and SE became longer and higher than the baseline or 1st day respectively
✓  the TSTs and SEs became longer and higher, respectively, compared with those at baseline
   or on the 1st day

✗  were 5.8% and 3.8% respectively
✓  were 5.8% and 3.8%, respectively
```

**Serial comma before the final `and`** in a list of three or more:
`3 patients were diagnosed with significant OSA, and 4 patients were diagnosed with
significant PLMS`; `days 1, 14, 28, and 56`.

---

## 3. Information order — frame first, new last

The most repeated structural move in the sample: what the sentence is *measured against*
goes to the front, and what the reader does not yet know goes to the end.

```
✗  these patients are of younger age ... compared to the RBD patients in the general population
✓  compared with RBD patients in the general population, psychiatric outpatients with RBD
   were younger in age ...

✗  Sertraline exacerbated RSWA during the current study, but did not induced RBD.
✓  In the current study, sertraline exacerbated RSWA but did not induce RBD.

✗  50 mg of sertraline was administered at 8 am on the 1st day.
✓  On the 1st day, 50 mg of sertraline was administered at 8 am.

✗  Compared with baseline, PLMI increased as soon as the administration of sertraline on the 1st day.
✓  Compared with their levels at baseline, the PLMI scores increased immediately after
   sertraline administration on the 1st day.
```

The third one does double duty: fronting the time frame also stops the sentence from
beginning with a numeral. See `reporting-conventions.md` §Numerals.

**Given information links back; new information lands at the end.** Compare the two versions
of a Discussion opening:

```
✗  The results of phasic RSWA were not consistent within Winkelman's study to some extent.
   In Winkelman's study, compared with normal control, increased subjects taking
   serotonergic antidepressants only had significantly tonic RSWA ...
✓  To some extent, the phasic RSWA results were inconsistent with those described by
   Winkelman and James. In that study, only tonic RSWA was significantly altered in subjects
   taking serotonergic antidepressants compared with normal controls ...
```

`In that study` picks up the study just named, so the reader is never asked to hold two
unlinked topics at once.

---

## 4. Connectives

The sample's connective inventory, and what each one signals. Use them because the relation
is true, not to decorate the seam between sentences.

| Connective | Signals | In the sample |
|---|---|---|
| `However,` | contrast with what precedes | `However, no patients reported abnormal behaviors related to RBD` |
| `Further,` | an additional point of the same kind | `Further, these patients were assessed by vPSG in three subsequent visits` |
| `Moreover,` | a stronger additional point | `Moreover, an average of 39% of patients ... experienced tonic RSWA` |
| `Additionally,` | a parallel finding | `Additionally, RSWA was more common in patients with multiple systemic atrophy` |
| `In addition,` | an addition to a mechanism just described | `In addition to this passive mechanism, active paralysis ... occurs` |
| `Notably,` | the reader should stop here | `Notably, depression is a common mental disorder` |
| `Indeed,` | evidence for the claim just made | `Indeed, two subjects were taking bupropion` |
| `Thus,` | consequence | `Thus, SSRI-related RSWA should be considered a serious public health problem` |
| `In summary,` | closing a stretch of argument | `In summary, these results support the notion that ...` |
| `In other words,` | restating for precision | `In other words, the potential adverse effects ... might be outweighed` |

`In this direction,` was **deleted** — it signalled nothing. If you cannot name the relation
a connective encodes, the connective is filler.

---

## 5. Paragraph architecture by section

### Abstract
One structural move only: make each sentence carry one finding, in the order
question → design → what was measured → what happened → what it means. The sample's abstract
edits were sentence-level; the paragraph was not restructured. Do not re-architect an
abstract that already reports in that order.

### Introduction
Funnel: field → what is known → what is not known → why the gap matters → this study's
purpose. The sample's Introduction closes exactly there:

```
✗  The main purpose of this study is to characterize the effect of sertraline on RSWA in
   depressed patients in 8-week clinical trial with repeated video-ploysomnography assessment.
✓  The main purpose of this study was to characterize the effect of sertraline on RSWA in
   depressed patients in an 8-week clinical trial using repeated video-polysomnography
   (vPSG) assessment.
```

Past tense — the purpose was fixed before the study ran.

The paragraph before it earns that close by stating the gap and the reason it matters, in
that order:

```
✓  However, most of these studies were retrospective, cross-sectional studies with small
   sample sizes, and the subjects received a mixture of SSRIs. It is well known that all
   SSRIs do not have the same pharmacological profiles; thus, different SSRIs might have
   different tendencies to induce RSWA. With this in mind, the specific effects of
   individual SSRIs on RSWA should be studied.
```

### Methods
Chronological, one procedure per paragraph, each paragraph opening with the procedure it
describes. Where the original buried the procedure behind a circumstance, the edit hoists it:

```
✗  According to the nocturnal vPSG, the basic recordings included ...
✓  The nocturnal vPSG included the following basic recordings: ...
```

Design → participants and eligibility → intervention and schedule → measurements →
scoring/definitions → analysis. Do not let an eligibility criterion appear for the first
time in Results.

### Results
Each paragraph takes one outcome family and reports it in a fixed rhythm: what was compared,
what happened, at which time points, with the pointer to the table or figure last.

```
✓  There were no significant differences in TRTs during the trial. From the 14th day onward,
   the TSTs and SEs became longer and higher, respectively, compared with those at baseline
   or on the 1st day. ... During the daytime assessment (MSLT), the mean SL remained stable
   during the trial (Table 2).
```

No interpretation. `which could evoke clinical RBD` → `that could indicate clinical RBD`:
an observation may *indicate*, it does not *evoke*.

### Discussion
Opens by restating the principal finding in the frame of this study, then compares with
prior work, then explains discrepancies, then limitations, then implications.

```
✓  In the current study, sertraline exacerbated RSWA but did not induce RBD. [finding]
   To some extent, the phasic RSWA results were inconsistent with those described by
   Winkelman and James. [comparison]
   This difference might be due to the small sample size (n=15) and mixture of
   antidepressants used in the study performed by Winkelman and James. [explanation]
   In summary, these results support the notion that SSRIs can induce or exacerbate RSWA
   ... [closure]
```

Alternative explanations are enumerated, not narrated — the `first / second / third`
semicolon chain in `language-mechanics.md` §9 is the sample's model for that.

### Conclusion
No new information, and every claim traceable to a Result. The sample's conclusion was
rebuilt to separate the finding from the inference:

```
✗  although the sertraline-induced RSWA seems not to have significant clinical disturbance
   and no overt RBD was found in current study, regarding observations RBD being greater
   prevalent in patients with the usage of antidepressants than the general population, the
   antidepressant-related RSWA should be potential public health problem in the depressed patients.
✓  Further, sertraline-induced RSWA did not cause significant clinical disturbance, and
   overt RBD was not observed in the current study. Despite these findings, the increased
   prevalence of RBD in patients using antidepressants compared with that in the general
   population indicates that antidepressant-related RSWA is a potential public health issue
   for depressed patients.
```

One 60-word sentence carrying a finding *and* a counter-inference became two: the finding,
then the inference marked as one.

---

## 6. Cohesion devices

- **Repeat the term; do not elegantly vary it.** `RSWA` stays `RSWA` throughout. Synonym
  variation in a scientific text reads as a new referent.
- **Give every `it`, `this` and `these` a visible antecedent.** `It might be supported by` →
  `This notion might be supported by`. Where the referent is a whole preceding clause, name
  it: `This result might have occurred due to ...`, `This difference might be due to ...`,
  `These prevalences are ten times higher ...`.
- **Number the members of a set once and keep the count.** `Nine patients discontinued
  treatment ... Of these 9, 5 patients discontinued before the 14th day ...` — the inserted
  `Of these 9` is what lets the reader verify 5 + 1 + 3 = 9 without re-reading.
