---
description: Check how the evidence is presented — estimates without confidence intervals, undescribed trial acronyms, repeated study descriptions, self-promotion in the closing
allowed-tools: Bash
---
Check how the manuscript presents its evidence. Arguments: $ARGUMENTS

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" claims MANUSCRIPT --journal generic
```

These are the things an editor asks for in almost every revision round, and
they are all decidable without reading for meaning:

- **an estimate without its precision** — checked per parenthetical, not per
  sentence. The failure that actually gets flagged in review is a headline
  estimate carrying its 95% CI next to subgroup values in the *same sentence*
  that do not. A bare `(8)` is understood as a citation, and a P value is not
  asked for a CI.
- **a study named only by an acronym** — flagged only when the token is clearly
  being introduced as a study (`In SELECT,` in a sentence that carries a
  citation) and no describing clause follows. Gene symbols, degrees, approval
  numbers and abbreviations the manuscript defines itself are excluded, so this
  should be quiet on a clean paper.
- **the same reference described twice** — the most common source of "this
  paragraph is repetitive". Describe a study once, where it first appears.
- **the authors' own ongoing study in the closing** — editors read it as
  self-promotion that dilutes the conclusion.

Report each with the sentence it sits in. For the acronym findings, suggest the
shape of the fix — population, design, comparator in one clause — rather than
writing the clause blind; the right description depends on the study.

Note the word budget: adding descriptions and confidence intervals costs words,
and short formats have hard limits. Run `/presubmit:submission` alongside this
one so the two are considered together.
