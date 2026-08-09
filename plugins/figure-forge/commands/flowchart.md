---
description: Flowchart / CONSORT diagram from a node-edge spec, labels kept inside boxes
allowed-tools: Bash, Write
---
Build a flowchart. Arguments the user gave: $ARGUMENTS

The engine takes a JSON spec of nodes and edges. Write the spec to a file first
(use the Write tool), then render it. Spec shape:

```json
{
  "direction": "TB",
  "nodes": [
    {"id": "a", "text": "Assessed (n=210)", "w": 44, "h": 12},
    {"id": "b", "text": "Excluded (n=90)", "w": 44, "h": 14, "x": 80, "y": 60},
    {"id": "c", "text": "Randomised (n=120)", "w": 44, "h": 10}
  ],
  "edges": [{"from": "a", "to": "b"}, {"from": "a", "to": "c"}]
}
```

Coordinates are on a 0-100 canvas; omit `x`/`y` to auto-stack vertically (`TB`)
or horizontally (`LR`). Put a branch node (like "Excluded") off to the side with
explicit `x`/`y`. `shape` can be `box` (rounded, default) or `sharp`; `color` is
a hex fill. Then run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" flowchart --spec SPEC.json --out STEM --formats svg,png,tiff --width single
```

The QC loop guarantees every node label stays fully inside its box and no label
lands on an arrow. Report the QC result verbatim, list the files (including the
`.overlay.png` proof), and show the PNG. If a label cannot fit, the report says
so — widen that node's `w`/`h` in the spec and re-run.
