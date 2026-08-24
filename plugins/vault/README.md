# vault

Continuous, private git backup for every project under one root. Same behaviour
on macOS and Windows.

You do not run it. After `/vault:init` it works on its own: every time a Claude
Code session stops, each project that changed gets a commit and a push to its
own **private** GitHub repository. At most one push per project per five
minutes, so a busy session does not turn into a hundred commits.

## What it does on first run

For each immediate subdirectory of the root:

1. `git init -b main` if the project has no repo, with `core.fileMode false` and
   `core.autocrlf false` — the second one matters, because CRLF conversion
   breaks the LF-ending shell and Python scripts these projects are full of.
2. Writes a `.gitignore` covering the usual noise (`.DS_Store`, `__pycache__`,
   `.venv`, `node_modules`, editor droppings) and appends to it rather than
   overwriting, so anything already there survives.
3. Finds every file at or above 95 MB — GitHub hard-rejects anything over
   100 MB — adds those to `.gitignore`, and writes them down with their exact
   sizes in `.vault/oversize.txt`. **Excluded is not the same as lost:** the
   files stay on disk untouched, and the list tells you precisely what is not in
   the history.
4. Commits.
5. Creates the private GitHub repo through `gh` and wires it as `origin`.

## What it refuses to do

A project larger than `max_repo_gb` (4 GB by default) is committed locally but
**not pushed**. This is not caution for its own sake: GitHub warns above 1 GB and
degrades badly beyond that, and a failed 10 GB push after twenty minutes is
worse than an honest refusal. `/vault:status` shows these as
`PUSH VISSZATARTVA`. If you really want one pushed anyway, create an empty file
`.vault/force-push` inside it.

It never force-pushes, never deletes, and never rewrites history.

## Commands

| Command | What it does |
|---|---|
| `/vault:init` | Set up repos and private remotes for everything |
| `/vault:status` | What is versioned, what is behind, what is held back |
| `/vault:save` | Commit and push everything now, ignoring the debounce |
| `/vault:pause` · `/vault:resume` | Suspend and restart autosaving |
| `/vault:doctor` | Why it is not saving |

## Requirements

`git`, and the GitHub CLI (`gh`) signed in — `gh auth login`, once, by hand. The
sign-in is an interactive browser flow; nothing here can or should do it for you.
Without it the local repos and commits still happen and only the remote half is
skipped.

## Configuration

`~/.claude/vault/config.json`, written on first `init`:

| Key | Default | Meaning |
|---|---|---|
| `root` | `~/Documents/claude` | Where the projects live |
| `github_owner` | `""` | Account owning the private repos; empty = gh's default |
| `repo_prefix` | `""` | Prefix for remote repo names |
| `interval_sec` | `300` | Minimum seconds between pushes, per project |
| `max_file_mb` | `95` | Files this size or larger are excluded |
| `max_repo_gb` | `4.0` | Repos larger than this are committed but not pushed |
| `exclude` | `[".claude", ".git", "evals"]` | Projects to leave alone entirely |

Set `VAULT_HOME` to move the config, state and log somewhere else.

## Why the hook cannot hurt you

The `Stop` hook does one thing: it spawns a detached child and returns. The child
does the walking, committing and pushing. A hung network, a rejected push, a
corrupt repo — none of it reaches the session, and none of it can make a hook
time out. Failures land in `~/.claude/vault/vault.log` and in `/vault:status`.
