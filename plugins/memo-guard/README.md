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
| every prompt | `UserPromptSubmit` | recall matching long-term memory into the prompt (`recall.py`) |
| before compaction | `PreCompact` | archive, then build a memo **synchronously** — the window is seconds from being replaced |
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
- `/memo-guard:autopilot` — let compaction fire on its own at a chosen context %
- `/memo-guard:doctor` — what is misconfigured, overlapping, or quietly broken

## Autopilot — archive, compress, compact, without you asking

```
/memo-guard:autopilot            # status
autopilot.py --enable --at 70    # compaction fires at 70% of the measured window
autopilot.py --disable
```

The plugin's oldest limitation was that it could prepare perfectly for a
compaction it had no way to cause. It still cannot cause one — but it does not
have to, because Claude Code compacts on its own, and where that trigger sits is
readable from the environment:

```
threshold = min(floor(effective_window * CLAUDE_AUTOCOMPACT_PCT_OVERRIDE / 100),
                effective_window - 13000)
```

Verified against the shipped binaries (2.1.211 and 2.1.237). Autopilot writes
that variable into `settings.json`; the `PreCompact` hook does the rest. The
compaction fires **between turns, never inside one** — which is the "when the
current step has finished" that no percentage watcher of ours could have
achieved, because ours only ever runs *during* a step.

Three things about it that are easy to get wrong:

**The two percentages are not the same percentage.** memo-guard measures against
the model's real window. Claude Code measures against an *effective* window: the
real one minus a reserve (capped at 20,000 tokens), and shrunk further by an
`autoCompactWindow` setting if you have one. Writing `70` therefore does not
produce compaction at the 70% this plugin reports:

| real window | `autoCompactWindow` | override 70 fires at | = of the real window |
|---|---|---:|---:|
| 1M | 800,000 | 546,000 tok | **54.6%** |
| 1M | — | 686,000 tok | 68.6% |
| 200k | — | 126,000 tok | 63.0% |

Rather than reimplement the product's arithmetic, which would break the first
time it changed, autopilot **measures where compaction actually landed** and
corrects the override toward the target — one proportional step, because both
sides are a fraction of a fixed window. Verified against a transcription of that
formula in `selftest.py`: all three rows above reach 70.0% in **at most one
correction**. `--status` shows every sample. Only *automatic* compactions are
samples — a manual `/compact` is you choosing a moment, and calibrating on it
would teach autopilot your habits instead of the product's arithmetic.

**It takes effect in the next session.** The environment is read when the process
starts, so writing `settings.json` cannot move the running session's threshold.

**Only automatic compactions can be raised into.** The trigger compares against
`min(floor(effWin * pct/100), effWin - 13000)`, so the correction has headroom up
to ~98% of the effective window; the clamp at 95 is well inside it. (The separate
`precomputeBufferFraction` floor at 80% applies to *precomputing* the summary,
not to firing.)

**The override is undocumented.** It is read straight from `process.env` by both
builds checked here, but nothing promises it will survive a release. If it
disappears, autopilot stops aiming and everything else keeps working exactly as
before — the archive, the memo and the resume never depended on it.

### The fast pass

Auto-compaction turns a rare race into a routine one. `PreCompact` used to
archive and spawn the compressor in the background; compaction then finished in
seconds and `SessionStart` injected a `RESUME.md` that was stale, or absent.

So `PreCompact` now: writes a stub immediately (the archive path and how to grep
it — 790 bytes, never overwriting a real memo), then runs
`compressor.py --fast` **synchronously** — deterministic only, no local model,
bounded to 40 s of the hook's 60 s budget — and only then spawns the full
background run that will upgrade the memo for next time.

"Wait, never skip" is right for a checkpoint and wrong here. A checkpoint is not
about to lose anything, so it can afford four minutes and the local model. The
fast pass is describing a context that disappears in seconds; a lossier memo that
exists beats a better one that arrives too late. Measured: 8.4 s on a 716 KB
transcript, RESUME present the moment the hook returns.

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

## Recall — memory that shows up without being asked

The three stores above were reachable only through `/memo-guard:memory` and
`/memo-guard:claim`, which makes them useless in the case they exist for: **you
cannot ask for a fact you have forgotten you recorded.** A memory that only
answers when addressed by name is a filing cabinet.

`recall.py` runs on `UserPromptSubmit` and injects what matches the prompt.
Everything about it is a constraint, because this cost is paid on *every turn*:

| rule | why |
|---|---|
| ≤ 400 tok, ≤ 3 facts | the question is never "is this relevant" but "is it worth more than the tokens it displaces" |
| once per fact per session | a fact injected on turn 1 is still in context on turn 2; injecting it again fills the window with repeats — the exact failure this plugin exists to prevent |
| silent below 25 chars, and on any `/command` | "yes", "go on", `/status` — instructions about the work in flight, not questions memory can answer |
| lexical by default | the semantic path is a round trip to a local model server |
| marked as data | facts were written by earlier sessions; text from an earlier session is not an instruction from the user |

A matching **refuted or superseded claim** is flagged before the work starts
rather than after it has been redone.

```bash
recall.py --test "what PROSPERO number did we register the PMOS review under"
# semantic path : off (lexical only)
# scope         : current project only   candidates: 1
#   INJECT [0.980] The PROSPERO registration number for the PMOS review is CRD…
# would inject  : ~31 tok of a 400 tok budget
```

### Measuring it — `recall_eval.py`

Two things here used to be assertions: that `SEMANTIC_FLOOR = 0.48` "sits in a
measured gap" (measured once, by hand, on a handful of facts), and that
injecting memory into every prompt is worth its tokens. Neither can be settled
by looking at what the retriever returned — you need the scores of the facts it
did *not* return, and the behaviour on prompts where the correct answer is
silence.

`eval/recall_corpus.json` is 20 labelled facts across four projects and 28
queries in four kinds:

| kind | what it tests |
|---|---|
| lexical | the query shares words with its fact — the easy case |
| paraphrase | it shares almost none; the only case embeddings can justify their latency |
| gated | the one relevant fact is in **another** project, so with no goal stated the correct answer is nothing. A hit here is a privacy failure, not a success |
| noise | nothing in the store answers it; anything returned is pure cost |

```bash
recall_eval.py                    # measure (both modes if an embedder is up)
recall_eval.py --sweep            # pick the injection floors from data
recall_eval.py --calibrate        # SEMANTIC_FLOOR: show the two distributions
recall_eval.py --no-embed --json  # fast, deterministic; what selftest runs
```

**The headline number is not recall — it is the false-injection rate.** Recall is
paid once per useful answer; noise is paid on every turn forever, and a block
that is usually noise is a block you learn to skip.

Measured on the bundled corpus, lexical path only:

| | before | after |
|---|---:|---:|
| recall | 70% | **70%** |
| precision | 67% | **93%** |
| false injection | 25% | **0%** |
| cross-project leaks | 0 | **0** |
| cost | 26 tok/prompt | **19 tok/prompt** |

#### What the harness found

**A single weak match scored a perfect 1.0.** The lexical signal was bm25
normalised to the best hit — so the best hit is 1.0 *even when it is terrible*.
A query about trains from Budapest to Debrecen matched one fact on the word
"goes" and was injected with full confidence, because nothing else matched
anything. Relative rank cannot say "the best answer here is still bad". It is
now damped by coverage — the share of query terms the fact actually contains —
floored at 0.25 so a paraphrase, which shares few words by definition, is damped
rather than deleted. One extra `IN (...)` query, no extra round trips.

**The floor belongs on relevance, not on the composite score.** The obvious knob
was "don't inject anything below score X". The composite carries a recency term,
so a floor on it is an age limit wearing a relevance costume — and the oldest
facts are the ones a memory exists for. `recall()` now returns `relevance`
separately (query signal only, no recency or same-project constant) and
`recall_min_relevance` gates on that. Graph neighbours are exempt: they were
pulled in by an edge, not by matching the query, so they have no relevance of
their own and the edge type is the evidence.

**The floors were swept, not chosen.** 0.35 and 0.40 perform identically; 0.45
is a cliff where recall drops to 65%. The default is 0.35, so the margin above
it is one step, not three. `recall_relative_floor` earns nothing once the
relevance floor is in place (identical rows at every value) and defaults to 0 —
it is kept for corpora full of near-duplicates, where the second-best answer is
a copy of the best.

#### What this does not prove

- **The corpus is small and synthetic.** 20 facts, written to make the four
  query kinds separable. Your own store will not behave identically —
  `--corpus mine.json` takes the same format.
- **Every fact in it is new.** Recency is therefore constant across the corpus,
  so nothing here exercises how ranking ages. The move of the floor onto
  relevance makes that structurally irrelevant for injection, but not for
  ranking order.
- **The semantic path is unmeasured.** The local embedder was stalled
  (`broker.py --diagnose` = SLOW) throughout, so every number above is the
  lexical floor of this system, not its ceiling. `paraphrase recall 54%` is the
  number embeddings have to beat, and `--calibrate` refuses to run without a
  responding embedder rather than print a threshold derived from nothing.

### The health check that had to be strict

Whether to embed is decided by `broker.healthy(strict=True)`, and the `strict`
existed for a reason found while building this. The non-strict check falls back
to `/api/tags` when `/api/embed` fails — so a **wedged server is reported
healthy**, and the hook would then block on an embed call in front of the user's
keystroke. Measured on this machine at the time: `/api/tags` answered in 1 ms,
`/api/embed` had still not answered after 60 s. The verdict is cached for a
minute, because paying a probe timeout per keystroke turns one broken component
into a tax on typing, and `embed.set_timeout()` bounds the call itself — 20 s is
right when a human asked for a recall and wrong in front of every prompt.

Measured (`selftest.py`): **74 ms warm**, 672 ms on the first prompt of a session
(interpreter start plus the one health probe). Silence is the correct output for
most prompts; every miss is written to `metrics.jsonl` so the hit rate is
measurable rather than anecdotal.

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
  "auto_compact_at": 70,
  "fast_wait_s": 20,
  "recall": true,
  "recall_max_tokens": 400,
  "recall_max_facts": 3,
  "recall_min_chars": 25,
  "recall_deadline_s": 1.5,
  "recall_min_relevance": 0.35,
  "recall_relative_floor": 0.0,
  "model_total_s": 900,
  "maintain_every_h": 24,
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
  run; a hook cannot execute a slash command. What autopilot does instead is
  *aim* the automatic compaction Claude Code already has (see below) — it never
  triggers one itself, and if auto-compaction is disabled it can do nothing at
  all.
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
- **On a large transcript the model reaches some sources and not others.** It
  is no longer all-or-nothing (see *The model path, per source* below), but a
  transcript big enough to exhaust the budget still ends with part of the
  session covered only by the deterministic distillation. The RESUME names
  which parts. The deterministic path remains the reliable one; the model path
  is an upgrade, not a dependency.

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

## The model path, per source

The old shape ran memo-index's `memo_gen` once over every source with a single
timeout. On a 14 MB transcript it ran past the budget, was killed, and the
non-zero exit was read as total failure — so the run fell back to deterministic
mode and **threw away every memo it had already finished**. `memo_gen` writes
each memo as it completes and skips files whose hash already matches, so that
work was sitting on disk the whole time. Nothing was missing except a caller
willing to keep it.

It is now a map/reduce:

- **map** — one `memo_gen` call per source, each with its own budget. A source
  that fails or times out costs that source, not the run.
- **reduce** — `verify_anchors` → `memo_db` → `index_build` once, over whatever
  the map phase produced. Zero memos is the only total failure left.

Order is deliberate: `conversation.md` first, because decisions live in the
dialogue and nothing else reconstructs them, then smallest-first, which
maximises how many sources are covered before the deadline.

**Partial coverage has to be visible.** A memo labelled `local-model` that
quietly modelled two thirds of the session reads, to the next context, exactly
like one that modelled all of it. So the mode becomes
`local-model (partial: 9 of 14 sources modelled)`, `PARTIAL.json` records both
lists, and the RESUME carries a line naming the sources the model never
reached — those keep only their deterministic distillation, and the reader
should grep them rather than assume the memo covers them.

`model_total_s` (default 900) bounds the whole map phase; `model_step_timeout_s`
(240) bounds one source.

Tested without a model at all: `selftest.py` drives `map_sources` with a stub
generator that fails and stalls on command, checking that ordering holds, that
one bad source skips one file rather than the run, that the total deadline stops
it and names what was dropped, and that every source ends up in exactly one of
the two lists.

## Doctor — the overlap, and everything else nobody checks

```
/memo-guard:doctor
doctor.py --fix              # settings.json only, the two keys it names
doctor.py --clean-handoffs   # unfilled templates only
doctor.py --maintain
```

### Two tools, one job

memo-index's `ctx_watch` and memo-guard's `ctx_monitor` measure the same number,
the same way, from the same transcript, and both fire at 70%. Both then write a
handoff and tell the model to wind down. The visible cost is litter: `ctx_watch`
writes `.memo/HANDOFF.md` into whatever directory the session happened to be
standing in, on every tool call. This repository had accumulated **six** of them,
in six directories, every one still holding the unfilled template — the section
only a person can write, unwritten.

They are not redundant in every part, which is why doctor does not tell you to
delete them. `hook_gate.sh` does two jobs and only the first duplicates:

| `hook_gate.sh` job | verdict |
|---|---|
| context ceiling + `HANDOFF.md` | duplicated — memo-guard archives *and* compresses at the same point |
| "this project has an index, query it" | keep — that is about the project's corpus, not the session |

So the prescription is narrowing, not removal: drop the PostToolUse `ctx_watch`
entry, and set `MEMO_CTX_THRESHOLD=101` — a percentage that cannot be reached,
using the skill's own documented knob — so `hook_gate.sh` keeps only the job
memo-guard does not do. `--fix` does exactly those two things and nothing else;
an unrelated hook sharing the same group survives, and running it twice is a
no-op.

### The rest

- **A model server that answers but does not work.** `/api/tags` in a
  millisecond, `/api/embed` never. Every semantic path degrades to lexical and
  nothing says so.
- **An installed copy older than the source.** Installing *copies* into the
  plugin cache, so the hooks running in your sessions are the installed ones —
  an easy way to spend an afternoon testing a fix that is not running.
- **Autopilot's state and `settings.json` disagreeing.** These are two files
  that have to agree and nothing kept them agreeing; they drifted during
  development — state written under one `CLAUDE_CONFIG_DIR`, settings under
  another — leaving autopilot reporting ON while nothing would fire at all.
  Silent, total failure, one comparison to catch.
- **`blockers()` no longer lists `autoCompactWindow`.** It changes *where*
  compaction fires, it does not prevent it, and calibration already corrects
  for it. A handled caveat listed as a blocker teaches the reader to skim the
  list, which is how the real entries stop being read. It is a caveat now.

### Maintenance

`cognify` and `memify` existed and nothing ran them. Session end is the only
moment the machine is reliably idle and the store reliably complete, so
`archive_now.py` spawns `doctor.py --maintain-if-due` there. It rate-limits
itself to once a day (`maintain_every_h`) and **reports rather than deletes** —
a scheduled job that removes things is the one component nobody is watching.
`--hard` stays an explicit act.

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

1. `diagnose()` — one verdict with its evidence. `BUSY`, `WEDGED` and `SLOW`
   look identical from outside (nothing comes back) but need opposite
   responses, so they are separated by measurement.
2. `recover(1)` if degraded — eviction only, so a hook may run it unattended.
3. `ensure_room(model)` — evict what is in the way **before** the load, instead
   of discovering afterwards that the model went half onto the CPU.

Repair also triggers on a **stale lock**: a lock whose owner is gone means a job
died mid-model, which is the most common way to inherit a degraded server. The
next run breaks the lock, diagnoses, and repairs rather than inheriting it.

```bash
broker.py --diagnose            # OK | BUSY | SPILLED | SLOW | WEDGED | DOWN
broker.py --fit gemma4:12b      # would it fit, and what would be evicted
broker.py --recover --level 1   # evict spilled models      (safe, automatic)
broker.py --recover --level 2   # evict everything, re-probe (safe, automatic)
broker.py --recover --level 3   # restart the server        (never automatic)
```

Level 3 is deliberately excluded from automatic recovery: it kills a process the
user may be using for something else. It now also *starts one again* — killing
without starting is not a restart, and on a machine where the server is launched
by a session script rather than by launchd, nothing else brings it back. If a
request was in flight when level 3 ran, the result says so instead of leaving
the aborted job to be discovered later.

### Busy is not wedged

A server with one slot (`OLLAMA_NUM_PARALLEL=1`) serves one request at a time.
While a long generation holds that slot, every other client waits and then times
out — at the socket this is **identical** to a hung server, and the prescriptions
are opposite: wedged wants a restart, busy wants patience.

They are told apart by CPU time, not by asking the server: a runner that is
generating burns hundreds of milliseconds of CPU per wall second, an idle one
burns none. `busy_evidence()` samples `ps` twice and reports the delta.

This was not hypothetical. A memo-index run held the only slot for twenty
minutes while `/api/tags` answered in 3 ms; the doctor called the server wedged,
and the fix it printed — `--recover --level 3` — would have destroyed the job.
The doctor now reports that state as **info, not a warning**, and its advice is
to wait. Raising `OLLAMA_NUM_PARALLEL` is deliberately *not* recommended:
Ollama already sizes the slot count from free memory — the `1` on this machine
is its own auto-pick with 0.7 GB free and a 5.4 GB model — and a second slot
means a second KV cache, which trades a queue for thrashing. memo-guard's
circuit breaker already makes the semantic paths fail fast and fall back to
lexical for the duration, which is the intended behaviour, not a fault.

Evidence for BUSY requires **both** a runner burning CPU and another client
actually connected (`lsof`). CPU alone is not enough: loading a model burns CPU
too, and on a paging machine a 5 GB load outlasts the probe timeout — which
would make a merely-slow server look busy. Where `lsof` is unavailable the
verdict reports `known: false` rather than guessing.

An unmeasurable runner (no `ps`, no runner process) reports `known: false` and
is never read as "idle" — a missing measurement must not become evidence.

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
