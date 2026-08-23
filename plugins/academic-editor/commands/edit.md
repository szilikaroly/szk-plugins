---
description: Teljes lektorálás — házistílus-mérés, determinisztikus ellenőrzés, tracked changes + kérdések
allowed-tools: Bash, Read, Write, Edit
---
Run a full Premium-level edit. What the user gave: $ARGUMENTS

Follow the skill's six steps in order. Do not skip step 2 (`housestyle.py`) when a target
journal is known — the whole point of the profile is that "match the journal's style" becomes
two numbers instead of an impression.

```
S="${CLAUDE_PLUGIN_ROOT}/scripts"
python3 "$S/housestyle.py" --journal "<JOURNAL>" --n 12 --years 3 --out journal-profile.json --md journal-profile.md
python3 "$S/housestyle.py" --profile journal-profile.json --compare <MANUSCRIPT>
python3 "$S/manuscript_check.py" <MANUSCRIPT> --json check.json
# ... build edits.json while editing, then:
python3 "$S/docx_tracked_edit.py" <MANUSCRIPT> edits.json --dry-run
python3 "$S/docx_tracked_edit.py" <MANUSCRIPT> edits.json -o <STEM>_edited.docx
python3 "$S/docx_accept_changes.py" <STEM>_edited.docx -o <STEM>_clean.docx
```

Ask the target journal if it was not named — the profile, the spelling convention and the
reference style all hang off it. Everything else defaults: premium substantive line edit,
US spelling, and say so in the report.
