---
description: Beérkező bírálat vagy javítási igény felvétele és pontokra bontása
allowed-tools: Bash, Read, Write, Glob, Skill
---
Turn an incoming reviewer/editor letter into tracked, answerable points. This is
the fast path from "megjött a review" to "tudom, mit kell csinálni".

`$ARGUMENTS`: `SLUG [letter file path]`. If no path is given, ask the user to
paste the letter or point at the file. If they pasted it into the chat, write it
to a file in the scratchpad first, then use `--file`.

**Step 1 — record the letter.**

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" review add SLUG \
  --file /path/to/letter.txt --decision major_revision \
  --due 2026-10-15 --received 2026-08-02 --editor "Name" --source manual
```

`--decision` must be one of `major_revision`, `minor_revision`, `accepted`,
`rejected` — it also updates the submission's status and deadline. Use
`--source gmail` when the letter came from `/science-monitor:inbox`. Note the review id it
prints.

For `.docx`/`.pdf` letters use the **doc-tools** skill to extract the text
first, and pass the extracted `.txt` to `--file` (keep the original too).

**Step 2 — split it into points.** Read the letter and decompose it into
individual, actionable reviewer comments. Write a JSON array to the scratchpad:

```json
[
  {"reviewer": "R1", "idx": 1, "severity": "major",
   "comment": "The sample size justification is missing.",
   "targets": "Methods §2.3",
   "action": ""},
  {"reviewer": "R1", "idx": 2, "severity": "normal", "comment": "..."},
  {"reviewer": "R2", "idx": 1, "severity": "minor", "comment": "..."}
]
```

Rules for the split:
- One row per thing that requires a distinct change or answer. A reviewer
  paragraph raising three issues becomes three rows.
- `reviewer`: `Ed` for the editor, `R1`, `R2`, … for reviewers, in the letter's
  own order.
- `comment`: the reviewer's own wording, condensed but not reinterpreted. Do
  not soften a criticism and do not add your own judgement here.
- `severity`: `major` if it can block acceptance (new analysis, missing data,
  a challenged claim), `normal`, or `minor` (wording, formatting, typos).
- `targets`: which section/table/figure it touches, if the letter says or it is
  obvious. Leave empty rather than guessing.
- Leave `response` and `action` empty — those get filled while working.

Load them:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" review points REVIEW_ID --json /path/points.json
```

**Step 3 — triage and report.** Run `sm.py review show REVIEW_ID`, then give
the user a Hungarian briefing:
- how many points, split by reviewer and by severity,
- the `major` ones listed explicitly — these decide the outcome,
- which ones need new analysis or new data (real work) versus text-only fixes,
- your estimate of what is genuinely contestable, if anything,
- the deadline and days remaining.

Then ask which point to start with. **Do not start rewriting the manuscript in
this command.**

**While working a point**, record progress:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" review set --point POINT_ID \
  --response "We have added ..." --action "Methods §2.3 rewritten, Table 2 added" \
  --state done
```

Point states: `open`, `drafted`, `done`, `declined` (use `declined` when you
argue against the reviewer rather than complying — the response still needs to
be written).
