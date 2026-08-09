---
description: Check language & typography — repeated words, spacing, quote/dash consistency
allowed-tools: Bash
---
Run the deterministic language/typography checks. Arguments: $ARGUMENTS

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" format MANUSCRIPT
```

This flags repeated words ("the the"), double spaces, spaces before punctuation,
likely missing spaces after a sentence, and mixed quote or dash styles. It does
**not** do spell-checking or grammar (no dictionary → no false positives on
medical terminology).

Report the findings, then remind the user that for real grammar and register
editing they should use the `academic-editor` skill — this command only catches
mechanical typography slips that make a manuscript look unpolished.
