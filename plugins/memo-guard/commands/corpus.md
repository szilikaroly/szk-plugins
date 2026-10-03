---
description: Search the whole indexed workspace — verified claims, concepts, and every table as SQL
argument-hint: search <query> | concept <query> | find <text> | sql <SELECT…> | tables [pattern] | sync | stats | maintain
allowed-tools: Bash
---
The corpus store holds every memo-index claim from the configured `corpus_roots`
(`memo.db`) and every CSV/TSV/XLSX as a real SQL table (`data.db`). Query it instead of
re-reading source files: a search costs tens of tokens, the files it points at cost
thousands.

Parse "$ARGUMENTS" and run the matching form (`S="${CLAUDE_PLUGIN_ROOT}/scripts"`):

- `search <query>` → `python3 "$S/store.py" --search "<query>"`
  Ranked claims whose anchor was string-verified against the source line. REFUTED claims
  never appear; add `--unproven` only when exploring, and say that those are unverified.
  Add `--project kutatas/<name>` to stay inside one project.
- `concept <query>` → `python3 "$S/concepts.py" --search "<query>"`
  Nearest concepts by meaning (works across languages and wording), each with its best
  verified claims. Use when `search` misses because the words differ.
- `find <text>` → `python3 "$S/tables.py" --find "<text>"`
  Full-text search over the rows of every text table (corpus lists, search exports,
  reference validations).
- `sql <query>` → `python3 "$S/tables.py" --sql "<query>"`
  Read-only. Use `tables` first to learn the table name (`t123`) and its columns; column
  names are the original headers, so quote them: `SELECT "doi", "cim" FROM t63 WHERE …`.
- `tables [pattern]` → `python3 "$S/tables.py" --list "<pattern>"`
- `sync` → `python3 "$S/store.py" --sync` then `python3 "$S/tables.py" --sync`
- `stats` → `python3 "$S/store.py" --stats` and `python3 "$S/concepts.py" --stats`
  and `python3 "$S/dbmaint.py" --status` (size, free share, statistics, FTS fragmentation)
- `maintain` → `python3 "$S/dbmaint.py" --heavy`: integrity check, index rebuild where it
  disagrees with its content, FTS optimize, ANALYZE, VACUUM when fragmented. It also runs
  daily on its own; say which steps did anything (a REBUILT index is worth reporting).

Report results as data with their `path:line`. Before quoting a claim in a manuscript or
editing a file because of it, Read the cited line: a claim is a pointer, not the source.
