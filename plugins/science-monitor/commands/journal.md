---
description: Célújság választás — folyóirat-illesztés egy kézirathoz
allowed-tools: Bash, Read, WebSearch, WebFetch, Skill, Glob
---
Find the journals a manuscript should actually go to. This is what the
dashboard's **Célújság** button and the post-rejection **Célújság választás**
step call.

`$ARGUMENTS` is a slug. Without one, run `sm.py gaps` and offer the manuscripts
that were rejected or have no journal yet.

## Step 1 — know the manuscript and its history

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" show SLUG
```

The submission history is the important part. A manuscript that already
collected a **desk rejection** and a **post-review rejection** needs a
different search from a fresh one:

- **Desk rejection** — the editor never sent it out. That is almost always
  scope, article type or format, not science. Look for journals whose published
  output actually contains work like this, and check the article type exists
  there at the length the manuscript is.
- **Post-review rejection** — reviewers engaged and said no. Read the stored
  review points (`sm.py review show ID`) before proposing anything; the reason
  they gave usually constrains where it can go next.

Read the manuscript's abstract and title (use **doc-tools** for `.docx`). You
need the actual claim, not the topic.

## Step 2 — find candidates from evidence, not memory

Do **not** propose journals from recall — impact factors and scopes drift, and
a wrong suggestion costs the user a submission cycle. Use:

- the **the-collector** or **pubmed-search** skill to find where comparable
  papers on this exact claim were published in the last 3 years,
- OpenAlex for the journals publishing that set (`api.openalex.org/works?filter=...`),
- the journal's own site for the article types, word limits and current scope.

For every candidate confirm, with a source: article type exists and fits the
manuscript's length; the scope covers the claim; open-access fee and whether the
user's institution has an agreement; and typical time to first decision if the
journal publishes it.

## Step 3 — rank and report

Give the user a short table in Hungarian: journal · why it fits · article type
and word limit · fee · what would need changing. Rank by fit, not by impact
factor, and say plainly when a candidate is a stretch.

Name the ones you rejected and why — "nem publikál Hypothesis and Theory
típust" is as useful as a recommendation.

## Step 4 — record the choice

Only after the user picks:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" submit SLUG --journal "..." --new
```

`--new` opens a fresh submission round and keeps the rejected one in the
history. Then set the state and note what has to change:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" state SLUG korrekcio
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" submit SLUG --notes "..."
```

Do not pick the journal for the user, and never record one they have not
confirmed.
