---
description: Check ethics & disclosure statements — conflict of interest, funding, consent, ethics approval
allowed-tools: Bash
---
Check the required and recommended disclosure statements. Arguments: $ARGUMENTS

Add `--journal <name>` if the target journal has a profile (Cureus makes COI,
funding, human subjects and informed-consent statements mandatory). Then run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" ethics MANUSCRIPT --journal generic
```

Report which required disclosures are missing (ERROR) versus recommended ones
(WARN). This is a keyword-presence check: if the user has the statement under an
unusual heading, tell them the checker may have missed it and ask them to
confirm it is present.
