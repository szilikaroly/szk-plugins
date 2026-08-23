---
description: Teljes kritikai értékelés — vázlat, kitöltés a cikkből, ellenőrzés, összegzés
allowed-tools: Bash, Read, Write
---
Run a full appraisal. Target and request: $ARGUMENTS

1. **Route** (`--route`) and state the instrument and the unit of assessment.
2. **Fix the comparator**: the target trial (ROBINS-I), the preliminary considerations
   (ROBINS-E), PICOTS (PROBAST), or the review question (QUADAS-2). Write down the confounder
   list **before** reading the paper's adjustment table.
3. **Print the slots** and save them:

```
A="${CLAUDE_PLUGIN_ROOT}/scripts/appraise.py"
python3 "$A" --skeleton <TOOL> --scope <SCOPE> > appraisal.md
```

4. **Fill every row from the paper**, quoting the sentence or naming the section. "No
   information" is a real answer — use it rather than inferring. Watch the polarity tags in the
   reference file: some questions are worded so that Yes is the problem, and some only route.
5. **Verify and roll up**:

```
python3 "$A" --verify appraisal.md --tool <TOOL> --scope <SCOPE>
python3 "$A" --rollup appraisal.md --tool <TOOL> --scope <SCOPE>
```

6. **Report one row per signalling question**, then the domain verdicts with a sentence each,
   then the overall with a paragraph. If you override what the rollup computed, say so and say
   why — silently smoothing over a flag is the failure this whole tool exists to prevent.

Never sum or average the domains. Most of these instruments have no total, and the ones that
look like they do (Newcastle-Ottawa) publish no threshold for it.
