---
description: Refute, supersede, pin or inspect a claim so it stays judged across sessions
argument-hint: refute|supersede|pin|check|list|forget <text>
allowed-tools: Bash
---
Manage cross-session claim verdicts with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claims.py"`.

The memo dir is rebuilt every session, so a claim you disprove today is regenerated
clean tomorrow unless it is recorded here. This store is the only thing that
persists a judgement.

Parse "$ARGUMENTS" and run the matching form:

- `refute <text>` → `--refute "<text>" --note "<why it is wrong>"`
  Use when a claim in a memo or RESUME is factually wrong. Always supply `--note`
  with the reason — the note is what a future session reads.
- `supersede <old> :: <new>` → `--supersede "<old>" --with "<new>" --note "..."`
  Use when the claim was right but is now outdated (a number changed, a decision
  was revised). The replacement text is what future memos will carry.
- `pin <text>` → `--pin "<text>" --note "..."`
  Use for a claim that must never be quietly rewritten — a decision the user made
  explicitly, a constraint that keeps getting forgotten.
- `check <text>` → `--check "<text>"`
  Ask whether a claim would be blocked. Do this before asserting something that
  feels like it might have been settled before.
- `list` (or empty arguments) → `--list`
  Show every verdict and its `hits` count — how many times each blocked claim
  tried to come back.
- `forget <fingerprint>` → `--forget <fp>`
  Remove a verdict. Only when the verdict itself was wrong.

If no arguments were given, run `--list` and summarise.

Two rules when reporting back:
- Quote the `hits` number when it is above zero. A claim that has tried to return
  three times is evidence the mechanism is earning its place, and the user should
  know which errors keep resurfacing.
- Never record a verdict on the user's behalf without saying which text you
  matched. Fuzzy matching means you may have caught a neighbouring claim.
