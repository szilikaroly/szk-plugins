# scripts

| Script | Deps | Does |
|---|---|---|
| `manuscript_check.py` | python-docx (for .docx) | deterministic pre-edit pass — counts, abbreviations, sentence outliers, passive density, p/P and ± splits, US/UK mix, register markers |
| `housestyle.py` | stdlib | measures the target journal's house style from its own recent OA papers; `--compare` measures a manuscript against that profile |
| `docx_tracked_edit.py` | lxml | applies `{find, replace, comment}` edits as real `w:ins`/`w:del` revisions with anchored comments |
| `docx_accept_changes.py` | lxml | accepts (or `--reject`s) every revision, producing the clean copy |

## edits.json

```json
[
  {"find": "increase risk of developing RBD",
   "replace": "increase the risk of developing RBD"},

  {"find": "the reducing score rates",
   "replace": "the changes",
   "comment": "Changed throughout this paragraph because you appear to be describing changes in general (some of which are increases) rather than reductions. Please check carefully.",
   "count": 0}
]
```

- `find` must match the manuscript **byte for byte** — curly quotes, en dashes, non-breaking
  spaces and double spaces included. A miss is reported, never guessed at.
- `count` is how many occurrences to change; `1` (default) or `0` for all of them.
- `comment` is optional; it anchors to the edited span and appears in Word's review pane.
- A match may span several runs with different formatting; the runs are split and the
  original `w:rPr` is carried onto each piece.

## What these scripts will not do

`docx_tracked_edit.py` skips text already inside a `w:ins` or `w:del`. Editing someone
else's pending revision would silently rewrite their proposal. Run it on a clean manuscript;
if the file already carries revisions, read them first and decide what to do with them.

`docx_accept_changes.py --reject` reports fewer deletions than `--accept` on the same file
when a deletion is nested inside an insertion — rejecting the insertion removes the nested
deletion with it. That is the semantics, not a miscount.

Neither script recalculates a word count in the manuscript's front matter. You cannot know
the count after the author accepts a subset of the changes; query for it instead, exactly as
the reference edit did.

## Verified round-trip

On the reference sample (`AJE-Sample-Premium-Editing.docx`, 979 insertions / 896 deletions /
11 comments): `--reject` reproduces the author's original text, `--accept` reproduces the
editor's final text, and every part of the resulting package is well-formed and reopens.
