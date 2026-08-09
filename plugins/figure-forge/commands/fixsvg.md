---
description: QC the labels in an existing SVG figure — flag labels outside boxes or over regions
allowed-tools: Bash
---
Check an existing SVG figure's labels. Arguments the user gave: $ARGUMENTS

Run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" fixsvg PATH.svg --preview
```

This is a **heuristic** check (the figure was drawn by another tool, so text
boxes are estimated from font-size and glyph width). It flags gross problems —
a label extending outside its box, or overlapping another region — and writes a
`.preview.png` rendering plus a `.qc.json` audit.

Report each issue with its suggested move in pixels. Be explicit that this is a
best-effort external check: for a guaranteed-clean result, offer to rebuild the
figure natively with `/ff:boxplot`, `/ff:forest` or `/ff:flowchart`, where the
QC loop measures the real renderer and corrects labels automatically.
