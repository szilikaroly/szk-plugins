---
description: Mi jár le hamarosan — határidő-ellenőrzés, napi futtatásra is
allowed-tools: Bash
---
Show everything with a deadline inside the horizon: submissions, reviewer
letters, and sub-tasks. Run this exact command:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" due --days ${ARGUMENTS:-7}
```

It exits 1 when something is already overdue, 0 otherwise — so it also works as
a check in a cron job or a shell prompt.

## Jelentés

Report it almost verbatim, then say **one** thing: what to do first. Rank by
what is actually blocked, not just by date:

1. anything already overdue,
2. a reviewer deadline with unanswered points — that is real work, not a form,
3. a submission deadline where the manuscript is still `drafting`,
4. a submission deadline where the package is `ready` and only the sending is
   missing — that is minutes of work, so say so.

For a conference abstract deadline that has passed, do not assume it was
missed: the form may have gone out from an address the store cannot see. Say
what is verifiable ("no send recorded") and suggest checking, not that they
failed to submit.

## Napi futtatás

If the user wants to be told without asking, set it up as a scheduled task —
`/schedule` or the `schedule` skill — running

```
science-monitor due --days 7 --quiet
```

`--quiet` prints nothing when there is nothing to report, which is what makes a
daily job tolerable. Never create a schedule without the user asking for one.
