# Figure Forge

Nature-style scientific figures with a **self-correcting label-quality loop**.

Build box plots, forest / meta-analysis plots, CONSORT flowcharts, box-and-arrow
diagrams and multi-panel composites — at **600 dpi**, with **editable-text**
labels — then let the engine guarantee that **no label sits outside its box and
no label covers a curve, marker or arrow**. Every figure ships with a QC audit
and a visual proof overlay.

## Why it exists

Getting figures through peer review is death by a thousand label collisions: a
study name lying across a confidence interval, a box caption spilling past its
rectangle, a panel letter clipped at the margin. Figure Forge measures every
label's true bounding box **from the same renderer that draws the figure**, then
runs `check → correct → recheck` until the layout is clean or reports exactly
what it could not fix.

## The QC guarantees

| rule | meaning |
|------|---------|
| **R1 containment** | a label bound to a box stays fully inside it |
| **R2 cover** | no label overlaps a data mark, curve, arrow or other box |
| **R3 collision** | no two labels overlap |
| **R4 canvas** | no label crosses the figure edge |

Correction order: recentre in the parent box → shrink font to the 5 pt floor →
spiral-search for free space → report if still impossible (box too small).

## Commands

| command | what it does |
|---------|--------------|
| `/figure-forge:advise "<goal>"` | recommend a chart type + Nature checklist before you plot |
| `/figure-forge:boxplot` | grouped box plot with jittered raw points |
| `/figure-forge:plot` | line / scatter plot with direct end-of-line labels (no legend clutter) |
| `/figure-forge:forest` | forest / meta-analysis plot; labels kept off every CI line |
| `/figure-forge:flowchart` | node/edge flowchart (CONSORT-friendly); labels kept inside boxes |
| `/figure-forge:assemble` | combine panel PNGs into a multi-panel figure with bold a, b, c |
| `/figure-forge:panelflow` | staged pipeline / architecture figure from a column-and-box spec |
| `/figure-forge:fixsvg` | heuristic label check of an existing external SVG |
| `/figure-forge:audit` | is this SVG/PDF really editable, and are its signs and dashes right? |

Natural-language requests ("make me a Nature-style forest plot of these ORs")
trigger the bundled **figure-forge skill**, which drives the same CLI.

## Defaults

600 dpi · Nature style · editable-text SVG master · Okabe-Ito colourblind-safe
palette · single-column (89 mm) sizing · Arial/Helvetica → DejaVu Sans fallback.

## Outputs

For stem `fig1` you get the requested formats plus proof and audit:

```
fig1.svg          editable-text vector master (labels editable in Illustrator)
fig1.png          600 dpi flat raster
fig1.tiff         LZW-compressed, 600 dpi tag embedded
fig1.pdf          vector, embedded fonts
fig1.pptx         one slide, real size, image + native editable text boxes
fig1.overlay.png  visual proof: a box round every checked label
fig1.qc.json      the audit (rules, residual violations, iteration log)
```

## Requirements

Python 3 with `matplotlib`, `numpy`, `pandas`, `lxml`, `python-pptx`, `Pillow`
(all standard in Anaconda). `cairosvg` is optional and only used to rasterise
external SVGs in `/figure-forge:fixsvg`.

## Sign is not punctuation

`-` joins words (follow-up, IL-6). `−` signs a number (−0.42). `–` spans a range
(12–24 months). Using one glyph for all three is the most common typographic
fault in scientific figures, and in a forest plot it is visible: the hyphen is
narrower and sits lower than the digits, so a column of negative estimates fails
to line up.

Every caller-supplied string is converted before it is drawn — axis titles, study
names, node text, legend entries — and the rules also produce `±`, `×`, `≤`, `≥`,
`µm`, `°C` and unit exponents, and space relational operators (`p<0.05` →
`p < 0.05`).

Identifiers are never touched: `IL-6`, `HLA-B27`, `COVID-19`, `2-fold`,
`p-value`, `NCT01032434`. Every rule that could reach them needs digits on *both*
sides of the separator with no adjacent letter. `$…$` mathtext passes through
untouched. Every substitution is listed in the QC audit and tallied on the
console — a rule that quietly edits data is worse than no rule. `--no-typography`
turns the whole thing off.

**The glyph check.** With `svg.fonttype: none` the SVG names a font instead of
embedding outlines, so a substitution the font cannot draw is a hollow box in the
vector master while the raster proof looks fine. Every run tests the resolved
font against the characters it introduced. 243 of the 320 font families on a
typical macOS install fail that test.

## Is it really editable?

```bash
scripts/ff.py audit figure.svg          # or figure.pdf
scripts/ff.py audit figure.svg --fix
```

Exports are verified by reading the file back, not by trusting the rcParam that
was supposed to produce it:

- **text is still text** — a `text_7` group with no `<text>` inside means the
  glyphs were outlined: visually identical, completely uneditable, invisible in
  a raster proof, unrecoverable;
- **a font fallback stack**, not one family. Matplotlib writes
  `font-family: 'Arial'`. Opened where Arial is absent, the renderer substitutes
  different metrics and the label-QC guarantee — no label outside its box, none
  over a curve — silently stops holding, because it was computed against Arial;
- **human-readable layers** — `inkscape:label` carrying the actual label text,
  so an editor's Layers panel shows `text: −0.42` instead of `text_7`.

`--fix` hardens those three on a figure made elsewhere and **never rewrites label
text**: it lists the typography that should change and leaves it alone.

## Self-test

```bash
python3 scripts/ff.py selftest
```

Proves the QC loop corrects a deliberately-misplaced label and that every export
format writes correctly.

## Examples

The `examples/` folder contains a CONSORT flowchart spec, a meta-analysis CSV,
and the figures they produce — including the `.overlay.png` proofs.

---

Part of the **szk-plugins** marketplace · MIT · Dr. Szili Károly
