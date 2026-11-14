---
description: Predict what a referee will write back about, before you submit
---

Run the reviewer-anticipation checks on `$ARGUMENTS` (a manuscript path):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" reviewer "$ARGUMENTS"
```

This category is not the editorial-office check the other subcommands run. It
asks the question a referee asks — is this claim carried by what is in the paper
— and each of the 147 rules comes from a real report: thirteen cohorts — twelve of the
author's own (462 points) and 38 open-peer-review manuscripts (608 objections) —
in English and Hungarian. `skills/presubmit/references/reviewer-patterns.md`
maps every finding code to the comment it came from.

Reporting it back:

- Lead with the count by severity, then walk the findings. An ERROR here means a
  referee is likely to ask for the change before recommending acceptance, not
  that the paper is wrong.
- Each finding names the **guard it looked for**. Where the omission is
  deliberate, say so and move on — that is a legitimate answer and takes one
  sentence.
- Silence is not proof. Say so: the module reports missing guards, and it cannot
  see whether a present guard is any good.
