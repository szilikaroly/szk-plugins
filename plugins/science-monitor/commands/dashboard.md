---
description: Dashboard — hiánylisták, checklistek, egykattintásos gombok
allowed-tools: Bash
---
The dashboard has two modes. Pick by what the user asked for.

## Élő mód — a gombok tényleg írnak

If the user wants to *click* things — tick checklist items, mark a submission
sent, flip a cover-letter state — they need the server. Run it in the
background so the session stays usable:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" serve
```

Use the Bash tool with `run_in_background: true`. It binds `127.0.0.1:8787`,
opens the browser, and prints the URL. Every checkbox and button writes
straight to `~/.science-monitor/monitor.db`. Tell the user it keeps running
until they stop it, and that a page reload always shows current state.

Port clash: pass `--port 8788`. The API is gated on a per-run token embedded in
the served page, so a stale browser tab from an earlier run will get 403s —
reload from the new URL.

## Statikus mód — a gombok a parancsot másolják

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" dashboard --open $ARGUMENTS
```

Writes `~/.science-monitor/dashboard.html` and opens it. Nothing is running, so
each button copies the exact command to the clipboard instead of acting. Good
for a quick look; not for working through a checklist.

## Mi van a lapon

- **Folyamat** — a beadási állapotok oszlopokban, kattintható a kézirathoz.
- **Kéziratonként**: a beadás vezérlői (cover letter állapota, beküldve-e,
  státusz), a **hiánylista** (mi hiányzik, és melyik parancs javítja), a
  **beadási checklist** (a kézirat típusához szabva), és a nyitott **bírálati
  pontok** pipálhatóan.
- **Összesítő tábla** blokkoló-számmal.

## Jelentés

Say the URL (or path) and, in one sentence, the single most pressing thing on
the page — normally the manuscript with the most blockers, or one that is ready
with a finished cover letter but still not submitted. Get that from
`sm.py gaps`, not by re-reading the HTML.

Never publish this page as an Artifact or upload it: it holds unpublished
manuscript titles, journal IDs and review state.
