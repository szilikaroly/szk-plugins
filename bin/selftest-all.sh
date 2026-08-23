#!/usr/bin/env bash
# Run every plugin's self test. Exit 0 only if all of them pass.
#
# Each suite is offline and deterministic: no network, no API key, no clock
# dependence. That is deliberate — a test suite that needs the internet stops
# being run, and a suite that is not run is not a suite.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

FAILED=()
PASSED=()
SKIPPED=()

for suite in plugins/*/scripts/selftest.py; do
    name="$(basename "$(dirname "$(dirname "$suite")")")"
    printf '\n\033[1m=== %s ===\033[0m\n' "$name"
    if out=$(cd "$(dirname "$suite")" && python3 selftest.py 2>&1); then
        echo "$out" | tail -1
        PASSED+=("$name")
    else
        echo "$out" | grep -E '^\s+FAIL|FAILURES|Traceback|Error' | head -20
        FAILED+=("$name")
    fi
done

# The validator carries two engines and a count guard that compares each parsed
# item list against the published total. It has already caught two real parsing
# bugs; run it here so a reference-file edit cannot silently shrink an instrument.
printf '\n\033[1m=== validator: item counts ===\033[0m\n'
if (cd plugins/validator/scripts && python3 appraise.py --counts && python3 checklist.py --counts | tail -1); then
    PASSED+=("validator-counts")
else
    FAILED+=("validator-counts")
fi

printf '\n\033[1m---\033[0m\n'
printf 'passed:  %s\n' "${PASSED[*]:-none}"
[ ${#SKIPPED[@]} -gt 0 ] && printf 'skipped: %s\n' "${SKIPPED[*]}"
if [ ${#FAILED[@]} -gt 0 ]; then
    printf '\033[31mFAILED:  %s\033[0m\n' "${FAILED[*]}"
    exit 1
fi
printf '\033[32mall suites passed\033[0m\n'
