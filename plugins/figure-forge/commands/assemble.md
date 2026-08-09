---
description: Combine panel images into one multi-panel Nature figure with bold a, b, c letters
allowed-tools: Bash
---
Assemble a multi-panel composite. Arguments the user gave: $ARGUMENTS

Pass the panel image files in reading order. Panel letters (a, b, c…) are added
bold at each top-left corner. Run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" assemble panelA.png panelB.png panelC.png --out STEM --formats svg,png,tiff --width double
```

Panels flow left-to-right, top-to-bottom; the grid is chosen automatically
(1 col for 1, 2 cols up to 4 panels, 3 cols beyond). Use `--width double` for a
full-page figure. Report the files written and show the composite PNG. Note:
panels are embedded as images, so the master here is a layout — keep each panel's
own editable SVG for text edits.
