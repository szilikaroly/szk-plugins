---
description: Tényleg szerkeszthető ez az ábra? — SVG/PDF editability és írásjel-ellenőrzés
allowed-tools: Bash, Read
---
Audit an existing figure file. Target: $ARGUMENTS

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" audit <FILE.svg|FILE.pdf>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" audit <FILE.svg> --fix
```

Answers two questions a rendered figure cannot answer by being looked at:

1. **Is the text still text?** An SVG whose glyphs were outlined looks identical
   in a browser and is completely uneditable. The audit reads the file rather
   than trusting the setting that was supposed to produce it. If the verdict is
   NOT EDITABLE, say so plainly: nothing recovers outlined text, and the figure
   has to be re-rendered from its source.
2. **Is sign differentiated from punctuation?** `-0.42` with a hyphen, `12-24`
   with the same hyphen, and `follow-up` with it again is one glyph doing three
   jobs. The audit lists every label that should change and **does not change
   any of them** — this file may not be ours, and rewriting someone's figure
   text without asking is an edit, not a fix.

`--fix` hardens only what is safe to harden without touching content: the font
fallback stack, human-readable layer names, and `xml:space` on text. It never
rewrites label text. To correct the typography, re-render from the source with
figure-forge, where the rules run before the containment QC measures anything.

Report the verdict first, then the font situation (a single declared family
means the figure re-flows on any machine without that font — and the label-QC
guarantee was computed against the original metrics), then the typography list.
