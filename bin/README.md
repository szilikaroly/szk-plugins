# Global CLI launchers

The szk-plugins engines as plain terminal commands, usable from **any directory
or session** — not only inside a Claude Code slash command.

| Command | Subcommands |
|---|---|
| `figure-forge` | the figure engine |
| `presubmit` | the pre-submission checker |
| `science-monitor` | the manuscript/submission register |
| `composer` | `harvest` · `validate` · `protocol` · `prisma` · `selftest` |
| `validator` | appraisal flags directly, plus `probast` · `selftest` |
| `academic-editor` | `check` · `housestyle` · `compare` · `track` · `accept` · `selftest` |

The three multi-script launchers share `bin/_resolve.sh`, which is sourced rather
than executed.

Each launcher runs the real **source `.py`** engine, resolved in this order:

1. the git working copy (`plugins/<name>/scripts/…`) — source of truth, editable;
2. the marketplace clone under `~/.claude/plugins/marketplaces/szk-plugins`;
3. the newest installed plugin cache under `~/.claude/plugins/cache`.

Because it always targets the `.py` source, a session never has to fall back to
bare matplotlib because "only `.pyc` is present".

## Install (this machine or any other)

```bash
./bin/install-cli.sh          # symlinks into ~/.local/bin
```

Then:

```bash
figure-forge selftest
presubmit selftest
figure-forge flowchart --spec my.json --out fig1 --formats svg,png,tiff,pptx --width double
presubmit check manuscript.docx --journal cureus
```

Python is taken from `python3` on PATH (override with `FIGURE_FORGE_PYTHON` /
`PRESUBMIT_PYTHON`). It must have the engines' dependencies — matplotlib,
numpy, pandas, python-pptx, Pillow, lxml (and cairosvg for external-SVG work).
On this setup that is the Anaconda `python3`.

## Run every self test

```bash
./bin/selftest-all.sh
```

Every suite is offline and deterministic — no network, no API key, no clock
dependence. That is deliberate: a test suite that needs the internet stops being
run, and a suite that is not run is not a suite.
