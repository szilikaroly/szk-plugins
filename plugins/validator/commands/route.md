---
description: Melyik értékelő eszközzel? — vizsgálati elrendezés → műszer
allowed-tools: Bash, Read
---
Pick the appraisal instrument. What the user described: $ARGUMENTS

```
A="${CLAUDE_PLUGIN_ROOT}/scripts/appraise.py"
python3 "$A" --route "<the design, in the user's own words>"
python3 "$A" --list
```

If the design is not clear from the request, ask exactly one question — was the exposure or
intervention assigned by the investigators, and was that assignment random? That single answer
separates RoB 2 from ROBINS-I from ROBINS-E, and everything else follows.

When the router returns more than one instrument, do not run them all. Name the question each
one answers and ask which the user needs — except for the two pairs that genuinely go together:

- PROBAST+AI (is the science sound) **and** TRIPOD+AI (is it reported completely) for anyone
  preparing or reviewing a prediction-model paper;
- AMSTAR 2 (was this review conducted well) **and** GRADE (how certain is the evidence it
  synthesised) for a review being used as evidence.

Say the unit of assessment out loud before starting — one result for RoB 2 and ROBINS, one
outcome for GRADE, one model for PROBAST, the review for AMSTAR 2. Getting the unit wrong
produces an appraisal that cannot be interpreted, and it is invisible in the output.
