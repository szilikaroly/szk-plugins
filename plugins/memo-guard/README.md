# memo-guard

A Claude Code plugin that watches the context window, **archives the original
losslessly at 70% and 80%**, compresses it into a queryable memo in the
background, and **re-injects a ~500-token resume** after `/compact`, `/clear`,
or resume — so the next context starts with the knowledge but not the bulk.

Companion to the `memo-index` skill: memo-index compresses *material you
choose to read*, memo-guard compresses *the session that already happened*.

---

## Install

From the marketplace repo (see the [root README](../../README.md)):

```
/plugin marketplace add szilikaroly/szk-plugins
/plugin install memo-guard@szk-plugins
/reload-plugins
```

Local, before publishing — from the directory containing the repo:

```
/plugin marketplace add ./szk-plugins
/plugin install memo-guard@szk-plugins
/reload-plugins
```

Verify before trusting it:

```bash
claude plugin validate ./plugins/memo-guard
MEMO_GUARD_HOME=/tmp/mg-test python3 plugins/memo-guard/scripts/selftest.py
```

Optional live counter in the footer — add to `~/.claude/settings.json`:

```json
{ "statusLine": { "type": "command",
  "command": "python3 ~/.claude/plugins/cache/szk-plugins/memo-guard/*/scripts/statusline.py" } }
```

(Shells expand the `*`; if yours doesn't, run `/memo-guard:status` once and use
the concrete cache path it prints.)

---

## What it does

| Event | Hook | Action |
|---|---|---|
| every tool call | `PostToolUse` | measure context %; at 70% / 80% archive + compress |
| every prompt | `UserPromptSubmit` | same, plus at 85% nudge Claude to recommend `/compact` |
| before compaction | `PreCompact` | archive first — nothing is ever lost to a summary |
| session ends | `SessionEnd` | archive, so tomorrow resumes for a few hundred tokens |
| session starts | `SessionStart` | after `compact`/`clear`/`resume`, inject `RESUME.md` |

The context number is a **measurement, not an estimate**: the last `usage`
block the API returned (`input + cache_creation + cache_read`), read from the
tail of the session transcript. Same method and same `MEMO_CTX_WINDOW`
variable as `memo-index/ctx_watch.py`, so the two never disagree.

### Two compression modes

1. **local-model** — hands `sources/` to the memo-index pipeline
   (`memo_gen` → `verify_anchors` → `memo_db`). Every kept fact becomes a
   line-anchored claim, checked by `grep` rather than trusted. Zero API tokens.
2. **deterministic** — no model at all: head/tail plus signal-line extraction
   (errors, declarations, headings, URLs, statistics). Lossier, and `RESUME.md`
   says so explicitly.

Mode 1 is tried first and falls back silently to mode 2 if no local model is
installed. `/memo-guard:status` always reports which one produced a given memo.

---

## Measured (`scripts/selftest.py`, 716 KB synthetic session)

| | tokens | vs raw window |
|---|---:|---:|
| raw context window | 183,417 | — |
| distilled working set on disk | 20,939 | −88.6% |
| **RESUME injected into fresh context** | **507** | **−99.7%** |
| **realistic resumed session** (resume + 5 lookups) | **1,890** | **−99.0%** |

Hook latency below threshold: **~34 ms** on a 716 KB transcript (tail-read only).

### What the 95% figure means — and what it doesn't

It is the cost of the *resumed* context versus the window it replaces. It is
**not** a 95% cut to your overall bill. Reading a file the first time still
costs full price; memo-guard makes the *second, third, and fourth* encounters
with that material nearly free. The saving is real in long or resumed
sessions and roughly zero in a short one-shot session.

The ratio also improves with session size — the resume is a near-constant
~500 tokens whether the window held 50k or 190k.

---

## Commands

- `/memo-guard:status` — context %, archives, memo state, measured savings
- `/memo-guard:compress` — archive + compress now, before a planned `/compact`
- `/memo-guard:restore [term]` — find a detail cheap-first, never reloading originals
- `/memo-guard:remember` — edit core memory (always-in-context blocks)
- `/memo-guard:memory` — long-term memory: recall through a goal, or promote a fact
- `/memo-guard:claim` — refute, supersede or pin a claim so it stays judged

## Memory tiers

Four stores, deliberately separate, because they have different costs:

**Core memory** — `blocks.py`, injected into *every* session. Three blocks by
default: `user_preferences`, `workflows`, `project_context`. Edited with Letta's
three operations and their semantics:

| op | behaviour |
|---|---|
| `memory_replace` | exact string replace; `old_str` must occur **exactly once**. Zero or several matches are both refused, never guessed |
| `memory_insert` | add at a line without disturbing what is there |
| `memory_rethink` | rewrite the whole block — deliberate, and how a careful record becomes a confident summary of itself if overused |

Edits past a block's `char_limit` are refused, not truncated. `--history` shows
every change.

**Long-term memory** — `memory.py`. Facts across all projects, and the access
rule is the whole design: **without a stated `--goal` you see the current project
only; a goal opens everything.** Reaching into unrelated projects should be an
explicit act with a recorded reason. Every recalled fact carries its project and
date, because a fact from elsewhere read as current context is worse than not
recalling it. Nothing enters without `--promote` unless `auto_promote` is on.

**Graph** — an `edge` table (`supersedes`, `contradicts`, `depends_on`,
`part_of`, `relates_to`) with one-hop expansion at recall. This earns its place
on exactly the case search cannot handle: the fact that overturns your query
does not match your query — that is what makes it a contradiction.

**Claim verdicts** — `claims.py`. The memo dir is rebuilt every session, so a
claim refuted on Monday regenerates clean on Tuesday. This store outlives
sessions and is applied before the RESUME is built; blocked claims appear in the
RESUME under *"Already judged in an earlier session"*. `hits` counts how many
times each one tried to come back — if it stays at zero the store is doing
nothing and should be deleted.

Matching is lexical first (free, offline) and semantic only where lexical was
unsure. Lexical alone cannot separate meaning from coincidence: *"412
participants were enrolled"* against a recorded *"the sample size was n=412"*
scores the same as an unrelated sentence. With embeddings available it is caught
at 0.82.

## Retrieval order (cheapest first)

1. `memo_query.py` against the claims index — ~60 tok/answer (local-model mode)
2. `grep` the `distilled/` set — ~250 tok/answer
3. `gunzip -c <archive> | grep -n` — exact original bytes, matching lines only

Never `cat` an archive. Reloading it re-fills the window with the thing you
just spent CPU compressing.

---

## Config — `${CLAUDE_PLUGIN_DATA}/config.json`

```json
{
  "checkpoints": [70, 80],
  "advise_at": 85,
  "window": 200000,
  "use_local_model": true,
  "resume_max_chars": 6000,
  "keep_archives": 40,
  "startup_max_age_h": 48,

  "adaptive": false,
  "hard_floor": 90,
  "core_memory": true,
  "core_memory_max_chars": 2000,
  "enforce_verdicts": true,
  "auto_promote": false,
  "auto_promote_utility": 0.75,
  "auto_promote_max": 5
}
```

`window` is a **fallback**, not the answer. The window is resolved from the
model id first, and a context larger than the assumed window disproves the
assumption — the measurement wins and the window steps up to the smallest tier
that can hold it. Without that step a 1M-window session reads as 442% and burns
every checkpoint on the first tool call. `MEMO_CTX_WINDOW` overrides everything;
`/memo-guard:status` prints which source was used.

`adaptive: true` turns the checkpoints advisory — the model decides whether the
work since the last archive is worth preserving, because it knows whether the
last hour was one coherent piece or three false starts, and a percentage cannot.
`hard_floor` still fires unconditionally: judgement may be wrong, but must never
lose the session.

`auto_promote` is off deliberately. A memory that fills itself is a memory you
cannot trust.

Data lives in `${CLAUDE_PLUGIN_DATA}` (`~/.claude/plugins/data/...`), which
survives plugin updates:

```
archive/<project>/<sid>-cp70-<ts>.jsonl.gz   lossless original + .meta.json
sessions/<sid>/sources/                      dialogue + heavy tool outputs
sessions/<sid>/distilled/                    compressed, grep-ready
sessions/<sid>/.memo/                        claims db (local-model mode)
sessions/<sid>/RESUME.md                     what gets injected
metrics.jsonl                                every run, auditable
```

---

## Honest limits

- **No script can open a new context.** `/compact` and `/clear` are yours to
  run. memo-guard cannot, and does not pretend to. What it does is make the
  next context cheap and ensure nothing is lost when you do run them.
- **The archive is the ground truth; the memo is lossy.** Before *editing*
  anything, read the real file — never work from a distilled copy.
- **Deterministic mode drops things.** It keeps heads, tails, and signal
  lines. A fact in the middle of an unremarkable block can be missed. The
  archive still has it; `RESUME.md` names the mode so you know when to dig.
- **Auto-extracted "what was in flight" is a guess** from the last turns.
  `/memo-guard:compress` before a planned compaction gives a sharper one.
- Archives contain **everything in your session**, including any secrets that
  passed through it. They sit unencrypted under `~/.claude`. Prune with
  `keep_archives` or delete the directory. `memory.db` is worse: facts from
  every project in one file. It is `0600`, promotion is explicit, and
  `memory.py --disable <slug>` excludes a project from recall entirely.
- **Both embedding models silently truncate long input.** They return a vector
  describing only the beginning and report no error, so a truncated embedding
  looks exactly like a working one. Measured here: mxbai stops between ~760 and
  2850 tokens, nomic between ~2850 and 5700. There is no long-context model,
  only a safe length — `SAFE_CHARS`, with chunking above it. Re-run
  `embed.py --truncation-test` after any model change; the cut depends on
  Ollama's context defaults, not just the model.
- **On Windows the `0600` file mode does not protect anything.** `os.chmod`
  there only toggles the read-only attribute, so `memory.db` — which holds
  material from every project — stays readable by every account on the machine.
  The call is still made because it is correct on macOS and Linux, and
  `mg_lib.secure_file()` returns whether it really applied. Getting the same
  guarantee on Windows needs an ACL (`icacls`), which this does not set behind
  your back. If you sync a knowledge base to a shared Windows box, set it
  yourself.
- **The retrieval floor is calibrated, not universal.** `SEMANTIC_FLOOR = 0.48`
  sits in a measured gap (relevant queries scored 0.562–0.724, nonsense queries
  0.320–0.408) — but that was a handful of facts. Re-check it against your own
  corpus; override with `MEMO_SEMANTIC_FLOOR`.
- **Claim matching still misses paraphrases with no embedder.** Lexical overlap
  cannot tell meaning from coincidence, and no threshold separates them. With
  Ollama unavailable, semantic matching degrades to lexical and some
  resurrections get through.
- **The local-model path does not finish on large transcripts.** On a 14 MB
  transcript it exceeds its budget and falls back to deterministic mode. Since
  `broker.py` this fails in ~4 minutes instead of 30 and still produces a
  ~1,030-token RESUME. The deterministic path is the reliable one; the model
  path is an upgrade, not a dependency.

## cognify / memify

Cognee splits memory into **add** (ingest), **cognify** (extract structure) and
**memify** (refine it afterwards). memo-guard already had add and had vectors,
but its graph was empty in practice because every edge was hand-made. These two
fill that gap. Cognee itself is not a dependency — it is a pip package with
database and LLM-provider backends, and this plugin's hooks run on every tool
call, so stdlib-only is load-bearing. The semantics are reimplemented on the
tables that already exist.

**`cognify.py`** — classify → extract entities → link facts sharing them.
Measured on the same six facts: the model path found 12 entity links and 4
edges; the deterministic fallback found 7 and 2. Worse, and still far better
than an empty graph. Two bugs the first version had, both fixed and both worth
knowing if you extend the regex:

- `"PROSPERO"` and `"The PROSPERO ID"` normalised to different entities, so the
  two facts about the same thing never linked. Leading articles and trailing
  `ID`/`number`/`form` are now stripped before normalising.
- Alternation is first-match-wins, so `[A-Z]{2,}` matched `CRD` out of
  `CRD42024518822` and threw the registration number away. Longest forms first.

**`memify.py`** — prune, reweight, derive. Verified: it identified a fact the
claim store had refuted, strengthened 6 edges from co-retrieval, and derived a
transitive `supersedes` (8→1 through 7) plus a contradiction edge.

**Reweighting is on edges, never on facts.** An earlier version scored facts by
`hits`, so a fact returned once scored higher and was returned again, until one
fact won every unrelated query. Co-retrieval of a *pair* is different evidence —
it says two facts answer the same question — and it only affects graph
expansion, never the ranking that decides what surfaces first. Do not merge the
two.

```bash
cognify.py --run [--all] [--no-model]
memify.py  --run [--hard]        # --hard actually deletes; default reports
broker.py  --route               # which model each task gets, from measured VRAM
```

## Syncing across machines

`sync.py` keeps the knowledge base in a **private** git repo, separate from this
public one. Nothing about this is optional: `memory.db` holds facts from every
project the plugin has ever seen, so the data repo must not be the code repo.

```bash
sync.py --setup <user>/<private-repo>    # clone or create, private
sync.py --push / --pull / --status
```

Then set `"sync": true` in `config.json`. Writes call `--request`, which marks
the store dirty and returns immediately; a detached worker pushes after an
8-second coalescing window, so a burst of ten promotions becomes one commit and
no write ever waits on the network.

**The database itself is never committed.** SQLite is binary and does not merge —
two machines editing it produces silent loss, not a conflict you can see. It is
exported to deterministic JSON, one file per project, which is the same strategy
science-monitor's `repo.py` uses and for the same reason: two machines working
on different projects never touch the same file.

Three things this got wrong first, all of them now fixed and all worth knowing
if you extend it:

- **Row ids are not portable.** `fact.id` is a local AUTOINCREMENT, so machine
  A's fact 5 is not machine B's. Edges exported by id would attach to whatever
  held that number elsewhere — worse than not syncing, because it looks like it
  worked. Everything is keyed by content fingerprint and resolved locally.
- **Union merge alone makes deletion impossible.** Anything removed came back on
  the next pull from any machine that still had it, so `--forget` and
  `memify --hard` were silently undone. Deletions now leave a tombstone, which
  travels with the data. Tombstones store the fingerprint only — never the text,
  which would re-leak what was removed.
- **A brand-new remote has no `main` to pull from,** and treating that as an
  error meant the very first push could never happen. Setup deadlocked
  permanently until the remote was checked before pulling.

Order matters in `push()`: pull → import → export → commit. The file git commits
is regenerated from the already-merged database, so concurrent edits to the same
project produce a union rather than a conflict. Verified with two machines
editing one project: both ended with the same four facts, nothing lost.

## The broker

Everything that wants the local model goes through `broker.py`, which owns one
machine-wide slot. Four separate problems turned out to be one:

| symptom | cause |
|---|---|
| two compressions hung 19 min at 0% CPU | the lock was per-session, so two Claude Code windows defeated it |
| the 80% memo silently never built | when the lock held, the second run **skipped** instead of waiting |
| `route.py`'s "one model at a time" | documented as a fact, enforced nowhere |
| no background reorganisation | nothing owned scheduling |

Rules it follows: **wait, never skip** — dropped work is worse than slow work
because you cannot see it happen. **Deadlines, not hope** — past the deadline the
caller degrades to deterministic instead of blocking. **Stale locks die** — a
crashed compressor must not wedge the machine. **Capacity is probed**, not
assumed, from actual VRAM.

Measured after: five concurrent processes serialise with zero overlap; two
compressors on one session both complete (241 s and 522 s) and both produce a
memo, where before neither did.

```bash
broker.py --probe        # hardware, backend, VRAM, capacity, loaded models
broker.py --status       # who holds the slot
broker.py --health       # is the model server actually answering
broker.py --break-lock   # refuses unless the lock is genuinely stale
```

### Preventing and repairing a stall

Prevention runs inside `slot()`, once the slot is held so nothing races it:

1. `diagnose()` — one verdict with its evidence. `WEDGED` and `SLOW` look
   identical from outside (nothing comes back) but need opposite responses, so
   they are separated by measurement.
2. `recover(1)` if degraded — eviction only, so a hook may run it unattended.
3. `ensure_room(model)` — evict what is in the way **before** the load, instead
   of discovering afterwards that the model went half onto the CPU.

Repair also triggers on a **stale lock**: a lock whose owner is gone means a job
died mid-model, which is the most common way to inherit a degraded server. The
next run breaks the lock, diagnoses, and repairs rather than inheriting it.

```bash
broker.py --diagnose            # OK | SPILLED | SLOW | WEDGED, with evidence
broker.py --fit gemma4:12b      # would it fit, and what would be evicted
broker.py --recover --level 1   # evict spilled models      (safe, automatic)
broker.py --recover --level 2   # evict everything, re-probe (safe, automatic)
broker.py --recover --level 3   # restart the server        (never automatic)
```

Level 3 is deliberately excluded from automatic recovery: it kills a process the
user may be using for something else.

Verified: an unreachable server is called `WEDGED` in 16 ms; `--fit gemma4:12b`
with 3,305 MB free evicted `llama3.1:8b` and reported 11,936 MB after; a lock
left by a dead PID is taken over by the next run in 0.3 s.

**The lock is machine-wide, not per data directory.** It first lived under
`mg.data_dir()`, which is keyed to `CLAUDE_PLUGIN_DATA`/`MEMO_GUARD_HOME` — so
two installs, or a test run with that variable set, had separate lock
directories and could not see each other. Two `memo_gen` processes were observed
driving one Ollama simultaneously: the exact starvation the lock exists to
prevent, reintroduced one level up. It now lives at
`~/.claude/memo-guard-locks`, because the resource being guarded is one model
server on one machine. `MEMO_GUARD_LOCK_DIR` overrides it for genuinely
separate servers.

**Not verified: an actual GPU spill.** `--probe` reports `size_vram/size` per
model and below 95% means part of it is on CPU — about 20× slower with nothing
else reporting it. But loading two models that together exceed VRAM did *not*
produce a spill here: Ollama's own scheduler evicted one first. The detection
is real and costs nothing; whether the condition ever occurs may depend on
`OLLAMA_MAX_LOADED_MODELS` and the platform. Treat that path as untested.

## Uninstall

```
/plugin uninstall memo-guard@szk-plugins
```

Then remove the data (archives and memos are NOT deleted by uninstall):

```bash
rm -rf ~/.claude/plugins/data/*memo-guard*
```
