---
description: Check what must not survive into a submitted file — placeholders, tracked changes, comments, word/reference limits, disclosures that belong on the form
allowed-tools: Bash
---
Check the mechanical submission blockers. Arguments: $ARGUMENTS

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" submission MANUSCRIPT --journal generic
```

If the user names a target journal and a profile exists (`pc.py journals`), pass
`--journal <name>` — the word, reference and figure ceilings and the
article-type rules all come from the profile, so a generic run cannot check them.

This category flags:

- **placeholders still in the text** — `TBD`, `TODO`, `XXX`, `[insert …]`, and an
  ellipsis stranded mid-sentence (`an RCT of…,`). An editor reading one assumes
  the draft was not finished.
- **tracked changes and comments still in the .docx** — the journal opens the
  file that was uploaded, not the view the author was working in. This reads the
  raw package, so it sees revisions python-docx silently accepts.
- **the declared word count** — `Word Count: N` on the title page against the
  format's limit. An order-of-magnitude typo here is common and embarrassing;
  so is a number left over from an earlier draft. When the body can be isolated
  it is also measured and compared, reported as an estimate.
- **reference and figure ceilings** — over the limit is an error, because it
  usually means a reference has to be *swapped*, not added, when an editor asks
  for a new one.
- **disclosures that do not belong in this article type** — an opinion or
  commentary format normally carries no ethics-approval, consent or trial
  registration block in the manuscript; those go on the disclosure form the
  journal publishes alongside the article.

Report every ERROR first — each one is visible to the editor the moment the file
is opened. For a .docx, if tracked changes or comments are found, say so plainly
and say how many, with the author name: that is almost always an accident.
