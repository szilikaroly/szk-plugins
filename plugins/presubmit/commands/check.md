---
description: Full pre-submission mistake scan of a manuscript — sections, authors, abstract, references, ethics, formatting
allowed-tools: Bash
---
Run the complete pre-submission check. Arguments the user gave: $ARGUMENTS

Identify the manuscript file (.docx/.pdf/.tex/.txt/.md). If a journal is
mentioned and a profile exists (see `pc.py journals`), add `--journal <name>`.
Then run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" check MANUSCRIPT --journal generic --json PRESUBMIT.json
```

Report the output faithfully, led by the VERDICT line and the error/warn/info
totals. Then walk through the findings grouped by category, prioritising:
1. every `ERROR` (these commonly trigger desk rejection) — reference duplicates,
   citations with no matching reference, missing required disclosures, no abstract;
2. `WARN`s (missing section, no corresponding email, over-long abstract, uncited
   references, missing recommended statements);
3. `INFO` only if the user asks.

The checks are deterministic and offline — be clear that a clean report means
"no *automatically detectable* problems", not a guarantee of acceptance. For
language polish beyond the typography checks, offer the `academic-editor` skill;
for tracking the submission afterwards, offer `science-monitor`.
