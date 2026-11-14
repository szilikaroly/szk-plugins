# Academic humanizer — rules for `/presubmit:humanize`

Adapted from **academic-humanizer v0.3.3** by AIScientists-Dev
(https://github.com/AIScientists-Dev/academic-humanizer, MIT, commit 94b88b2,
3 July 2026), which itself builds on **blader/humanizer** (MIT) and draws on
**koaeraser/ARMS**. The upstream licence is reproduced in
`licenses/academic-humanizer-LICENSE`. What changed in this adaptation:

- the examples are recast for clinical and biomedical manuscripts;
- the rules a regular expression can decide are implemented in
  `scripts/pc_style.py` and run before any rewriting (`pc.py style`);
- the promise that no number or citation changes is **checked**, by
  `pc.py invariants ORIGINAL REWRITE`, rather than taken on trust;
- em-dash removal applies to English text only; a Hungarian gondolatjel and
  every numeric en-dash range are left alone;
- presubmit's evidence rule is added: never write an evidence pointer that is
  not already in the manuscript (see Layer 4);
- the audit and the rewrite see only the prose: title page, declarations,
  back matter (abbreviations, supplementary lists, CRediT roles), legends and
  references are form text and are excluded, and a journal's word limit is
  treated as a budget the rewrite must stay within.

This is an editing aid for clarity and voice. It does not generate findings,
does not change data or citations, and is **not** a tool for evading AI-use
detection. Using it leaves the author's obligation to disclose AI assistance
exactly where it was: follow the target journal's policy.

---

## Finding code → layer

| `pc.py style` code | Layer | What it flags |
|---|---|---|
| `ai-vocabulary` | L1 | delve, underscore, intricate, tapestry, testament, pivotal, showcase, foster, realm, seamless, multifaceted, meticulous, "evolving landscape" |
| `copula-avoidance` | L1 | "serves as a", "stands as", "boasts" ("serves as a control/comparator/proxy" exempt) |
| `ing-tail` | L1 | ", highlighting the …", ", underscoring …" commentary tails |
| `filler-phrase` | L1 | in order to, due to the fact that, it is clear that, plays a crucial role |
| `em-dash` | L1 | em-dashes in English prose (INFO only; CRediT role names such as "writing—original draft" are exempt) |
| `overclaim-verb` | L2.1 | prove/proof that, clearly demonstrate, guarantee |
| `significant-without-test` | L2.1 / L4 | "significant(ly)" with no statistic, table or citation in the sentence |
| `significance-hype` | L2.2 | paves the way, sheds light on, paramount, bridges the gap, groundbreaking |
| `empty-intensifier` | L2.3 | extensive experiments, a wide range of, a plethora of |
| `novelty-padding`, `novel-repeated` | L2.4 | to the best of our knowledge, for the first time, "novel" twice in a section |
| `formulaic-opener` | L2.5 | In recent years…, has attracted increasing attention |
| `connective-run`, `connective-density` | L2.6 | Moreover. Furthermore. Additionally. in a row |
| `citation-dump` | L2.8 | six or more references behind one claim (in a systematic review or meta-analysis only the narrative sections are checked: an included-studies list is not dumping) |
| `vague-hedge` | L2.9 | somewhat, fairly, quite, to some extent |
| `boilerplate-emphasis` | L2.10 | It is worth noting that, Notably, Importantly, |
| `overlong-sentence` | L2.11 | sentences over 40 words (the source uses ~30; clinical prose runs longer) |
| `style-english-only` | — | Hungarian manuscript: no style rules applied |

Layers 3, 4 (beyond `significant-without-test`), 5 and 6 need reading for
meaning and are applied only in the rewrite pass.

---

## Core principle

Academic writing already has a correct human voice: neutral, precise, "we",
every claim tied to its evidence. The job is (1) to strip the AI *tells*
without casualising, and (2) to enforce what a general humaniser misses:
**every claim earns its number, figure, table or citation, and no verb is
stronger than its evidence.** Never inject opinion, humour or "personality"
into a manuscript.

## Process

1. **Read** the text and any writing sample of the author; note the document
   type (paper vs. funding proposal) and the target journal or funder.
2. **Audit** before editing: list each pattern with its location and the
   proposed fix, and each empirical claim's evidence status. Start from the
   `pc.py style` findings, then add what needs reading for meaning.
3. **Rewrite**: same structure and content, every claim and citation kept,
   tells removed, over-claims matched to evidence, legitimate hedging kept.
4. **Verify**: run `pc.py invariants` on original vs. rewrite. Any lost or
   added number, citation, cite key, DOI, equation or Table/Figure reference
   is a defect of the rewrite, to be fixed before anything is shown as final.
5. **Report**: cleaned text plus a short change log. Cover everything the
   original covered: five paragraphs in, five paragraphs out.

---

## Layer 1 — General AI-tell catalogue

Inflated significance ("marking a pivotal moment"); "-ing" tails that fake
depth ("…, highlighting…"); promotional or figurative language ("rich",
"vibrant", "groundbreaking"); vague attributions ("experts argue" with no
citation); AI vocabulary (*delve, underscore, intricate, tapestry, testament,
landscape (abstract), pivotal, showcase, foster, leverage (filler), realm,
seamless*); copula avoidance ("serves as" → "is"); negative parallelisms
("not just X, but Y"); rule-of-three padding; elegant variation (cycling
synonyms for one referent — in a clinical paper this also creates ambiguity:
"patients", "subjects", "the cohort" must mean one thing); filler ("it is
worth noting that", "in order to"); overlong clause-stacked sentences (2.11);
and, in English text, **em-dashes** (recast with commas, colons, parentheses
or separate sentences).

*Before:* Additionally, an enduring testament to the score's value is its
ability to delve into intricate risk dependencies, showcasing a seamless
integration that underscores its pivotal role.
*After:* The score also captures the interaction between renal function and
age, which the comparator scores miss (Table 2).

## Layer 2 — Academic AI tells

**2.1 Over-claiming verbs.** Empirical work *shows* and *provides evidence*;
it does not *prove*. Watch: prove, demonstrate (universal), establish,
confirm, guarantee; "significantly" with no test.
*Before:* We prove that the intervention significantly outperforms usual care.
*After:* The intervention reduced 30-day readmission by 6.1 percentage points
versus usual care (95% CI 2.3–9.9; Table 3).

**2.2 Significance hype.** paves the way for, a crucial step toward, has the
potential to revolutionise, opens new avenues, sheds light on, of paramount
importance, bridges the gap.
*After pattern:* name the one failure mode the work addresses and where.

**2.3 Empty intensifiers.** extensive/comprehensive experiments, a wide range
of, numerous, various → say how many and which.

**2.4 Novelty padding.** "novel" more than once per section; "to the best of
our knowledge"; "for the first time" → say what prior work did not do, and
cite it.

**2.5 Formulaic openers.** "In recent years, X has attracted increasing
attention"; "With the rapid development of…"; "Despite recent advances…" →
open on the specific problem.

**2.6 Connective overuse.** No consecutive sentences opening on
Moreover/Furthermore/Additionally/In particular; let the logic carry.

**2.7 Contribution-list clichés.** Each contribution names a specific result,
not "a novel method; extensive experiments; strong results".

**2.8 Citation dumping.** Cite the one or two works that matter and say why,
not "[3, 7, 9, 12, 15]". (In a systematic review the included-studies list is
legitimate — leave it.)

**2.9 Hedging by vagueness.** somewhat, relatively, fairly, to some extent,
quite → quantify or cut.

**2.10 Boilerplate emphasis.** "It is worth noting that", "It should be
emphasised that", sentence-initial "Notably," / "Importantly," → delete the
frame.

**2.11 Overlong sentences.** Split sentences that chain three or four clauses
with "which", "that", "while", "with": one idea per sentence.

## Layer 3 — Preserve (do NOT over-correct)

- **Evidence-tied hedging is correct and required**: "suggests", "is
  consistent with", "we hypothesise that", "may indicate". Never turn
  "the results suggest X" into "the results show X". In observational
  clinical research this is also what referees enforce (presubmit's reviewer
  rules flag causal verbs on observational data).
- **Passive voice** where the actor is irrelevant: "Samples were stored at
  −80 °C."
- **"We"** is standard.
- **Semicolons** and an occasional triple are fine; em-dashes are the English
  exception (Layer 1).
- **Definitions, named methods, scales, outcomes, drug names, gene symbols,
  equations, units and symbols** stay verbatim. Reporting-guideline wording
  (CONSORT, STROBE, PRISMA items) stays as the guideline words it.
- **Never invent, drop or alter a number, equation, citation or cross-reference.**
  `pc.py invariants` checks this.

## Layer 4 — Claim–evidence discipline

For every empirical claim: (a) is it carried by a number, figure, table or
citation in the text, and (b) does the verb match the strength of that
evidence?

- **Unbacked claim → point to evidence that is already in the manuscript, or
  soften.** Never write a table number, statistic or citation that is not in
  the original. If the evidence is missing, insert an author query instead:
  `⟦AUTHOR: which table/reference supports this?⟧`. (presubmit's
  `placeholder-left` check will then refuse to call the file ready until the
  author answers — by design.)
- **Verb stronger than evidence → downgrade.** "This demonstrates that the
  score is universally superior" → "In these three cohorts the score matched
  or exceeded the best comparator (Table 2)."
- **Vague magnitude → the number or range already reported, attributed** to
  its outcome, measure and comparator. Lead with the comparison against the
  strongest comparator, not the weakest.

## Layer 5 — Voice and venue

If the author supplies prior papers, read a sample first: sentence rhythm,
connective habits, level and placement of hedging, how sections open,
notation, recurring phrasings — then match them. Match the venue's register
(clinical journals: structured, results-forward; Nature/PNAS family: more
expository). Absent a sample, default to clean, precise, venue-appropriate
prose — never a casual voice.

## Layer 6 — Funding-proposal mode (NIH, NSF and similar)

A proposal is sold on **vision plus feasibility**, so ambition language a
paper would trim ("long-term goal", "transformative", "establish a
foundation") is appropriate when a credible plan backs it. Do not flatten the
vision; enforce **claim ↔ feasibility** instead.

- **Structure.** NIH: the Specific Aims page is the proposal in one page —
  gap/critical need → long-term goal and central hypothesis → "The objective
  of this application is…" → 2–3 Aims (goal, approach, expected outcome) →
  payoff. NSF: one-page Project Summary with Overview, Intellectual Merit and
  Broader Impacts each self-contained; the Description opens vision → goal →
  gap → thrusts → payoff within 1–2 pages. Check binding rules against the
  current NIH guide / NSF PAPPG, not this summary.
- **First-pages primacy.** By the end of page 1 (NIH) or pages 2–3 (NSF) the
  reader must hold the hook, the gap, the central idea, the aims and the
  payoff. Edit these hardest.
- **Weak moves to fix.** Vague importance ("this is an important problem");
  method-as-aim ("Aim 2: apply machine learning to the registry" → "Aim 2:
  determine whether…, and for which patients"); dominoed aims (state the
  fallback); ambition without footing (attach the preliminary data, prior
  result or collaborator beside the claim); boilerplate broader impacts or
  training plans; a hedged central hypothesis.
- **Keep and deploy.** Bold long-term goal up front; run-in lead-ins
  (**Goal:**, **Innovation:**, *Aim N:*); one running example across aims;
  aims posed as sharp questions; anchoring in named classical results; the
  team's real track record placed early as feasibility evidence.
- **Never invent** preliminary results, prior funding, partners or letters.
  If support is missing, flag the gap for the author.

---

## Output

Cleaned text plus a short change report: patterns removed (by type, using the
codes above where they apply), claims softened or given an evidence pointer
that already existed in the text, author queries inserted, and voice/venue
notes. End with the `pc.py invariants` verdict, verbatim.
