---
description: Tracked changes .docx + tiszta változat előállítása az edits.json-ból
allowed-tools: Bash, Read
---
Produce the deliverables. Arguments: $ARGUMENTS

```
S="${CLAUDE_PLUGIN_ROOT}/scripts"
python3 "$S/docx_tracked_edit.py" <MANUSCRIPT> <EDITS.json> --dry-run
python3 "$S/docx_tracked_edit.py" <MANUSCRIPT> <EDITS.json> -o <STEM>_edited.docx
python3 "$S/docx_accept_changes.py" <STEM>_edited.docx -o <STEM>_clean.docx
python3 "$S/manuscript_check.py" <STEM>_clean.docx --only counts
```

**Always `--dry-run` first.** An edit whose `find` string does not match is simply absent
from the delivered file, and the author will never know it was intended. Fix the mismatches —
they are almost always curly quotes, en dashes, non-breaking spaces or a double space — and
re-run.

Hand back **both** files. The tracked one is the deliverable the author works through; the
clean one is what goes into a submission system. Say the new word count from the clean file,
and never edit a word-count figure inside the manuscript itself.

If `docx_accept_changes.py --reject` is used to verify, note that it legitimately reports
fewer deletions than `--accept` when a deletion sits inside an insertion.
