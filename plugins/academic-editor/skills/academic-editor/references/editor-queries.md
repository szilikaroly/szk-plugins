# Editorial Protocol: Prohibitions, Queries and Editing Intensity

This file governs when you stop editing and speak to the author. In the reference edit, 60
paragraphs were changed and only 8 carried any comment — 11 comments across ~900 tracked
operations. Comments are scarce because they are the signal that the editor made a decision only the
author can ratify. Everything below is derived from that sample and verified against it.

## The line the editor never crosses

### Reproduce every reported value exactly

Never change, recompute, round, correct or delete a numeral, unit value, mean±SD, r, p, n, %, dose,
sample size or time point. You may re-space it, re-attach it to the noun it actually quantifies, and
repair the grammar of the reporting sentence around it.

```
✗  Only a few patients took 200mg/dayof sertraline (2 patients in the 28th day and 1 patient in the 56th day)
✓  Only a few patients received a sertraline dose of 200 mg/day (2 patients on the 28th day and 1 patient on the 56th day)
```

Across the whole sample not one reported value was altered — including the one whose referent the
editor did reassign (39% of *patients*, not 39% *of RSWA*), and that reassignment was queried.

Not when: the change is purely typographic inside a comparison operator — `(> 18%)` → `(>18%)` was
applied consistently. Do not extend this to ± spacing; the editor closed `216.4% ± 53.9%` in one body
paragraph and left dozens of mixed-spacing table cells untouched.

### Treat the paragraph's citation set as invariant — reposition, never multiply

You may move a citation to the clause it actually supports and normalize its punctuation. You may
never add one, including to support a statement you have just sharpened, and never delete one. The
identity and count of citations in the edited text must equal those in the original.

```
✗  In this direction,a mean of  the amount of tonic RSWA was observed in patients with idiopathic and PD-associated RBD  is a mean 39%, which is large than the 12% found in our study (Iranzo et al., 2005).
✓  Moreover, an average of 39% of patients with idiopathic and PD-associated RBD experienced tonic RSWA in a previous study (Iranzo et al., 2005), which is greater than the 12% found in our study.
```

### Never insert a fact the author did not supply, even one that is certain

This is the sharpest demonstration of the boundary in the sample: the editor corrected `Inc` to
`Inc.` and still refused to write `USA` after `Chicago, IL`, asking for it in a comment instead.
Correct the format of what is there; query for what is missing.

```
✗  All statistical procedures were performed by using Statistical Package for the Social Sciences 17.0 for Windows (SPSS, Inc, Chicago, IL).
✓  All statistical procedures were performed using the Statistical Package for the Social Sciences 17.0 for Windows (SPSS, Inc., Chicago, IL).
```

The same prohibition covers author names: extend a narrative mention only to a form verifiable from
the manuscript's own citations (`Winkelman's study` → `the study performed by Winkelman and James`,
because the citation reads `(Winkelman and James, 2004)`). Never invent a co-author.

Not when: the missing item is not a manufacturer address. A missing ethics-approval number in the
same manuscript drew no comment at all, and the SPSS version number drew no version query. Do not
generalize this query to every gap you notice.

### Leave reference-list entries exactly as supplied

Do not touch spelling, author-name formatting, capitalization, journal abbreviation, page ranges or
publisher details in the reference list — the entries are reference-manager output and the style is
journal-determined. All 35 entries were passed through untouched, including a plain typo.

```
✗  MURRAY, D. J., LOPEZ, A.D. 1996. The global burden of disease: a comprehensive assessment of morality and disability from diseases, injuries, and risk factors in 1990 and projected to 2020. , Cambridge, MA, Harvard Schoo
✓  MURRAY, D. J., LOPEZ, A.D. 1996. The global burden of disease: a comprehensive assessment of morality and disability from diseases, injuries, and risk factors in 1990 and projected to 2020. , Cambridge, MA, Harvard Schoo
```

`morality` (for `mortality`) and the stray `. ,` both survived. The section heading is fair game:
`REFERENCE` → `REFERENCES`. So are narrative mentions of cited authors inside the body text.

### Never strengthen a claim past the data — flatten a modal only on the study's own observed result

You may convert a hedged statement of what *this study* observed into a flat past-tense assertion,
because the result is reported in the same manuscript. You may not upgrade an inference, a mechanism,
a speculation, or another study's finding.

```
✗  Sertraline could induce or exacerbate RSWA, but did not induce RBD.
✓  Sertraline induced or exacerbated RSWA but did not induce RBD.
```

Not when: the sentence is explanatory or speculative. `RSWA might simply be an unusual PSG finding
and may not develop into overt clinical RBD` kept both modals inside an otherwise heavily rebuilt
clause. Never convert correlation into causation, and never delete a limitation or a caveat.

### Delete only from the permitted classes, and never to hit a word count

Remove text without replacement only when it is (a) a word already carried by the same sentence,
(b) a vague list-extender (`and so on`, `such as:`), (c) a second hedge or intensifier stacked on one
that already does the work, (d) a magnitude qualifier contradicted by the statistic beside it, or
(e) a modal on the study's own observed result. Never delete a proposition, a citation, a limitation
or a number, and never trim substantive content to meet a limit without flagging it.

```
✗  if they currently had significant sleep disorder (e.g., RBD, obstructive sleep apnea [OSA], periodic limb movement during sleep [PLMS], restless legs syndrome [RLS], and so on); or if they had a serious medical condition
✓  if they currently had a significant sleep disorder (e.g., RBD, obstructive sleep apnea [OSA], periodic limb movement during sleep [PLMS], restless legs syndrome [RLS]), or if they had a serious medical condition
```

If a hard word limit forces cuts beyond these classes, propose them in a comment and let the author
decide; do not execute them silently.

### Leave the author's declared counts and placeholder blocks untouched

The front-matter word/figure/table count is the author's declaration to the journal, and any number
you compute mid-pass is wrong again by the end of it. Placeholder blocks encode intended display-item
positions and are production instructions, not prose.

```
✗  Word Count: 4480 words (main body) with 2 figures and 4 tables
✓  Word Count: 4480 words (main body) with 2 figures and 4 tables
```

Unchanged, with the re-count request anchored on `4480` as the first comment in the document. The
same holds for `Insert Figure 2 a-c` and its dashed rules: passed through verbatim, even though the
in-text callout `figure 2 a-c` was capitalized to `Figure 2 a-c`.

## When to query instead of edit

### Query only when your repair supplied meaning the source did not determine

Attach a meaning-maintenance query when your edit does one of exactly three things to a claim that
was already grammatically well formed: changes what a reported number is a claim about; introduces a
definitional relation the author never stated; or imposes a causal connective plus a new qualifier on
a speculative explanation. All five instances in the sample are of this kind.

```
✗  A similar profile was observed for phasic RSWA and for the proportion of patients with abnormal phasic anterior tibialis.
✓  A similar profile was observed for phasic RSWA as well as for the proportion of patients with abnormal phasic anterior tibialis RSWA.
```

The elided head noun `RSWA` is the editor's supply, not the author's, so the comment lands on
`abnormal phasic anterior tibialis RSWA`. Same trigger, definitional variant:

```
✗  Because the recurrent major depression (up to 7 episodes in the study) should share some biological and clinical aspects
✓  Because recurrent major depression (defined as up to 7 episodes in this study) should share some biological and clinical features
```

Not when: you merely re-linearized propositions all present in the source. Length of the rewrite is
irrelevant to the decision.

### Restructure silently — volume of rewriting never earns a comment

If you can rebuild the sentence from material already in the source (re-ordering, voice change,
splitting run-ons, agreement, repairing half-applied revisions), make the change with tracked changes
and no comment, however violent the rewrite. The most heavily rebuilt paragraphs in the sample carry
no comment at all.

```
✗  Serotonergic neurons descending to the nuclei of cranial nerves and to the lower motor neurons reduce their firing, the disfacilitat ofing the neurons during non non-REM sleep, and cease firing during REM sleep (Siegel, 2006).
✓  During non-REM sleep, the firing of serotonergic neurons descending to the nuclei of the cranial nerves and to the lower motor neurons is reduced, leading to disfacilitation; during REM sleep, the firing of serotonergic neurons ceases (Siegel, 2006).
```

A paragraph can be rebuilt end to end and still carry a comment on one span inside it — the comment
belongs to the span, not to the paragraph.

### Never query a garble — repair it on your best reading and move on

Text that is run together, doubled by an un-accepted earlier revision, or self-contradictory at the
surface is a mechanical defect. Reconstruct the intended string and fix it, with no comment, even
when the reconstruction is a judgement call.

```
✗  Similar to the 1st day, sertraline usually was administered at 8 am during this clinical trial except for ofsignificant sedation and dosages of 200 mg/day.
✓  Similar to the 1st day, sertraline was usually administered at 8 am throughout the clinical trial, except for cases in which the patient was significantly sedated or was receiving a dosage of 200 mg/day.
```

That edit turned *and* into *or* — a logical change — and still drew no comment. The same silence
covers `no lessconcurrent neurodegenerative diseases` → `had fewer concurrent neurodegenerative
diseases`, where the editor resolved to the reading opposite the literal one. Queries are reserved
for text that parses cleanly and supports two different scientific claims.

### When the readings assert different science, refuse to choose

If picking a reading would commit the manuscript to a different scientific claim — co-administration
versus adverse interaction, a marker *reflecting* a mechanism versus *participating in* it — leave
the author's phrasing, apply mechanical fixes only, and offer the alternatives as complete,
paste-ready text.

```
✗  (2 due to worsening symptoms and combination with other drugs; 1 due to gastrointestinal side effect;
✓  (2 due to worsening symptoms and combinations with other drugs, 1 due to a gastrointestinal side effect,
```

Only the plural `-s` was applied; the phrase itself was left alone under the comment *Your intended
meaning is somewhat unclear. Did you mean “negative interactions with other drugs”?*

Not when: one reading is merely more idiomatic than the other. Then edit to it and use the
meaning-maintenance formula instead.

### Query a sweep once, at its first instance

When you replace the same author term more than twice in a paragraph or section, make every
replacement and explain it in one comment anchored on the first. Never comment per instance.

```
✗  no significant correlations were shown between the reducing score rates ofin RSWA and continuous demographic and clinical characteristics (such as: age) at the baseline
✓  no significant correlations were observed between the changes in RSWA scores and continuous demographic and clinical characteristics, such as age at baseline
```

`reducing score rates` → `changes` was applied throughout that paragraph under a single note. Where
the same substitution recurred elsewhere with fewer instances, the generic meaning-maintenance
formula was used instead.

### Query a convention breach only when honouring it would make you write authorial content

Expanding an abbreviation, or choosing where its definition belongs, commits you to a fact and a
placement decision that belong to the author and the target journal. State the convention and leave
the text alone.

```
✗  The increase of tonic muscle tone during REM sleep over time correlated with reduced REM sleep Latency (r=0.56, p=0.004), PLMI (r =0.39, p=0.047)
✓  The increase in tonic muscle tone during REM sleep over time was correlated with reduced REM sleep latency (r=0.56, p=0.004), PLMI (r =0.39, p=0.047)
```

`PLMI` — the first undefined acronym in the abstract — was left unexpanded and carries the
abbreviation-convention comment. Casing, agreement and punctuation in the same span were still fixed
silently.

Not when: the convention is one this protocol does not evidence. Abbreviations and manufacturer
location are the only two convention queries in the sample; a missing ethics-approval number went
unremarked.

## Query templates

Use these verbatim. The wording is the AJE original; only the slots change.

### Ask for meaning maintenance after supplying meaning

One sentence, no elaboration, no account of what you changed. The anchor tells the author which
decision to check.

```
Please ensure that the intended meaning has been maintained in this edit.
```

```
✗  The correlations between the reducing reduced score rates of the clinical and polysomnographic measures and the reducing reduced score rates of tonic and phasic EMG activities during REM sleep were performed using the Pearson test.
✓  Correlations between changes in the clinical and polysomnographic measures and changes in tonic and phasic EMG activities during REM sleep were determined using the Pearson test.
```

### Offer the ambiguous reading as paste-ready text, not as a description

One option when a single reading is in doubt, two when they compete. Options go in typographic
quotation marks and must be complete replacement wording the author can paste.

```
Your intended meaning is somewhat unclear. Did you mean “<complete alternative wording>”?

Your intended meaning is slightly unclear. Did you mean “<complete wording A>” or “<complete wording B>”?
```

```
✗  Did you mean that the drugs interacted badly?
✓  Your intended meaning is somewhat unclear. Did you mean “negative interactions with other drugs”?
```

The two-option form as delivered: *Did you mean “Thus, RSWA, PLMS, REM latency, and HRSD scores might
reflect the mechanisms of 5-HT and/or DA neurotransmission to some extent” or “Thus, RSWA, PLMS, REM
latency, and HRSD might be involved in the mechanisms of 5-HT and/or DA neurotransmission to some
extent”?*

### Explain a global change once, in four parts

Old and new wording in quotation marks; the scope of the sweep; the reason expressed as an
observation about the author's apparent intent; a request to check.

```
Note that the phrase “<old>” was changed to the word “<new>” throughout this paragraph because you appear to be describing <observation>. Please check the changes made throughout this paragraph carefully.
```

```
✗  "Reducing score rates" is wrong here — several of these values increased, so I changed it.
✓  Note that the phrase “reducing score rates” was changed to the word “changes” throughout this paragraph because you appear to be describing changes in general (some of which are increases) rather than reductions. Please check the changes made throughout this paragraph carefully.
```

### Ask for manufacturer location rather than completing the address

Anchor on the supplier string, after correcting its punctuation.

```
Please consider including full location information (including city, state, and country) for all manufacturers of specialized software, equipment, and reagents.
```

```
✗  (SPSS, Inc, Chicago, IL)
✓  (SPSS, Inc., Chicago, IL)
```

### State the abbreviation convention impersonally

Anchor on the first undefined acronym token only — one comment, not one per acronym.

```
Abbreviations and acronyms are often defined the first time they are used within the abstract and again in the main text and then used throughout the remainder of the manuscript. Please consider adhering to this convention.
```

```
✗  Please define PLMI at first use, as required.
✓  Abbreviations and acronyms are often defined the first time they are used within the abstract and again in the main text and then used throughout the remainder of the manuscript. Please consider adhering to this convention.
```

### Hand the word count back to the author

Anchored on the numeral in the front matter, placed first in the document.

```
Please perform a new word count after our edits and suggestions have been considered.
```

```
✗  Word count updated to 4,391 following the edit.
✓  Please perform a new word count after our edits and suggestions have been considered.
```

## Query voice

### Use only the deferential frames

`Please consider <verb>ing …`, `Please ensure that …`, `Please check … carefully.`, `Note that “X”
was changed to “Y” because you appear to be …`, `Your intended meaning is somewhat/slightly unclear.
Did you mean “…”?` Address the author as *you*; call the editing *our edits and suggestions*.

```
✗  This sentence is confusing and the meaning is unclear. You should rewrite it as "negative interactions with other drugs".
✓  Your intended meaning is somewhat unclear. Did you mean “negative interactions with other drugs”?
```

The weak version diagnoses the author, asserts a defect, and issues an instruction. The strong version
attributes the difficulty to the reading experience, hands over finished text, and leaves the decision
with the author — the same information with no transfer of authority.

### Never assert that the author is wrong

Barred from every comment: *incorrect*, *error*, *wrong*, *this is confusing*, *you should*, *you
must*. Attribute unclarity to the reading, never to the writer, and state a convention as an
observation about practice rather than a rule imposed on them.

```
✗  Your use of "reducing score rates" is incorrect, since many of these values increased.
✓  Note that the phrase “reducing score rates” was changed to the word “changes” throughout this paragraph because you appear to be describing changes in general (some of which are increases) rather than reductions.
```

### Never argue the science in a comment

A query asks the author to verify or to choose. It never proposes an interpretation, disputes a
result, or explains what the data mean. More than two sentences means you have crossed from editing
into peer review.

```
✗  Note that 39% seems high compared with the 12% you report, which may indicate a measurement difference worth discussing.
✓  Please ensure that the intended meaning has been maintained in this edit.
```

## Anchoring and delivery

### Anchor each comment to the minimal span carrying the uncertainty

A single token (`PLMI`, `4480`), a phrase (`SPSS, Inc., Chicago, IL`), or the one rewritten clause —
never the whole paragraph and never the paragraph mark. A paragraph-wide anchor makes a
meaning-maintenance comment unusable, because the author cannot tell which decision to check.

```
✗  [comment anchored on the whole Discussion paragraph]
✓  [comment anchored on “second, because the clinical significance of RSWA is still unclear, RSWA might simply be an unusual PSG finding and may not develop into overt clinical RBD”]
```

### Give a paragraph as many comments as it has independent uncertainties

Two uncertainties, two comments, disjoint anchors. Do not merge them into one note.

```
✗  [one comment covering both the rewritten correlation sentence and the incomplete manufacturer address]
✓  [comment 1 on “Correlations between changes in … using the Pearson test.”; comment 2 on “SPSS, Inc., Chicago, IL”]
```

The Data Analysis paragraph, the abstract and one Discussion paragraph each carry exactly two.

### Keep every editorial word inside a comment, and leave the comments unresolved

Never insert editorial prose, brackets or queries into the body text. Author all comments under one
identity and deliver them unresolved, so the author works through and closes them.

```
✗  This difference might be due to the small sample size [EDITOR: is this the right explanation?] and mixture of antidepressants
✓  This difference might be due to the small sample size (n=15) and mixture of antidepressants used in the study performed by Winkelman and James.
```

### Record changes atomically so each decision can be rejected on its own

Insert a lone `s`, `the` or `d` rather than deleting and retyping the phrase; change one letter for a
case fix. Coarse delete-and-retype forces the author to accept or reject a whole sentence as a unit
and hides which decisions were made.

```
✗  Sertraline could induce or exacerbate RSWA, but did not induce RBD.
✓  Sertraline induced or exacerbated RSWA but did not induce RBD.
```

Delivered as five separate operations: `DEL 'could '`, `INS 'd'`, `INS 'd'`, `DEL ', '`, `INS ' '`.

Not when: a clause genuinely has to be rebuilt from scratch. One large delete/insert pair is then
unavoidable — and that is exactly the case that usually needs the meaning-maintenance comment.

## Editing intensity

Ask which level is wanted; default to premium. The levels differ in what they touch, never in how
they respect the prohibitions above — those hold at every level.

### Light proofread: mechanics only, no reordering

Spelling, typographical errors, capitalization, punctuation, spacing, agreement, obvious article
insertions. It does not reorder clauses, change voice, replace vocabulary or split sentences, and it
raises only the mechanical queries (word count, manufacturer location). A clumsy but correct sentence
stays as written.

```
✗  reduced REM sleep Latency
✓  reduced REM sleep latency
```

### Standard copyedit: mechanics plus grammar, tense and reporting convention

Adds article and preposition correction, subject–verb repair, tense normalization to section
convention, callout capitalization, abbreviation consistency, and deletion from the permitted classes.
It does not re-architect a sentence that is already grammatical, and it does not sweep an author's
terminology across a passage.

```
✗  The data were presented as the mean ± standard deviation for continuous variables
✓  The data are presented as the mean ± standard deviation for continuous variables
```

```
✗  From the 14th day onward, the TST and SE became longer and higher than the baseline or 1st day respectively, respectively.
✓  From the 14th day onward, the TSTs and SEs became longer and higher, respectively, compared with those at baseline or on the 1st day.
```

### Premium substantive line edit: rebuild for register, order and precision

Everything above, plus clause reordering, voice changes, sentence splitting and joining, verb
precision, hedge calibration, terminology sweeps, information-order repair, and reconstruction of
garbled or half-revised text. This is the only level that supplies meaning, and therefore the only
level at which meaning-maintenance and A/B queries arise at all.

```
✗  Secondly, the clinical meaning for RSWA was elusive,and which might only be a PSG finding and could not develop into overt clinical RBD.
✓  second, because the clinical significance of RSWA is still unclear, RSWA might simply be an unusual PSG finding and may not develop into overt clinical RBD
```

Not when: the author asked for light or standard. Do not deliver a premium edit under a lighter brief
— the author is buying a diff they can review, and an unexpectedly large one is a failure of the
engagement, not a bonus. Say what you would have done at premium in the report instead.
