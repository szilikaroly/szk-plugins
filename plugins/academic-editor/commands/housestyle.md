---
description: Célfolyóirat házistílusának mérése a saját friss cikkeiből
allowed-tools: Bash, Read
---
Measure a journal's house style. Journal / request: $ARGUMENTS

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/housestyle.py" --journal "<NAME>" \
    --n 12 --years 3 --out journal-profile.json --md journal-profile.md
```

Use `--issn` instead of `--journal` when the title is ambiguous, and `--type review` or
`--type research` when the manuscript being prepared is one or the other — a journal's
reviews and its research papers do not read alike, and profiling the wrong half gives the
author advice that will not match their own article type.

To measure a manuscript against a profile you already built:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/housestyle.py" --profile journal-profile.json --compare <MANUSCRIPT>
```

Report the profile honestly:

- give the sample size, and if fewer than 3 full texts were obtainable, say the profile is
  not usable as an average and stop treating it as one;
- read out only the rows where the sample is unambiguous (≥90%); the "vegyes" ones mean the
  journal itself is inconsistent, so there is nothing to match;
- pair every ⚠ from `--compare` with both numbers when you tell the author about it.
