---
description: List the built-in journal profiles Presubmit can check against
allowed-tools: Bash
---
List available journal profiles. Arguments (ignored): $ARGUMENTS

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" journals
```

Show the user the profiles and their notes. If they want a journal that isn't
listed, offer to add a new profile: it's a small JSON file in the plugin's
`profiles/` folder with abstract/keyword limits, required sections and required
disclosures. Ask them for the journal's author-guide numbers and create it.
