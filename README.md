# szk-plugins

Claude Code plugins by Dr. Szili Károly. Currently one:

## memo-guard

Context-window and memory tooling in four tiers, each one you only pay for if the
tier above did not answer:

| tier | what it holds | cost |
|---|---|---|
| **core memory** (`blocks.py`) | preferences, learned workflows, project context | injected every session |
| **resume** (`compressor.py`) | a ~500–1000 token index of the last session | injected after `/compact` or `/clear` |
| **long-term memory** (`memory.py`) | facts across all projects, vector + graph | only what a goal recalls |
| **archive** | the original transcript, gzipped, lossless | disk only, never context |

Plus a claim-verdict store (`claims.py`) that keeps a judgement alive across
sessions, so a claim you disproved last week is not regenerated clean this week.

### Measured

On a 716 KB synthetic session, in the *weaker* (no local model) mode:

| | tokens | vs raw window |
|---|---:|---:|
| raw context window | 183,417 | — |
| RESUME injected into fresh context | 507 | **−99.7%** |
| realistic resumed session (resume + 5 lookups) | 1,890 | **−99.0%** |

On a real 14 MB transcript (884,346 measured tokens) the deterministic path
produced a 1,030-token RESUME — **−99.9%**. Expect roughly 2× the synthetic
figure on real sessions.

Hook latency: ~25 ms median on the hot path that runs on every tool call.

Full documentation: [`plugins/memo-guard/README.md`](plugins/memo-guard/README.md).

---

## Install

Everything in one command, on the machine where Claude Code runs:

```bash
./install.sh                          # from this local directory
./install.sh <your-user>/szk-plugins  # from GitHub, after publishing
```

It validates the marketplace and plugin, runs the selftest, then uses the
non-interactive `claude plugin` subcommands. One step remains:

```
/reload-plugins       activate now, without restarting
/memo-guard:status    confirm it is live
```

`/reload-plugins` exists only in the interactive `claude` terminal. In the
desktop and web apps, start a new session instead — plugin config is loaded at
session start either way.

### Or by hand

```
/plugin marketplace add <your-user>/szk-plugins
/plugin install memo-guard@szk-plugins
```

Local, before publishing — from the directory *containing* this repo:

```
/plugin marketplace add ./szk-plugins
/plugin install memo-guard@szk-plugins
```

### Optional: local embedding models

Semantic matching and retrieval activate automatically when an embedding model
is reachable through Ollama, and fall back to lexical matching when it is not.
No configuration either way.

```bash
ollama pull nomic-embed-text     # 274 MB — fast path, 768 dims, ~18 ms
ollama pull mxbai-embed-large    # 670 MB — recall path, 1024 dims, ~25 ms
```

Both are used: the fast one for hot per-claim checks, the larger one for recall.
Vectors are stored **per model**, because vectors from different models are not
comparable and a cosine between them is a number with no meaning. Check with
`embed.py --benchmark`.

**Re-measure after changing models.** Both models silently truncate long input —
they return a vector describing only the beginning and report no error.
`embed.py --truncation-test` finds where each one stops reading. `SAFE_CHARS`
must stay below that, and longer text is chunked rather than routed to a
"long-context" model: there is no long-context model here, only a safe length.
The retrieval floor (`SEMANTIC_FLOOR`, override with `MEMO_SEMANTIC_FLOOR`) was
calibrated on a small corpus and should be re-checked against your own.

### Publish to GitHub

```bash
./publish.sh <your-github-user>
```

Requires the [GitHub CLI](https://cli.github.com) authenticated with
`gh auth login`. It runs the same checks, refuses to push if any transcript or
archive file is staged, commits with **your** git identity, creates the repo,
and pushes.

### Validate manually

```bash
claude plugin validate .                        # marketplace + each entry
claude plugin validate ./plugins/memo-guard     # manifest, hooks, commands
MEMO_GUARD_HOME=/tmp/mg-test python3 plugins/memo-guard/scripts/selftest.py
```

CI runs all three on every push (Ubuntu + macOS, Python 3.11/3.12).

### After you edit the plugin

Installing **copies** the plugin into `~/.claude/plugins/cache`. Editing this
directory afterwards changes nothing in the installed copy:

```
/plugin marketplace update szk-plugins
/plugin update memo-guard
```

---

## Versioning

`plugin.json` carries an explicit `"version"`, and it must be bumped on every
release.

This was tried the other way round first. With no `version` field the fallback is
supposed to be the git commit SHA — but installed from a local path that is not a
git repository, it falls back to the literal string `unknown`, the cache lands in
`.../memo-guard/unknown/`, and `claude plugin update` fails outright with
*"Plugin not found"*. Every change then needs a full uninstall/reinstall. An
explicit version costs one edit per release and avoids that.

Do not set `version` in both `plugin.json` and `marketplace.json`: `plugin.json`
silently wins.

## Note on privacy

memo-guard archives your full session transcripts, unencrypted, under
`~/.claude`. Anything that passed through a session — tokens, patient data,
credentials — is in there.

The long-term memory raises the stakes, because
`~/.claude/memo-guard/memory.db` holds facts from **every** project in one file.
Three things bound that: it is created `0600`, nothing enters it without an
explicit `--promote` (`auto_promote` is off by default), and any project can be
excluded from recall entirely:

```bash
memory.py --disable <project-slug>
```

Recall itself is gated: without a stated `--goal` you only see the current
project. `.gitignore` blocks `archive/`, `sessions/`, `*.jsonl*` and `*.db` from
ever being committed, but check before you push, and prune with `keep_archives`.

## License

MIT — see [LICENSE](LICENSE).
