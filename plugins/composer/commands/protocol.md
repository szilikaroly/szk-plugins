---
description: PROSPERO protokoll — váz, jogosultság-ellenőrzés, szakasztábla, export
allowed-tools: Bash, Read, Edit
---
Manage the PROSPERO protocol record. Request: $ARGUMENTS

```
P="${CLAUDE_PLUGIN_ROOT}/scripts/prospero.py"
python3 "$P" fields                                        # the 36 registration fields
python3 "$P" init --project <slug> --title "<title>"       # scaffold
python3 "$P" check --protocol <file>                       # eligibility + completeness
python3 "$P" stage --protocol <file> --set formal_screening=started
python3 "$P" export --protocol <file> --out protocol.md    # submission-ready
```

Fill the fields *with* the user, one block at a time — review question,
population, intervention/exposure, comparator, outcomes, study types, synthesis
strategy, risk-of-bias tool. Do not invent content for a protocol: every field
here is a commitment the user will be held to.

Two things to say out loud rather than bury in the output:

- If `check` reports the review type is ineligible (narrative, scoping,
  literature, mapping), PROSPERO will not register it. Point at OSF Registries
  and make sure the manuscript does not claim a PROSPERO registration.
- If the stage table shows data extraction has started, the registration window
  is closed. The honest option is to state in the manuscript that the review was
  not prospectively registered.

For the risk-of-bias field, the `validator` plugin's instrument router picks the
right tool for the planned study designs — name the actual instrument
(RoB 2 / ROBINS-I / ROBINS-E / QUADAS-2 / PROBAST / AMSTAR 2 …), not
"risk of bias will be assessed".
