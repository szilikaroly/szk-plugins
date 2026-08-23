---
name: figure-forge
description: Build publication-quality, Nature-style scientific figures at 600 dpi with editable-text labels and a self-correcting label-quality loop that guarantees no label sits outside its box or covers a curve, marker or arrow. Differentiates sign from punctuation — minus sign for negative numbers, en dash for ranges, hyphen for compounds — without touching identifiers, and verifies the font can draw every character it introduces. Use whenever the user wants to CREATE, GENERATE, POLISH or FIX a figure, chart, plot or diagram for a paper — box plots, forest / meta-analysis plots, CONSORT / flowcharts, pathway or box-and-arrow diagrams, or multi-panel composites — or wants a figure exported as SVG, TIFF, PNG or PPTX, or asks how best to visualise some data. Also use to check/repair labels in an existing SVG. Also use to audit whether an existing SVG or PDF figure is genuinely editable, or to check its dashes and signs. Hungarian triggers — ábra készítése, forest plot, folyamatábra, box plot, dobozdiagram, feliratok ellenőrzése, nature-stílusú ábra, 600 dpi, szerkeszthető feliratok, írásjel, előjel, mínuszjel, gondolatjel, szerkeszthető SVG.
---

# Figure Forge

Turn data or a description into a journal-ready figure whose labels are
provably clean. Everything is driven by one CLI; each subcommand builds the
figure, runs the QC loop, and exports every requested format.

## The one rule that defines this skill

**Never hand back a figure without running the QC loop.** Every generate
command already does this by default (`autofix`), and prints a QC result. Relay
that result to the user verbatim — whether it is CLEAN or has unresolved
violations. The guarantees the loop enforces:

- **R1 containment** — a label bound to a box stays fully inside it.
- **R2 cover** — no label overlaps a data mark, curve, arrow or other box.
- **R3 collision** — no two labels overlap.
- **R4 canvas** — no label crosses the figure edge.

Every figure also writes `<stem>.overlay.png` (a visual proof: a box drawn
round each checked label, green = clean, red = unresolved) and `<stem>.qc.json`
(the audit). Show the user the overlay when they want proof it was checked.

## Defaults

600 dpi · Nature style · editable-text SVG master (font fallback stack, named
layers) · sign/punctuation differentiated · Okabe-Ito colourblind-safe
palette · single-column (89 mm) unless the figure wants more. Fonts fall back
from Arial/Helvetica to DejaVu Sans automatically.

## Workflow

1. **Advise first when the user is unsure.** `ff.py advise "<what they want to
   show>"` returns a chart-type recommendation and a Nature checklist. Relay it,
   add your judgement, then propose the exact build command.
2. **Build.** Pick the subcommand:
   - `boxplot  --data F --value V --group G` — grouped box plot + jittered points
   - `plot     --data F --x X --y Y [--series S] [--kind line|scatter]` — direct-labelled
   - `forest   --data F --label L --effect E --low LO --high HI [--weight W]`
   - `flowchart --spec SPEC.json` — nodes/edges; write the spec with the Write tool first
   - `panelflow --spec SPEC.json` — staged pipeline / proposed-architecture figure:
     columns with header bars, titled boxes, arrows, optional status banner.
     Reach for this instead of `flowchart` when the figure is a *stage* diagram
     carrying prose in each box, and when the final printed width is fixed
   - `assemble  a.png b.png c.png` — multi-panel composite with bold a/b/c
   - `fixsvg    old.svg --preview` — heuristic label check of an external SVG
3. **Report** the QC result and every file written; show the PNG.
4. **If violations remain**, the message says why (usually a box too small or a
   label too long). Widen the column (`--width double`), shorten the label, or
   enlarge the node box in the spec, then re-run — "recheck until polished".

## Running the CLI

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" <subcommand> [flags]
```

Common flags on every generate command: `--out STEM`, `--outdir DIR`,
`--formats svg,png,tiff,pdf,pptx` (default `svg,png`), `--dpi 600`,
`--palette okabe-ito|nature`, `--width single|1.5|double|<mm>`, `--title`,
`--no-check` (skip QC — discourage this), `--max-iter N`,
`--no-typography` (leave every string exactly as given — see below).

Inspect a data file's columns with `head -1 FILE` before choosing `--value`,
`--group`, `--label`, `--effect` etc. Never invent column names or data.

## Sign is not punctuation

Three characters that look alike and are not interchangeable:

| Char | Name | Job | Example |
|---|---|---|---|
| `-` | hyphen-minus | joins words | follow-up, IL-6, Kruskal-Wallis |
| `−` | minus sign U+2212 | signs a number | −0.42, Δ = −1.5 |
| `–` | en dash U+2013 | spans a range | 12–24 months, 2019–2021 |

Every string the caller supplies — axis titles, study names, node text, legend
entries, direct labels — is converted before it is drawn, and matplotlib already
handles negative tick labels (`axes.unicode_minus`). The rules also produce
`±`, `×`, `≤`, `≥`, `≠`, `µm`, `°C` and unit exponents (`mm3` → `mm³`), and
space relational operators the way journals set them (`p<0.05` → `p < 0.05`).

**Identifiers are never touched.** `IL-6`, `HLA-B27`, `COVID-19`, `2-fold`,
`p-value` and `NCT01032434` keep their hyphens: every rule that could reach them
requires digits on *both* sides of the separator with no adjacent letter. Text
inside `$…$` is passed through untouched so mathtext still works.

**Nothing is silent.** Every substitution is listed in `<stem>.qc.json` and
tallied on the console (`typography: 2× range en dash, 1× minus sign`). Read the
tally back to the user when a label mattered — a typographic rule that quietly
edits data is worse than no rule. If a label is a literal that must not be
touched, re-run with `--no-typography` and say that you did.

**The glyph check is the other half.** Because the SVG names a font rather than
embedding outlines, a substitution the font cannot draw becomes a hollow box in
the vector master while the raster proof still looks correct. Every run tests the
resolved font against the characters it introduced; 243 of the 320 font families
on a typical machine fail that test, so the warning is not theoretical. If it
fires, say so and offer the two real options: a font that has the glyphs, or
`--no-typography`.

## Is it really editable?

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" audit FILE.svg        # or FILE.pdf
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" audit FILE.svg --fix
```

Every export is checked by reading the file back, not by trusting the setting
that was supposed to produce it, and the result is in the QC audit and on the
console. Three things are asserted or fixed:

- **text stays text** — a group named `text_7` that contains no `<text>` means
  the glyphs were outlined. Visually identical, completely uneditable, and
  invisible in a raster proof. Nothing recovers it; the figure must be
  re-rendered.
- **a font fallback stack**, not one family. Matplotlib writes
  `font-family: 'Arial'`; opened where Arial is absent, the renderer substitutes
  different metrics and **the label-QC guarantee silently stops holding**,
  because it was computed against Arial. Say this if a user asks why the SVG
  looks different on another machine.
- **human-readable layers** — `inkscape:label` on every group, carrying the
  actual label text, so Illustrator's Layers panel and Inkscape's Objects panel
  show `text: −0.42` instead of `text_7`.

`audit --fix` hardens those three on a file made elsewhere. It **never rewrites
label text**: it lists the typography that should change and leaves it. Fixing
text in someone else's figure is an edit, not a repair.

## Formats — what each is for

- **svg** — the editable master; text stays as `<text>`, with a font fallback
  stack and named layers, so labels stay editable in Illustrator/Inkscape. This
  is what satisfies "editable labels".
- **tiff** — LZW-compressed, 600 dpi tag embedded; the classic raster ask.
- **png** — 600 dpi flat raster for submission portals and previews.
- **pdf** — vector with embedded fonts.
- **pptx** — one slide at the figure's real size, high-res image plus native,
  editable PowerPoint text boxes over each label.

## Self-test

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" selftest` proves the QC loop
corrects a deliberately-misplaced label, that every export format writes, that
each typography rule converts what it should and leaves every identifier alone,
that the resolved font can draw what the rules introduce, and that the exported
SVG and PDF really are editable. Run it if anything looks off.
