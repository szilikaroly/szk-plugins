---
description: Beadás rögzítése — folyóirat, cover letter állapota, beküldve-e
allowed-tools: Bash, Read, Glob
---
Record or update a submission attempt.

`$ARGUMENTS` is normally just a slug; everything else you ask for or infer.

**What must end up recorded**, and these are three separate things — do not
collapse them:
1. the journal (and, if known, the portal and the journal-side manuscript ID),
2. the **cover letter**: does a file exist, and is it `draft` or `ready`,
3. whether the package was **actually submitted**, and on what date.

**Step 1.** Show the current state:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" show SLUG
```

**Step 2.** Fill the gaps. Look for a cover letter on disk first — search the
project's directory for `cover*letter*` — and only ask the user about what you
genuinely cannot determine. Ask all your questions in one message.

**Step 3.** Write it, using only the flags you have real values for:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" submit SLUG \
  --journal "Journal Name" --portal "Editorial Manager" --ms-id "ABCD-25-0123" \
  --cover "/path/to/cover_letter.docx" --cover-state ready \
  --status ready --due 2026-09-30
```

Add `--sent` (optionally `--date YYYY-MM-DD`) **only** when the user confirms
the package actually went out — `--sent` flips the submitted flag and sets the
status to `submitted`. Never infer submission from the existence of files.

Sending the same manuscript to a different journal after a rejection: pass the
new `--journal`, which opens a fresh attempt and keeps the old one in the
history. Use `--new` to force a new attempt at the same journal.

Statuses: `drafting`, `ready`, `submitted`, `under_review`, `major_revision`,
`minor_revision`, `revision_sent`, `accepted`, `rejected`, `withdrawn`.

**Step 4.** Report the resulting line back, and if the cover letter is missing
or a draft, say so plainly — that is the usual thing blocking a submission.
