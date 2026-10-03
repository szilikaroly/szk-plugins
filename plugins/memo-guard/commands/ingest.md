---
description: Realtime ingestion of the workspace — queue status, pause/resume the GPU, scan now
argument-hint: status | pause | resume | scan | now | add <path>
allowed-tools: Bash
---
Files written inside a `corpus_roots` folder are queued by the PostToolUse hook; files
changed outside Claude are picked up by a scan at session start (at most every
`ingest_scan_every_min`). A detached worker turns them into memos on the local GPU,
verifies the anchors, imports tables as SQL, and refreshes the corpus store.

Parse "$ARGUMENTS" and run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ingest.py"` with:

- `status` (or nothing) → `--status`
- `pause` → `--pause` — the user needs the GPU. Documents stay queued; nothing touches
  the GPU until `resume`. Tables are still imported (CPU only). If the user says the GPU
  is needed right now, also stop any running worker: it finishes its current file first.
- `resume` → `--resume`
- `scan` → `--scan` — look for changed files now instead of at the next session start.
- `now` → `--now` — process the queue in the foreground (shows the outcome per file).
- `add <path>` → `--enqueue "<path>"`
