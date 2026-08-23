---
description: GRADE — a bizonyítékok biztonsága kimenetenként, Summary of Findings-hez
allowed-tools: Bash, Read, Write
---
Rate certainty of evidence. Request: $ARGUMENTS

**One rating per outcome.** Not per study, not per review. If several outcomes matter, this runs
once for each, and the Summary of Findings reports them separately. Establish the outcome list
first and say how many tables you are about to produce.

```
A="${CLAUDE_PLUGIN_ROOT}/scripts/appraise.py"
python3 "$A" --skeleton grade > grade-<outcome>.md
python3 "$A" --rollup grade-<outcome>.md --tool grade
```

Inputs you need before starting: the per-study risk-of-bias ratings (RoB 2 / ROBINS-I /
ROBINS-E), the pooled estimate with its confidence interval, the heterogeneity, and the number
of studies. GRADE's risk-of-bias domain is about the **body** weighted by contribution — one
high-risk study carrying 3% of the weight does not downgrade a pooled estimate; the same study
carrying 60% does. Name the studies that drove the decision.

Report the certainty with GRADE's own informative statement, not your own wording:

- High → "X reduces Y"
- Moderate → "X probably reduces Y"
- Low → "X may reduce Y"
- Very low → "the evidence is very uncertain about the effect of X on Y"

Two answers that are easy to get wrong: with fewer than about ten studies, publication bias
"could not be assessed" — which is not the same as "undetected", so say which you mean. And
upgrade factors apply only to a body of evidence that has not been downgraded; the rollup
refuses to apply both and will tell you.
