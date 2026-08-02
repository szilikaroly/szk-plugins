---
description: Közös git adat-repo — szinkron a szerzőtársakkal
allowed-tools: Bash
---
The local SQLite store is one person's working copy. The shared truth lives in a
git repo: `projects/<slug>.json` per manuscript plus the documents themselves.

`$ARGUMENTS` is `pull`, `push`, `status`, or `init <path>`.

## Napi használat

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" repo pull
```

Run this **at the start** of a working session: it does `git pull --ff-only`,
then rebuilds the local database from the repo. Submissions, checklists,
reviews and review points are replaced wholesale from the repo — the repo is the
truth for them, so local edits that were never pushed are lost. If the user has
unpushed work, push first.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" repo push -m "üzenet"
```

Run this at the end: writes every project out, copies any new manuscripts, cover
letters, responses and supplements into the repo, commits, and pushes if a
remote exists. Add `--no-push` for a local commit only.

## Első beállítás

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" repo init ~/science-monitor-data
```

Then the user adds a **private** remote themselves. Do not create a remote, and
do not push to a host on their behalf — the repo holds unpublished manuscripts,
cover letters and reviewer letters. If they ask you to publish it anywhere,
confirm explicitly that the target is private first.

Joining an existing shared repo instead: clone it, then
`sm.py config data_repo <path>` and `sm.py repo pull`.

## Ütközés

Conflicts land in `projects/<slug>.json`. The JSON is sorted and pretty-printed,
so the conflict is readable — resolve it in the file, `git add`, `git commit`,
then `sm.py repo pull` to load the merged result. Two people on different
manuscripts never conflict; one file per manuscript is the whole point.

## Ami nem megy a repóba

Figures, tables, datasets, code and session transcripts stay local — they are
large and rarely need sharing. Their entries record which machine they are on,
so a co-author sees that a file exists elsewhere rather than a dead path. Widen
or narrow this with `sm.py config sync_roles manuscript,cover_letter,response`.

## Jelentés

After a pull, say how many manuscripts came in and whether anything now needs
attention (`sm.py gaps`). After a push, say what was committed and whether it
actually reached a remote — "committed locally, no remote configured" is a
materially different outcome from "pushed", and the user needs to know which.
