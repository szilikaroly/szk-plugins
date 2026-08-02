---
description: Build and refine the memory graph — cognify extracts structure, memify keeps it worth having
argument-hint: cognify | memify | stats | route | explain <fact-id>
allowed-tools: Bash
---
Two pipelines over the long-term memory, borrowed from Cognee's phases. Cognee
itself is not installed; the semantics are reimplemented on the existing SQLite,
vector and edge tables so the plugin stays dependency-free.

**cognify** — `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cognify.py"`
Turns stored facts into a graph: classifies each one, extracts entities, and
links facts that share them. Before this the `edge` table only ever had hand-made
rows, so graph expansion had nothing to expand through.

- `cognify` → `--run` (only facts not yet processed)
- `cognify all` → `--run --all` (reprocess everything, e.g. after a model change)
- `cognify offline` → `--run --no-model` (regex extraction, no model needed)
- `stats` → `--stats`; `entities <id>` → `--entities <id>`

With a local model, extraction is real. Without one it falls back to
capitalised-phrase and identifier heuristics — measurably worse (7 links vs 12 on
the same six facts) but not useless, and it needs nothing installed.

**memify** — `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memify.py"`
Refines what cognify built. Three passes:

- **prune** — facts refuted or superseded by the claim store, entities nothing
  mentions, edges whose endpoints are gone. Reports by default; `--hard` deletes.
  Always show the user the list before running `--hard`.
- **reweight** — strengthens edges between facts repeatedly retrieved together.
  This is edge weight, **not** fact ranking: an earlier version scored facts by
  hit count and one fact ended up winning every query. Do not reintroduce that.
- **derive** — transitive `supersedes`, and `contradicts` edges where a refuted
  fact shares an entity with a live one.

`memify` is safe to run often and is idempotent except `--hard`.

**route** — `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/broker.py" --route`
Which model each task profile gets on this machine, derived from measured VRAM
rather than assumed. Flags any profile whose model will not fit — that model
still runs, on the CPU, about 20× slower with nothing else reporting it.

Suggested order when the memory has grown: `cognify` → `memify` → check `stats`.
