---
description: Response-to-reviewers dokumentum összeállítása a rögzített pontokból
allowed-tools: Bash, Read, Write, Edit, Skill
---
Build the point-by-point response letter from the stored reviewer points.

**Step 1.** See what is answered and what is not:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" review show REVIEW_ID
```

If points are still `open`, say so and ask whether to draft responses for them
now or emit the skeleton with TODO markers.

**Step 2.** Generate the markdown skeleton:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" respond REVIEW_ID
```

It writes `response_to_reviewers_rN.md` into the project directory, with every
point in order and whatever responses are already recorded.

**Step 3.** Fill and polish. Each response should:
- state plainly what was changed and where (section, table, line),
- quote the changed text when short,
- when disagreeing, say so directly with the reason and the evidence — a
  reasoned disagreement is a legitimate response, and pretending to comply is
  worse than arguing,
- thank the reviewer once, at the top, not per point.

Keep any response you write back in the store so it is not lost:
`sm.py review set --point ID --response "..." --state done`.

**Step 4.** If the user wants a `.docx` for the portal, use the **docx** skill
to convert. For language polish on the finished letter, the **academic-editor**
skill is the right tool — offer it, do not run it unasked.

**Step 5.** When the revision actually goes back to the journal:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" review set --review REVIEW_ID --state answered
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" submit SLUG --status revision_sent
```
