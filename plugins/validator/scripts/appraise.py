#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One engine for every risk-of-bias / quality / certainty instrument.

    appraise.py --list
    appraise.py --route "randomised controlled trial"
    appraise.py --skeleton rob2
    appraise.py --skeleton robins-i --scope all
    appraise.py --verify draft.md --tool rob2
    appraise.py --rollup  draft.md --tool rob2
    appraise.py --migrate old.md  --tool robins-i --scope adherence > new.md
    appraise.py --counts

Three jobs, and the split matters
---------------------------------
**skeleton** prints every slot that must be filled. **verify** reads a finished
appraisal back and names what was left blank. **rollup** applies the instrument's
own published algorithm to the recorded answers and computes the domain and
overall judgements.

The characteristic failure of a 22- or 34-item instrument is not a wrong answer;
it is a silently missing one. A domain assessed on two of its four questions
still produces a confident-looking rating, and nothing in the output says which
question was never asked. So the model can be wrong about an answer; it should
not be able to be wrong about *whether it answered* — and a domain with an
unanswered question gets no verdict at all (INCOMPLETE), never a LOW computed
from the questions that happened to be answered.

And where the instrument publishes an algorithm — RoB 2's per-domain walk,
AMSTAR 2, the Newcastle-Ottawa star count, GRADE's start-and-adjust — the verdict
is arithmetic, not judgement.
Computing it here means the judgement can be checked against the answers, and a
rating that does not follow from them is visible instead of plausible.

Item lists, answer vocabularies, shorthands and the old-to-new id maps are
PARSED FROM references/*.md, never duplicated in this file. A second copy drifts
from the reference the moment either is edited, and two sources disagreeing
silently is worse than having no script at all.

Exit codes
----------
0  complete, and the verdict is final;
1  something is missing, invalid, undecided (GRADE publication bias), or the file
   uses an item numbering that has since changed — the output says which;
2  usage error: unknown --scope, or an instrument that runs on checklist.py.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REF = Path(__file__).resolve().parent.parent / "skills" / "validator" / "references"

#: `**1.1 (all) — question**`, `**3c (D;E)** — question`, `**1.1 — question**`.
#: One pattern for every reference file: a second pattern is a second source of
#: truth about what an item looks like.
#: The id must contain a digit somewhere. Without that, any bold line of the
#: shape `**Note — something**` parses as an item and the instrument silently
#: grows slots the published tool does not have. The lookahead goes BEFORE the
#: first character, not after it: placed after, it demanded a digit in position
#: two, so AMSTAR 2's single-digit items 1-9 and ROBIS's phase-3 items 3A-3C
#: vanished — 7 of 16 and 21 of 24 parsed, and only the --counts check made that
#: visible.
ITEM_RE = re.compile(
    r"^\*\*(?P<id>(?=[\w.\-]*\d)[A-Za-z0-9][\w.\-]*)\s*"
    r"(?:\((?P<scope>[^)]*)\))?\s*"
    r"(?:\*\*)?\s*[—–-]\s*"
    r"(?P<text>.+?)\s*$")
#: The heading word is part of the group's identity. ROBIS has a "Domain 3" and a
#: "Phase 3"; keyed by the number alone, the phase heading overwrote the domain's
#: title and its three items were scored as part of domain 3.
DOMAIN_RE = re.compile(
    r"^##+\s*(?P<kind>Domain|Phase|Section|Item group)\s*(?P<num>[\w.]+)\s*[—–-]\s*"
    r"(?P<name>.+?)\s*$", re.I)
META_RE = re.compile(r"^\s*(\w[\w\-]*)\s*:\s*(.+?)\s*$")

#: Every instrument accepts these as "not applicable" unless an item's own
#: vocabulary (meta `item_answers`) says otherwise.
NA_TOKENS = ("N/A", "NA", "Not applicable")

YES_ISH = frozenset({"yes", "probably yes", "partial yes"})
NO_ISH = frozenset({"no", "probably no"})
UNKNOWN = frozenset({"no information", "unclear"})
#: QUIPS's middle level. It is an answer, and it is not "no problem".
PARTLY = frozenset({"partly"})
#: ROBINS-E's graded No (PMC11098530, section 3): the weak form keeps the problem
#: small enough for the middle tier, the strong form is the top tier.
WEAK_NO = frozenset({"weak no"})
STRONG_NO = frozenset({"strong no"})

#: The answer codes a routing condition may name: "If Y/PY/NI to 2.1 or 2.2:".
_COND_CODES = r"(?:PY|PN|NI|WN|SN|Y|N)"
#: A question that opens with its routing condition. "If applicable, and if …"
#: (RoB 2's adherence 2.3) keeps N/A open even when the condition holds.
_COND_LEAD = re.compile(
    rf"^\s*if\s+(?P<optional>applicable,?\s*(?:and\s+)?if\s+)?"
    rf"(?P<body>{_COND_CODES}(?:/{_COND_CODES})*\s+to\s+[^:?]*?)\s*[:?]", re.I)
_COND_CLAUSE = re.compile(
    rf"(?<![\w/])(?P<codes>{_COND_CODES}(?:/{_COND_CODES})*)\s+to\s+"
    rf"(?P<ids>[0-9][\w.]*(?:\s*(?:,|\bor\b|\band\b)\s*[0-9][\w.]*)*)", re.I)


def _canonical(answer: str) -> str:
    t = answer.strip().lower()
    return "n/a" if t in ("n/a", "na", "not applicable") else t


def _pairs(spec: str, sep: str) -> list[tuple[str, str]]:
    """`a=b; c=d` -> [(a, b), (c, d)] — the shape of every list-valued meta key."""
    out = []
    for part in spec.split(";"):
        if sep in part:
            k, v = part.split(sep, 1)
            if k.strip() and v.strip():
                out.append((k.strip(), v.strip()))
    return out


def _ids(spec: str) -> list[str]:
    return [x.strip() for x in spec.split(",") if x.strip()]


# --------------------------------------------------------------------------- model


class Lines(list):
    """The printed lines of a rollup, plus whether the verdict in them is final.

    A list subclass so that `"\\n".join(rollup_x(...))` keeps working; `final`
    decides the exit code of --rollup.
    """
    final: bool = True


class Instrument:
    def __init__(self, path: Path):
        self.path = path
        self.meta: dict[str, str] = {}
        self.items: list[dict] = []
        self.domains: dict[str, str] = {}
        self.labels: dict[str, str] = {}
        self._parse()
        self._vocabulary()
        self._check_ids()
        self._conditions()

    def _parse(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        block = re.search(r"<!--(.*?)-->", text, re.S)
        if block:
            for line in block.group(1).splitlines():
                m = META_RE.match(line)
                if m:
                    self.meta[m.group(1)] = m.group(2)
        domain = ""
        heading = ""
        for line in text.splitlines():
            d = DOMAIN_RE.match(line)
            if d:
                kind = d.group("kind").capitalize()
                num = d.group("num")
                key = num if kind == "Domain" else f"{kind[0]}{num}"
                name = d.group("name")
                # PROBAST+AI repeats domain 4 per pass on purpose; it runs on
                # checklist.py, which reads the passes apart.
                if key in self.domains and self.domains[key] != name \
                        and not self.meta.get("engine"):
                    raise ValueError(f"{self.path.name}: group '{key}' is defined twice "
                                     f"('{self.domains[key]}' and '{name}')")
                self.domains[key] = name
                self.labels[key] = f"{kind} {num}"
                domain = key
                continue
            if line.startswith("##"):
                # A reference file may group its items under ordinary headings —
                # JBI's are one checklist per design, not "Domain 1". Remember the
                # heading so those items land in a named group instead of one
                # undifferentiated "Items" block.
                heading = re.sub(r"^#+\s*", "", line).split("—")[0].strip()
                domain = ""
            m = ITEM_RE.match(line)
            if m:
                text_ = m.group("text").rstrip("*").strip()
                key = domain or m.group("id").split(".")[0]
                if not domain and heading:
                    self.domains.setdefault(key, heading)
                self.items.append({
                    "id": m.group("id"),
                    "scope": (m.group("scope") or "all").strip(),
                    "text": text_,
                    "domain": key,
                })

    def _vocabulary(self) -> None:
        """Per-instrument answer tables. There is no global normaliser.

        "PY" meant "probably yes" everywhere in 1.x — including AMSTAR 2, where it
        is the published shorthand for *Partial yes*, and the Newcastle-Ottawa
        scale, which has no "probably". A critical AMSTAR 2 item marked PY was
        then read as a full Yes and vanished from the rating. Each reference file
        now declares its own shorthands (meta `aliases`) and nothing else is
        accepted.
        """
        self.canon: dict[str, str] = {}      # lower-case token -> canonical answer
        self.spelling: dict[str, str] = {}   # lower-case token -> the token as written in the vocabulary
        for a in self.answers + list(NA_TOKENS):
            self.canon[a.lower()] = _canonical(a)
            self.spelling[a.lower()] = a
        for short, full in _pairs(self.meta.get("aliases", ""), "="):
            self.canon[short.lower()] = _canonical(full)
            self.spelling[short.lower()] = short
        # Keys are an item id, or `scope/id` where one id names different questions
        # in different scopes (RoB 2's 2.6 is unconditional for the effect of
        # assignment and conditional for the effect of adhering).
        self.item_vocab: dict[str, set[str]] = {}
        for ids, vals in _pairs(self.meta.get("item_answers", ""), "="):
            allowed = {_canonical(v) for v in vals.split("|") if v.strip()}
            for iid in _ids(ids):
                self.item_vocab[iid] = allowed
        # `not_applicable`: the only items that may be answered N/A (or `none`).
        # Absent, N/A is accepted everywhere. In 2.0.0 RoB 2 and ROBIS had no such
        # line, so a record with every answer N/A verified complete and rolled up
        # LOW — 22 unassessed questions read as a clean trial.
        na = self.meta.get("not_applicable")
        self.na_items: set[str] | None = (
            None if na is None else {x.lower() for x in _ids(na) if x.lower() != "none"})
        # `restricted_answers`: words of the vocabulary that only the items listed
        # in `item_answers` offer — ROBINS-E's weak and strong No exist on its
        # first confounding question, not on every question of the tool.
        self.restricted: set[str] = {
            _canonical(a) for a in self.meta.get("restricted_answers", "").split("|")
            if a.strip()}
        toks = sorted(self.spelling.values(), key=len, reverse=True)
        self.token_re = re.compile(
            r"(?<![\w/])(" + "|".join(re.escape(t) for t in toks) + r")(?![\w/])", re.I)

    def _check_ids(self) -> None:
        """Within one scope an id names exactly one question.

        RoB 2's adherence variant reuses the published ids 2.1-2.6 for different
        questions; that is legal only because the two variants are never in the
        same scope.
        """
        if self.meta.get("engine"):
            return
        for sc in set(self.scope_names) | {"all"}:
            seen: set[str] = set()
            for it in self.scoped(sc):
                if it["id"] in seen:
                    raise ValueError(f"{self.path.name}: item id {it['id']} occurs twice "
                                     f"in scope '{sc}'")
                seen.add(it["id"])

    def _conditions(self) -> None:
        """Parse each question's routing condition ("If Y/PY to 2.2 and 2.3, or N/PN to 2.4:").

        Stored on the item as `cond`: OR-ed (or AND-ed) clauses, each a set of
        canonical answers and the ids it applies to (any of "2.2 or 2.3", all of
        "2.2 and 2.3"). The condition is the item's own text, so it cannot drift
        from what the question says; a condition naming an answer the instrument
        does not have, or an id it does not have, is a load error.
        """
        if self.meta.get("engine"):
            return
        known = {it["id"] for it in self.items}
        for it in self.items:
            m = _COND_LEAD.match(it["text"])
            if not m:
                continue
            body = m.group("body")
            clauses, joins, last = [], [], 0
            for c in _COND_CLAUSE.finditer(body):
                if clauses:
                    joins.append(body[last:c.start()])
                last = c.end()
                ids_txt = c.group("ids")
                if re.search(r"\band\b", ids_txt, re.I) and re.search(r"\bor\b", ids_txt, re.I):
                    raise ValueError(f"{self.path.name}: item {it['id']}: condition "
                                     f"'{body}' mixes 'and' and 'or' in one clause")
                ids = [x for x in re.split(r"\s*(?:,|\bor\b|\band\b)\s*", ids_txt, flags=re.I)
                       if x]
                codes = set()
                for code in c.group("codes").split("/"):
                    full = self.canon.get(code.lower())
                    if full is None:
                        raise ValueError(f"{self.path.name}: item {it['id']}: condition names "
                                         f"'{code}', which is not an answer of this instrument")
                    codes.add(full)
                for i in ids:
                    if i not in known:
                        raise ValueError(f"{self.path.name}: item {it['id']}: condition names "
                                         f"item {i}, which this instrument does not have")
                clauses.append((frozenset(codes), ids,
                                "all" if re.search(r"\band\b", ids_txt, re.I) else "any"))
            if not clauses:
                raise ValueError(f"{self.path.name}: item {it['id']}: unreadable condition "
                                 f"'{body}'")
            ors = [j for j in joins if re.search(r"\bor\b", j, re.I)]
            ands = [j for j in joins if re.search(r"\band\b", j, re.I)]
            if ors and ands:
                raise ValueError(f"{self.path.name}: item {it['id']}: condition '{body}' "
                                 f"mixes 'and' and 'or' between clauses")
            it["cond"] = {"clauses": clauses, "mode": "all" if ands else "any",
                          "text": f"If {body}", "optional": bool(m.group("optional"))}

    def reached(self, items: list[dict], valid: dict[str, str]) -> dict[str, bool | None]:
        """For each item: is it asked, given the answers before it? None = cannot tell yet.

        An unconditional question is always asked. A conditional one is asked when
        its condition holds on the answers of questions that were themselves asked:
        an answer recorded at a question the routing never reached counts as N/A,
        so a stray "No" there cannot open the next question either.
        """
        in_scope = {it["id"] for it in items}
        state: dict[str, bool | None] = {}

        def value(rid: str) -> str | None:
            if rid not in in_scope or state.get(rid) is False:
                return "n/a"
            a = valid.get(rid)
            return None if a is None else self.norm(a)

        for it in items:
            c = it.get("cond")
            if not c:
                state[it["id"]] = True
                continue
            results = []
            for codes, rids, mode in c["clauses"]:
                vals = [value(r) for r in rids]
                if mode == "any":
                    results.append(True if any(v in codes for v in vals if v is not None)
                                   else None if None in vals else False)
                else:
                    results.append(False if any(v not in codes for v in vals if v is not None)
                                   else None if None in vals else True)
            if c["mode"] == "any":
                state[it["id"]] = True if True in results else None if None in results else False
            else:
                state[it["id"]] = False if False in results else None if None in results else True
        return state

    def na_where_asked(self, items: list[dict], valid: dict[str, str]) -> list[dict]:
        """Conditional questions answered N/A although their condition holds."""
        reach = self.reached(items, valid)
        return [it for it in items
                if it.get("cond") and not it["cond"]["optional"] and reach.get(it["id"])
                and it["id"] in valid and self.norm(valid[it["id"]]) == "n/a"]

    # ------------------------------------------------------------ properties

    @property
    def key(self) -> str:
        return self.meta.get("tool", self.path.stem)

    @property
    def name(self) -> str:
        return self.meta.get("name", self.key)

    @property
    def short_name(self) -> str:
        return self.name.split(" (")[0].split(" — ")[0]

    @property
    def answers(self) -> list[str]:
        return [a.strip() for a in self.meta.get("answers", "Yes|No").split("|")]

    @property
    def verdicts(self) -> list[str]:
        return [v.strip() for v in self.meta.get("verdicts", "Low|High|Unclear").split("|")]

    @property
    def scope_names(self) -> list[str]:
        return [s.lower() for s in _ids(self.meta.get("scopes", ""))]

    @staticmethod
    def tags(item: dict) -> set[str]:
        return {t.strip().lower() for t in re.split(r"[;,/]", item["scope"])}

    def valid_scope(self, scope: str) -> bool:
        return (scope or "all").strip().lower() in set(self.scope_names) | {"all"}

    def resolve_scope(self, scope: str) -> str:
        s = (scope or "all").strip().lower()
        if s == "all":
            s = self.meta.get("default_scope", "all").strip().lower()
        return s

    def scoped(self, scope: str) -> list[dict]:
        s = self.resolve_scope(scope)
        if s == "all":
            return list(self.items)
        return [it for it in self.items if {"all", s} & self.tags(it)]

    def heading(self, dom: str, skeleton: bool = False) -> str:
        lab = self.labels.get(dom, "")
        if lab and not lab.startswith("Domain "):
            return lab
        if skeleton:
            return f"{self.meta.get('group_label', 'Domain')} {dom}"
        return f"Domain {dom}"

    # ------------------------------------------------------------ answers

    def spell(self, token: str) -> str | None:
        """The vocabulary spelling of a recognised answer, or None."""
        return self.spelling.get(token.strip().lower())

    def norm(self, token: str) -> str:
        t = token.strip().lower()
        return self.canon.get(t, t)

    def _keys(self, it: dict) -> list[str]:
        """The vocabulary keys of an item, most specific first: `scope/id`, then `id`."""
        return [f"{t}/{it['id']}" for t in sorted(self.tags(it))] + [it["id"]]

    def item(self, iid: str, scope: str = "all") -> dict | None:
        return next((it for it in self.scoped(scope) if it["id"] == iid), None)

    def vocab_of(self, it: dict | None) -> set[str] | None:
        """The answers an item accepts (canonical), or None for "the whole vocabulary"."""
        if it is None:
            return None
        for k in self._keys(it):
            if k in self.item_vocab:
                return self.item_vocab[k]
        if self.na_items is None and not self.restricted:
            return None
        allowed = {_canonical(a) for a in self.answers} - self.restricted
        if self.na_items is None or any(k.lower() in self.na_items for k in self._keys(it)):
            allowed.add("n/a")
        return allowed

    def allowed(self, iid: str, scope: str = "all") -> set[str] | None:
        return self.vocab_of(self.item(iid, scope))

    def invalid_item(self, it: dict, token: str) -> bool:
        vocab = self.vocab_of(it)
        return vocab is not None and self.norm(token) not in vocab

    def invalid(self, iid: str, token: str, scope: str = "all") -> bool:
        return self.invalid_item(self.item(iid, scope) or {"id": iid, "scope": "all"}, token)

    def allowed_text(self, iid: str, scope: str = "all") -> str:
        vocab = self.allowed(iid, scope)
        if vocab is None:
            return " / ".join(self.answers + ["N/A"])
        order = [a for a in self.answers + ["N/A"] if _canonical(a) in vocab]
        return " / ".join(order)

    def answer_rules(self, scope: str) -> list[str]:
        """The per-item restrictions that apply in this scope, for the skeleton."""
        items = self.scoped(scope)
        out = []
        for ids, vals in _pairs(self.meta.get("item_answers", ""), "="):
            here = [i.split("/")[-1] for i in _ids(ids)
                    if any(i in self._keys(it) for it in items)]
            if here:
                out.append(f"{', '.join(here)}: {vals.replace('|', ' / ')}")
        if self.na_items is not None:
            na = [it["id"] for it in items
                  if any(k.lower() in self.na_items for k in self._keys(it))]
            out.append("N/A only at " + ", ".join(na) + " — a conditional question whose "
                       "condition is not met; every other item needs an answer"
                       if na else "N/A is not an answer in this instrument")
        if self.restricted:
            words = [a for a in self.answers if _canonical(a) in self.restricted]
            out.append(f"{' / '.join(words)} only where an item lists them above")
        return out

    def shorthand_text(self) -> str:
        return ", ".join(f"{k} = {v}" for k, v in _pairs(self.meta.get("aliases", ""), "="))

    # ------------------------------------------------------------ legacy ids

    def legacy_map(self) -> dict[str, list[str]]:
        return {k: [x.strip() for x in v.split("+") if x.strip()]
                for k, v in _pairs(self.meta.get("legacy_map", ""), ">")}

    def legacy_retired(self) -> list[str]:
        return _ids(self.meta.get("legacy_retired", ""))

    def legacy_cues(self) -> dict[str, str]:
        return dict(_pairs(self.meta.get("legacy_cue", ""), "="))

    def legacy_new_only(self) -> list[str]:
        return _ids(self.meta.get("legacy_new_only", ""))


def load_all() -> dict[str, Instrument]:
    if not REF.exists():
        sys.exit(f"nincs referencia könyvtár: {REF}")
    out: dict[str, Instrument] = {}
    for p in sorted(REF.glob("*.md")):
        inst = Instrument(p)
        if inst.items:
            out[inst.key] = inst
    return out


# --------------------------------------------------------------------------- router

#: design keyword -> (tool key, why). The router exists because picking the wrong
#: instrument is the most expensive mistake available here: an appraisal done with
#: the wrong tool is not a weak appraisal, it is an inapplicable one, and reviewers
#: notice. Ordered — the first match wins, so the specific patterns come first.
#: "non-randomised" contains "randomised" after a word boundary (the hyphen), so
#: the RoB 2 pattern refuses a match preceded by non-/quasi-; without that, an
#: explicitly non-randomised study was routed to RoB 2 first, or only to RoB 2.
_NOT_RANDOM = r"(?<!non-)(?<!non )(?<!quasi-)(?<!quasi )"
ROUTES: list[tuple[str, str, str]] = [
    (r"\b(prediction model|prognostic model|risk score|nomogram|machine learning model|"
     r"ai model|algorithm validation|diagnostic model)\b", "probast-ai",
     "prediction-model study — quality and risk of bias"),
    (r"\b(tripod|reporting completeness.*model)\b", "tripod-ai",
     "prediction-model REPORTING completeness"),
    (r"\b(diagnostic (test )?accuracy|sensitivity and specificity|index test|"
     r"reference standard|dta)\b", "quadas2",
     "diagnostic test accuracy study"),
    (r"\b(prognostic factor|prognostic marker|predictor of outcome)\b", "quips",
     "prognostic factor study"),
    (r"\b(umbrella review|overview of reviews|systematic review|meta-analys)\b", "amstar2",
     "systematic review — methodological quality"),
    (r"\b(risk of bias in.*review|robis)\b", "robis",
     "systematic review — risk of bias in the review process"),
    (_NOT_RANDOM + r"\b(randomi[sz]ed|rct|cluster.?randomi[sz]ed|crossover trial)\b",
     "rob2", "randomised trial"),
    (r"\b(non.?randomi[sz]ed|nrsi|non.?rct|quasi.?experimental|quasi.?randomi[sz]ed|"
     r"interrupted time series|before.?after study)\b", "robins-i",
     "non-randomised study of an intervention"),
    (r"\b(exposure|environmental|occupational|nutritional epidemiolog|"
     r"observational study of an exposure)\b", "robins-e",
     "observational study of an exposure"),
    (r"\b(cohort study|case.?control study)\b", "nos",
     "cohort or case-control study (star system)"),
    (r"\b(cross.?sectional|case series|case report|prevalence study|qualitative study)\b",
     "jbi", "JBI checklist family — pick the design-specific list"),
    (r"\b(certainty of evidence|quality of evidence|summary of findings|grade)\b", "grade",
     "certainty of the body of evidence, per outcome"),
]


def route(query: str) -> list[tuple[str, str]]:
    hits = [(tool, why) for pattern, tool, why in ROUTES
            if re.search(pattern, query, re.I)]
    return hits


# --------------------------------------------------------------------------- output


def _applicability_domains(inst: Instrument) -> list[str]:
    """`applicability: domains 1-3` -> ['1', '2', '3']. Anything else -> none."""
    m = re.search(r"domains?\s+(\d+)\s*[-–]\s*(\d+)", inst.meta.get("applicability", ""), re.I)
    if not m:
        return []
    return [str(n) for n in range(int(m.group(1)), int(m.group(2)) + 1)]


def skeleton(inst: Instrument, scope: str) -> str:
    items = inst.scoped(scope)
    answers = " / ".join(inst.answers)
    L = [f"# {inst.name}", ""]
    if inst.meta.get("unit"):
        L += [f"**Assessed per {inst.meta['unit']}** — repeat the whole table for each.", ""]
    L += [f"{len(items)} slots to fill. Answer vocabulary: **{answers}**.",
          f"Domain verdicts: **{' / '.join(inst.verdicts)}**.", ""]
    if inst.shorthand_text():
        L += [f"Shorthands accepted for this instrument only: {inst.shorthand_text()}.", ""]
    rules = inst.answer_rules(scope)
    if rules:
        L += ["Item-specific answers — any other answer is rejected: " + "; ".join(rules) + ".",
              ""]
    if inst.meta.get("skeleton_note"):
        L += [f"Note for this instrument: {inst.meta['skeleton_note']}", ""]
    resolved = inst.resolve_scope(scope)
    if (scope or "all").lower() == "all" and resolved != "all":
        others = [s for s in inst.scope_names if s not in ("all", resolved)]
        L += [f"Scope: `all` means `{resolved}` for this instrument — its variants are "
              f"alternatives, not additions (other: {', '.join(others) or 'none'}).", ""]
    elif scope != "all":
        L += [f"Scope filter: `{scope}`.", ""]

    by_domain: dict[str, list[dict]] = {}
    for it in items:
        by_domain.setdefault(it["domain"], []).append(it)

    applic = _applicability_domains(inst)
    for dom, rows in by_domain.items():
        title = inst.domains.get(dom, dom)
        head = inst.heading(dom, skeleton=True)
        L += [f"## {head} — {title}" if dom else "## Items", "",
              "| # | Signalling question | Answer | Evidence (quote or section) |",
              "|---|---|---|---|"]
        for it in rows:
            L.append(f"| {it['id']} | {it['text'][:76]} |  |  |")
        L += ["", f"**{head} judgement:** {' / '.join(inst.verdicts)} — one-sentence "
                  f"rationale.", ""]
        if dom in applic:
            # One applicability judgement PER DOMAIN. A single line for domains
            # 1-3 together is not what QUADAS-2 or PROBAST ask for.
            L += [f"**{head} applicability:** {' / '.join(inst.verdicts)} — against the "
                  f"stated review question.", ""]
    marker = (f" · numbering: {inst.key} {inst.meta['numbering']}"
              if inst.meta.get("numbering") else "")
    L += [f"**OVERALL:** {' / '.join(inst.verdicts)} — a paragraph of rationale.", "",
          f"<!-- {len(items)} slots{marker}; run --verify, then --rollup, before calling "
          f"this done -->"]
    return "\n".join(L)


# --------------------------------------------------------------------------- reading

ANSWER_COLS = ("answer", "response", "válasz", "valasz")
EVIDENCE_COLS = ("evidence", "bizonyíték", "bizonyitek", "where")
QUESTION_COLS = ("signalling", "question", "q", "sq", "kérdés", "kerdes")

#: Lines the skeleton itself prints. "16 slots to fill. Answer vocabulary: **Yes /
#: Partial yes / No**." starts with AMSTAR 2's last item id and contains an
#: answer — read as prose, a blank skeleton verified 1/16 and rolled up HIGH.
_BOILER = re.compile(
    r"slots to fill|Answer vocabulary|Shorthands accepted|Item-specific answers|"
    r"^\s*Note for this instrument:|"
    r"^\s*Domain verdicts:|judgement:\*\*|applicability:\*\*|^\s*\*\*OVERALL|"
    r"^\s*\*\*Applicability|^\s*Scope( filter)?:|^\s*<!--|^\s*#", re.I)

#: "If Y/PY/NI to 2.1 or 2.2:" — the conditional prefix of a question. Its Y and N
#: are part of the question, not the answer.
_COND_RE = re.compile(
    r"\b(?:if\s+applicable,?\s*(?:and\s+)?)?if\s+(?:(?:Y|PY|N|PN|NI|NA)/)*(?:Y|PY|N|PN|NI|NA)"
    r"\s+to\b[^:?]*[:?]", re.I)
_SEP_RE = re.compile(r"\s[—–]\s|\s-\s|:\s|\s=>?\s|\s->\s")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_sep(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c) \
        and any(cells)


def _clean(cell: str) -> str:
    c = cell.strip().strip("*_`").strip()
    return "" if c in ("—", "–", "-") else c


def _col(header: list[str] | None, names: tuple[str, ...]) -> int | None:
    if not header:
        return None
    for i, h in enumerate(header):
        h = h.strip("*_ ").lower()
        if any(h == n or h.startswith(n + " ") or (len(n) > 2 and h.startswith(n))
               for n in names):
            return i
    return None


def table_rows(text: str) -> list[tuple[list[str], list[str] | None]]:
    """(cells, header) for every body row of every Markdown table in the text.

    The header is the row immediately above a `|---|` separator, lower-cased; it
    lets the answer be read from the ANSWER cell and nowhere else.
    """
    lines = text.splitlines()
    out: list[tuple[list[str], list[str] | None]] = []
    header: list[str] | None = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("|"):
            header = None
            continue
        cells = _cells(s)
        if _is_sep(cells):
            continue
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if nxt.startswith("|") and _is_sep(_cells(nxt)):
            header = [c.lower() for c in cells]
            continue
        out.append((cells, header))
    return out


def _row_id(cells: list[str]) -> str:
    return cells[0].strip("*_` ") if cells else ""


ID_COLS = ("#", "item", "sq", "id", "no", "no.", "tétel", "tetel")
#: "1. Item 7 (excluded studies) — No": a numbered list line about ANOTHER item.
_OTHER_ITEM = re.compile(r"^\s*(?:\*\*|__)?items?\s+([A-Za-z]?\d[\w.]*?)[.,;:)]?(?=\s|$)",
                         re.I)


def _id_col(header: list[str] | None) -> int:
    """The column that holds the item id: the first, unless the header names another.

    A priority table "| Priority | Item | Answer |" keyed by its first cell
    credited priority 1, 2 … to items 1, 2 ….
    """
    names = [h.strip("*_ ").lower() for h in header or []]
    if not names or names[0] in ID_COLS:
        return 0
    return next((i for i, h in enumerate(names) if h in ID_COLS), 0)


def _table_id(cells: list[str], header: list[str] | None, known) -> str:
    """The row's item id: from the header's id column, else (if that is no item) the first cell."""
    i = _id_col(header)
    named = re.sub(r"^item\s+", "", _row_id(cells[i:]), flags=re.I) if i < len(cells) else ""
    return named if i == 0 or named in known else _row_id(cells)


def _first_token(s: str, inst: Instrument) -> str | None:
    for m in inst.token_re.finditer(s):
        tok = m.group(1)
        # A lone letter counts only as written in capitals: "n = 230" is a count.
        if len(tok) == 1 and not tok.isupper():
            continue
        return inst.spell(tok)
    return None


def _answer_in(rest: str, it: dict, inst: Instrument) -> str | None:
    """The answer in the part of a prose line after the item id.

    The item's own question text is cut out first, then any "If Y/PY to 2.1:"
    clause: RoB 2's 2.3, 2.7, 3.2-3.4 and 4.3-4.5 all open with one, and in 1.x
    the first Y or N inside it was read as the answer — a clean prose appraisal
    came back with ten of 22 answers wrong and three domains rated high risk.
    An emphasised answer (**No**) wins; otherwise the text after the last
    separator; otherwise the first answer word left.
    """
    r = rest
    for t in sorted({it["text"], it["text"][:76], it["text"][:60], it["text"][:50]},
                    key=len, reverse=True):
        t = t.strip()
        if len(t) >= 12:
            j = r.lower().find(t.lower())
            if j >= 0:
                r = r[:j] + " " + r[j + len(t):]
                break
    r = _COND_RE.sub(" ", r)
    r = re.sub(r"^\s*\([^)]*\)", " ", r)
    for b in re.findall(r"\*\*(.+?)\*\*|__(.+?)__", r):
        tok = inst.spell(_clean(b[0] or b[1]))
        if tok:
            return tok
    parts = _SEP_RE.split(r)
    if len(parts) > 1:
        tok = _first_token(parts[-1], inst)
        if tok:
            return tok
    return _first_token(r, inst)


def _prose_head(iid: str) -> re.Pattern:
    """An item id at the START of a prose line: `- 2.3 …`, `**16** — …`, `Item 4: …`."""
    return re.compile(
        rf"^\s*(?:[-*+]\s+)?(?:\*\*|__)?(?:(?:item|sq|q)\s*)?{re.escape(iid)}"
        rf"(?:\*\*|__|[.):])*(?=\s|$)", re.I)


def read_record(text: str, inst: Instrument, scope: str
                ) -> tuple[dict[str, str], dict[str, str]]:
    """({item id: answer token}, {item id: unrecognised answer cell}).

    Table rows are parsed as TABLE ROWS, and the answer comes from the Answer
    column named in the table's header. RoB 2's own question texts contain the
    strings "N/PN/NI" and "Y/PY" — a line-wide search finds those before it
    reaches the answer column, so a correctly answered 2.7 read back as "No" and
    the rollup rated three domains high risk on a trial with no problems.

    A table without a header falls back to the first cell that is exactly an
    answer word. Prose lines count only when they START with the item id; a
    number elsewhere in a sentence is not an item.
    """
    items = {it["id"]: it for it in inst.scoped(scope)}
    found: dict[str, str] = {}
    bad: dict[str, str] = {}
    for cells, header in table_rows(text):
        iid = _table_id(cells, header, items)
        if iid not in items or iid in found or iid in bad:
            continue
        ai = _col(header, ANSWER_COLS)
        if ai is not None:
            if ai < len(cells):
                cell = _clean(cells[ai])
                if cell:
                    tok = inst.spell(cell)
                    if tok:
                        found[iid] = tok
                    else:
                        bad[iid] = cell
            continue
        for cell in cells[1:]:
            tok = inst.spell(_clean(cell))
            if tok:
                found[iid] = tok
                break

    prose = [ln for ln in text.splitlines()
             if not ln.lstrip().startswith("|") and not _BOILER.search(ln)]
    for iid, it in items.items():
        if iid in found or iid in bad:
            continue
        head = _prose_head(iid)
        for line in prose:
            m = head.match(line)
            if not m:
                continue
            other = _OTHER_ITEM.match(line[m.end():])
            if other and other.group(1).lower() != iid.lower():
                continue
            tok = _answer_in(line[m.end():], it, inst)
            if tok:
                found[iid] = tok
                break
    return found, bad


def read_answers(path: Path, inst: Instrument, scope: str) -> dict[str, str]:
    """{item id: answer token} — the recognised answers only."""
    return read_record(path.read_text(encoding="utf-8"), inst, scope)[0]


_APPLIC_LINE = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?\s*(?:domain|d)\s*(?P<dom>\d+)\s+applicability\s*"
    r"(?:concerns?)?\s*:?\s*(?:\*\*|__)?\s*:?\s*(?P<rest>.*)$", re.I)


def read_applicability(text: str, inst: Instrument) -> tuple[dict[str, str], dict[str, str]]:
    """({domain: verdict}, {domain: unrecognised value}) for the domains that take one.

    QUADAS-2 rates applicability once per domain 1-3, as a judgement of its own:
    no signalling question feeds it, so nothing can compute it, and in 2.0.0 a
    record with every applicability slot blank verified complete. Read from the
    skeleton's `**Domain N applicability:**` line, or from a summary table with an
    applicability column whose first cell names the domain.
    """
    doms = _applicability_domains(inst)
    got: dict[str, str] = {}
    bad: dict[str, str] = {}
    if not doms:
        return got, bad
    verdicts = {v.lower(): v for v in inst.verdicts}
    template = " / ".join(inst.verdicts).lower()

    def take(dom: str, raw: str) -> None:
        if dom not in doms or dom in got or dom in bad:
            return
        value = _clean(raw)
        if not value or value.lower().startswith(template):
            return
        word = re.split(r"[\s—–,.;:(/]", value, maxsplit=1)[0].strip("*_").lower()
        if word in verdicts:
            got[dom] = verdicts[word]
        else:
            bad[dom] = value[:40]

    for line in text.splitlines():
        m = _APPLIC_LINE.match(line)
        if m:
            take(m.group("dom"), m.group("rest"))
    titles = {inst.domains.get(d, "").lower(): d for d in doms}
    for cells, header in table_rows(text):
        ci = next((i for i, h in enumerate(header or []) if h.strip("*_ ").startswith("applicab")),
                  None)
        if ci is None or ci >= len(cells) or not cells:
            continue
        first = _clean(cells[0]).lower()
        m = re.match(r"^(?:domain\s*|d)?(\d+)\b", first)
        dom = m.group(1) if m else next((d for t, d in titles.items() if t and first.startswith(t)),
                                        None)
        if dom:
            take(dom, cells[ci])
    return got, bad


# --------------------------------------------------------------------------- legacy ids


def _numbering_marker(text: str, inst: Instrument) -> bool:
    return bool(re.search(rf"numbering:\s*{re.escape(inst.key)}\b", text))


def _file_ids(text: str) -> tuple[set[str], set[str]]:
    """(ids of table rows, ids that open a prose line)."""
    table = {_row_id(c) for c, _ in table_rows(text)}
    prose = set()
    for line in text.splitlines():
        if line.lstrip().startswith("|") or _BOILER.search(line):
            continue
        m = re.match(r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?([0-9][0-9A-Za-z.]*?)(?:\*\*|__|[.):])*\s",
                     line)
        if m:
            prose.add(m.group(1))
    return table, prose


def detect_legacy(text: str, inst: Instrument) -> str | None:
    """Why this file looks like it uses the validator 1.x numbering, or None.

    Renumbering is safe only if an old file cannot be scored against the new
    questions by accident. A file written from a 2.0.0 skeleton carries a
    `numbering:` marker; without it, the old numbering is recognised by its ids
    (QUIPS 1.1-6.5), by the old question text in a row whose id now asks
    something else, or — for files written from a 1.x skeleton without question
    text — by rows for the changed ids with none for the ids that only exist now.
    """
    if not inst.meta.get("numbering") or _numbering_marker(text, inst):
        return None
    table_ids, prose_ids = _file_ids(text)
    pat = inst.meta.get("legacy_ids")
    if pat:
        old = sorted(i for i in table_ids if re.match(pat, i))
        # A prose line may open with a number ("2.5 % were lost …"); it takes
        # several old ids at line starts to call a prose file legacy.
        old_prose = sorted(i for i in prose_ids if re.match(pat, i))
        if not old and len(old_prose) >= 3:
            old = old_prose
        if old:
            return (f"its item ids ({', '.join(old[:5])}{', …' if len(old) > 5 else ''}) "
                    f"are the validator 1.x numbering")
    cues = inst.legacy_cues()
    if cues:
        for cells, header in table_rows(text):
            iid = _row_id(cells)
            if iid not in cues:
                continue
            qi = _col(header, QUESTION_COLS)
            q = cells[qi] if qi is not None and qi < len(cells) else " ".join(cells[1:])
            if cues[iid].lower() in q.lower():
                return f"row {iid} asks the 1.x question ('…{cues[iid]}…')"
        for line in text.splitlines():
            for iid, cue in cues.items():
                m = _prose_head(iid).match(line)
                if m and cue.lower() in line[m.end():].lower():
                    return f"line {iid} asks the 1.x question ('…{cue}…')"
    new_only = set(inst.legacy_new_only())
    changed = set(inst.legacy_map())
    if new_only and (table_ids & changed) and not (table_ids & new_only):
        return (f"its table has rows for {', '.join(sorted(table_ids & changed))} but none "
                f"for {', '.join(sorted(new_only))}, which only the current numbering has")
    return None


def _legacy_message(inst: Instrument, reason: str, path: str, scope: str) -> None:
    sc = f" --scope {scope}" if scope and scope != "all" else ""
    print(f"  LEGACY NUMBERING — {path}: {reason}.")
    if inst.meta.get("legacy_note"):
        print(f"  {inst.meta['legacy_note']}.")
    print("  Not scored: an answer recorded under an old id would be read against a "
          "different question.")
    print(f"  Convert it first:  python3 scripts/appraise.py --migrate {path} "
          f"--tool {inst.key}{sc} > migrated.md")


def migrate(path: Path, inst: Instrument, scope: str) -> int:
    """Rewrite a validator 1.x appraisal to the current item numbering.

    Explicit, never silent: the old answers are carried only to the item that
    asks the same question; a merged question that was split is carried only
    when the answer settles both halves (a No to "A or B" is a No to each);
    retired prompts are listed, not dropped quietly; the new questions are left
    blank so --verify names them.
    """
    if not inst.legacy_map():
        print(f"{inst.name}: nothing to migrate — its item ids did not change in 2.0.0.",
              file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    reason = detect_legacy(text, inst)
    if not reason:
        print(f"{path}: refusing to renumber — the file carries the current numbering "
              f"marker or none of the 1.x signs. Renumbering a file twice scrambles it.",
              file=sys.stderr)
        return 1
    rows: dict[str, tuple[str, str]] = {}
    for cells, header in table_rows(text):
        iid = _row_id(cells)
        if not iid or iid in rows:
            continue
        ai, ei = _col(header, ANSWER_COLS), _col(header, EVIDENCE_COLS)
        ans = _clean(cells[ai]) if ai is not None and ai < len(cells) else ""
        if ai is None:
            ans = next((_clean(c) for c in cells[1:] if inst.spell(_clean(c))), "")
        ev = cells[ei].strip() if ei is not None and ei < len(cells) else ""
        rows[iid] = (ans, ev)
    if not rows:
        print(f"{path}: no table rows found. --migrate converts table appraisals; re-enter "
              f"a prose appraisal against a fresh --skeleton.", file=sys.stderr)
        return 1

    lmap = inst.legacy_map()
    retired = set(inst.legacy_retired())
    legacy_pat = inst.meta.get("legacy_ids")
    current = {it["id"] for it in inst.items}
    # The variant being migrated to. ROBINS-I's 1.x 4.3 (the adhering-analysis
    # question, filed under the effect of assignment) becomes 4.6, which only the
    # adhering variant asks: 2.0.0 reported "moved: 4.3→4.6" for --scope
    # assignment and wrote nothing, and counted 4.1-4.2 as carried for --scope
    # adherence although that skeleton has no row for them.
    in_scope = {it["id"] for it in inst.scoped(scope)}
    filled: dict[str, tuple[str, str]] = {}
    moved, split_notes, dropped, outside, kept = [], [], [], [], 0
    for old, (ans, ev) in rows.items():
        if not ans and not ev:
            continue
        if old in lmap:
            targets = lmap[old]
            tag = f"[1.x {old}]"
            ev2 = f"{ev} {tag}".strip()
            here = [t for t in targets if t in in_scope]
            if not here:
                outside.append(f"{old} '{ans}' (now {' + '.join(targets)})")
            elif len(targets) == 1:
                filled[targets[0]] = (ans, ev2)
                if targets[0] != old:
                    moved.append(f"{old}→{targets[0]}")
            elif ans and inst.norm(ans) in NO_ISH:
                for t in here:
                    filled[t] = (ans, ev2)
                split_notes.append(f"{old} '{ans}' → {' and '.join(here)}")
            else:
                split_notes.append(f"{old} '{ans}' not carried: a '{ans or 'blank'}' to the "
                                   f"merged 1.x question does not say which of "
                                   f"{' / '.join(targets)} it is")
        elif old in retired:
            dropped.append(f"{old} '{ans}'")
        elif old in current and not (legacy_pat and re.match(legacy_pat, old)):
            if old not in in_scope:
                outside.append(f"{old} '{ans}'")
                continue
            if old not in filled:
                filled[old] = (ans, ev)
                kept += 1

    out = [f"<!-- migrated from the validator 1.x {inst.key} numbering by appraise.py "
           f"--migrate {path.name}: answers carried to the item that asks the same "
           f"question; blank rows are new or split questions — answer them, then --verify "
           f"-->", ""]
    for line in skeleton(inst, scope).splitlines():
        cells = _cells(line) if line.startswith("| ") else []
        if len(cells) == 4 and cells[0] in filled:
            ans, ev = filled[cells[0]]
            line = f"| {cells[0]} | {cells[1]} | {ans} | {ev} |"
        out.append(line)
    print("\n".join(out))

    blank = [it["id"] for it in inst.scoped(scope) if it["id"] not in filled]
    err = sys.stderr
    print(f"MIGRATION — {inst.name}: 1.x → {inst.meta.get('numbering', 'current')}", file=err)
    if moved:
        print(f"  moved:    {', '.join(moved)}", file=err)
    if kept:
        print(f"  same id:  {kept} answer(s) whose question did not change", file=err)
    for n in split_notes:
        print(f"  split:    {n}", file=err)
    if dropped:
        print(f"  retired (no published counterpart; carry the concern by hand): "
              f"{', '.join(dropped)}", file=err)
    if outside:
        sc = inst.resolve_scope(scope)
        print(f"  not carried — the '{sc}' variant does not ask them (migrate again with the "
              f"--scope of the effect you assess if it is the other one): "
              f"{', '.join(outside)}", file=err)
    if blank:
        print(f"  to answer now (blank): {', '.join(blank)}", file=err)
    return 0


# --------------------------------------------------------------------------- verify


def verify(path: Path, inst: Instrument, scope: str) -> int:
    text = path.read_text(encoding="utf-8")
    legacy = detect_legacy(text, inst)
    if legacy:
        _legacy_message(inst, legacy, str(path), scope)
        return 1
    items = inst.scoped(scope)
    found, bad = read_record(text, inst, scope)
    invalid = {i: t for i, t in found.items() if inst.invalid(i, t, scope)}
    missing = [it["id"] for it in items if it["id"] not in found and it["id"] not in bad]
    print(f"  {len(found) - len(invalid)}/{len(items)} answered  ({inst.name})")
    if invalid:
        print(f"  INVALID ({len(invalid)}): " + "; ".join(
            f"{i} '{t}' — this item offers {inst.allowed_text(i, scope)}"
            for i, t in invalid.items()))
    if bad:
        sh = f"; shorthands {inst.shorthand_text()}" if inst.shorthand_text() else ""
        print(f"  UNRECOGNISED ({len(bad)}): " + "; ".join(f"{i} '{c}'" for i, c in bad.items())
              + f" — {inst.short_name} answers are {' / '.join(inst.answers)}{sh}")
    if missing:
        print(f"  UNANSWERED ({len(missing)}): {', '.join(missing)}")
        unk = inst.meta.get("unknown_answer")
        print("  An appraisal with unanswered slots is not finished. "
              + (f"'{unk}' is an answer; silence is not." if unk else
                 "Every slot needs an answer from its vocabulary; silence is not one."))
    if invalid or bad:
        print("  An answer the instrument does not offer is not an answer.")
    valid = {i: t for i, t in found.items() if i not in invalid}
    asked_na = inst.na_where_asked(items, valid)
    if asked_na:
        print(f"  N/A WHERE ASKED ({len(asked_na)}): " + "; ".join(
            f"{it['id']} — its condition holds ({it['cond']['text']})" for it in asked_na)
            + ". N/A answers a question the routing skipped, not one it reached.")
    applic = _applicability_domains(inst)
    app_missing: list[str] = []
    app_bad: dict[str, str] = {}
    if applic:
        app, app_bad = read_applicability(text, inst)
        app_missing = [d for d in applic if d not in app and d not in app_bad]
        print(f"  applicability: {len(app)}/{len(applic)} domains judged")
        if app_missing:
            print(f"  APPLICABILITY NOT RECORDED: "
                  f"{', '.join(inst.heading(d) for d in app_missing)} — {inst.short_name} judges "
                  f"applicability once per domain {applic[0]}-{applic[-1]} "
                  f"({' / '.join(inst.verdicts)}); no signalling question supplies it.")
        if app_bad:
            print("  APPLICABILITY NOT RECOGNISED: " + "; ".join(
                f"{inst.heading(d)} '{v}'" for d, v in app_bad.items())
                + f" — use {' / '.join(inst.verdicts)}")
    if missing or invalid or bad or asked_na or app_missing or app_bad:
        return 1
    print("  complete")
    return 0


# --------------------------------------------------------------------------- rollups


def _partition(inst: Instrument, answers: dict[str, str], items: list[dict]
               ) -> tuple[dict[str, str], dict[str, str], list[str]]:
    valid, invalid, unanswered = {}, {}, []
    for it in items:
        a = answers.get(it["id"])
        if a is None:
            unanswered.append(it["id"])
        elif inst.invalid_item(it, a):
            invalid[it["id"]] = a
        else:
            valid[it["id"]] = a
    return valid, invalid, unanswered


def _flag_text(normal: list[str], reverse: list[str]) -> str:
    """Which answers raised the domain, in the polarity they were recorded in.

    A reverse-worded item is a problem when answered Yes; saying "'No' or
    'Probably no' at 1.3" about a Yes was the 1.x wording. The reverse clause
    comes first, so a reader keyed on the 1.x prefix never mis-reads it.
    """
    parts = []
    if reverse:
        parts.append(f"'Yes' or 'Probably yes' at {', '.join(reverse)} (reverse-worded)")
    if normal:
        parts.append(f"'No' or 'Probably no' at {', '.join(normal)}")
    return "; ".join(parts)


def rollup_signalling(inst: Instrument, answers: dict[str, str],
                      items: list[dict]) -> Lines:
    """The shared shape of ROBINS-I/-E, QUADAS-2, QUIPS, ROBIS and JBI (RoB 2: rollup_rob2).

    Deliberately conservative and deliberately NOT the official flowchart. The
    published algorithms branch on specific questions in ways that a generic
    engine cannot reproduce without hard-coding each one — and a generic engine
    that *claimed* to reproduce them would give a wrong verdict that looks
    official. So this reports what the answers force, names the questions that
    forced it, and leaves the final call to the assessor.

    Every in-scope question of a domain is looked at, not only the answered
    ones. In 1.x a domain with one answer out of four was LOW — "no signalling
    question flags a problem" — because the three blank ones flagged nothing.
    A blank (or invalid) answer now makes the domain INCOMPLETE, and an
    incomplete domain makes the overall INCOMPLETE.
    """
    # Polarity is per item, not per instrument. RoB 2's 1.3, 4.1 and 4.2 are
    # worded so that YES is the problem. Treating every "No" as bad rated a
    # well-conducted trial as high risk on domain 4 for correctly answering "No,
    # the measurement method was not inappropriate".
    # Routers (gateways): questions whose Yes or No only decides what is asked
    # next. ROBINS-I's 2.1 (selection on characteristics observed after the start
    # of intervention) opens 2.2-2.3; the bias is judged there, and a Yes at 2.1
    # with a No at 2.2 can still be Low. Their answer is listed, not scored — but
    # No information at a gateway leaves the domain unclear.
    # Middle: a problem answer that rules out the low tier but cannot by itself
    # reach the top one — ROBINS-I's 1.1 ("is there potential for confounding?"),
    # which 1.x scored as Serious for every observational study ever run.
    # Joint: problem answers that count only together. ROBINS-I's 6.1 and 6.2 (an
    # outcome open to influence AND assessors who knew) — either alone is Low in
    # the 2016 criteria; 5.4 and 5.5 — either Yes is Low.
    # Routing: a conditional question ("If Y/PY to 2.2 and 2.3, or N/PN to 2.4:")
    # is scored only where its condition holds. An answer at a question the
    # routing skipped is listed and ignored; N/A at one it reached is a blank.
    if inst.key == "rob2":
        # RoB 2 publishes a per-domain algorithm small enough to run exactly;
        # tags cannot express it (3.1 No + 3.2 Yes is Low, not a flag).
        return rollup_rob2(inst, answers, items)
    valid, invalid, _ = _partition(inst, answers, items)
    reach = inst.reached(items, valid)
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it["domain"], []).append(it)
    low_label = dict(_pairs(inst.meta.get("low_label", ""), "="))

    L = Lines()
    tier: dict[str, str] = {}            # domain -> low / some / high (complete domains)
    flagged_high: set[str] = set()       # incomplete domains already at the top tier
    incomplete: list[str] = []
    for dom, rows in groups.items():
        high_n, high_r, mid_n, mid_r, partly, unk, missing, bad, routers = \
            [], [], [], [], [], [], [], [], []
        graded_high, graded_mid, offpath, asked_na = [], [], [], []
        joint: list[tuple[dict, str, str]] = []       # (item, answer, problem/good/unknown)
        for it in rows:
            iid = it["id"]
            if iid in invalid:
                bad.append(iid)
                continue
            a = valid.get(iid)
            if a is None:
                missing.append(iid)
                continue
            n = inst.norm(a)
            if reach.get(iid) is False:
                if n != "n/a":
                    offpath.append(f"{iid} '{a}'")
                continue
            if n == "n/a":
                if it.get("cond") and reach.get(iid) and not it["cond"]["optional"]:
                    asked_na.append(it)
                continue
            tags = inst.tags(it)
            rev = "reverse" in tags
            if "router" in tags:
                (unk if n in UNKNOWN else routers).append(iid)
                continue
            if not rev and n in WEAK_NO | STRONG_NO:
                strong = n in STRONG_NO and "middle" not in tags
                (graded_high if strong else graded_mid).append(f"'{a}' at {iid}")
                continue
            problem = (n in YES_ISH) if rev else (n in NO_ISH)
            if "joint" in tags:
                joint.append((it, a, "unknown" if n in UNKNOWN | PARTLY
                              else "problem" if problem else "good"))
                continue
            if n in UNKNOWN:
                unk.append(iid)
                continue
            if n in PARTLY:
                partly.append(iid)
                continue
            if not problem:
                continue
            if "middle" in tags:
                (mid_r if rev else mid_n).append(iid)
            else:
                (high_r if rev else high_n).append(iid)

        # A joint group flags only when every reached member shows the problem;
        # one good answer clears it, and No information keeps it unclear.
        joint_tier, joint_why = None, ""
        states = [s for _, _, s in joint]
        if joint and "good" not in states:
            prob_n = [it["id"] for it, _, s in joint
                      if s == "problem" and "reverse" not in inst.tags(it)]
            prob_r = [it["id"] for it, _, s in joint
                      if s == "problem" and "reverse" in inst.tags(it)]
            if all(s == "problem" for s in states):
                joint_why = _flag_text(prob_n, prob_r) + (" together" if len(joint) > 1 else "")
                if all("middle" in inst.tags(it) for it, _, _ in joint):
                    joint_tier = "some"
                    joint_why += (" — at least the middle tier; whether it is worse is a "
                                  "judgement the answers do not record")
                else:
                    joint_tier = "high"
            else:
                joint_tier = "some"
                unk.extend(it["id"] for it, _, s in joint if s == "unknown")
                if prob_n or prob_r:
                    others = [it["id"] for it, _, s in joint if s != "problem"]
                    joint_why = (_flag_text(prob_n, prob_r) + " counts only together with "
                                 + ", ".join(others))

        title = inst.domains.get(dom, dom)
        top = [x for x in (_flag_text(high_n, high_r),
                           joint_why if joint_tier == "high" else "",
                           ", ".join(graded_high)) if x]
        if missing or bad or asked_na:
            verdict = "INCOMPLETE"
            why = []
            if missing:
                why.append(f"unanswered: {', '.join(missing)}")
            if bad:
                why.append(f"answer not offered by the item at {', '.join(bad)}")
            for it in asked_na:
                why.append(f"N/A at {it['id']}, but its condition holds ({it['cond']['text']}) "
                           f"— answer it")
            if top:
                why.append("already flagged by " + "; ".join(top))
                flagged_high.add(dom)
            incomplete.append(dom)
        elif top:
            verdict, why = "HIGH / SERIOUS", top
            tier[dom] = "high"
        elif mid_n or mid_r or partly or unk or graded_mid or joint_tier == "some":
            verdict = "SOME CONCERNS / UNCLEAR"
            why = []
            if mid_n or mid_r:
                why.append(_flag_text(mid_n, mid_r) + " — rules out low; on its own goes "
                           "no higher than the middle tier")
            if graded_mid:
                why.append(", ".join(graded_mid) + " — the weak form: the middle tier")
            if joint_why:
                why.append(joint_why)
            if partly:
                why.append(f"'Partly' at {', '.join(partly)}")
            if unk:
                why.append(f"no information at {', '.join(unk)}")
            tier[dom] = "some"
        else:
            verdict, why = "LOW", ["no signalling question flags a problem"]
            if dom in low_label:
                why.append(f"in {inst.short_name}'s terms: {low_label[dom]}")
            tier[dom] = "low"
        L.append(f"  {inst.heading(dom)} ({title[:42]}): {verdict}  — {'; '.join(why)}")
        if routers:
            L.append(f"  {'':<12}routing questions answered, not scored: {', '.join(routers)}")
        if offpath:
            L.append(f"  {'':<12}answered, but the routing does not reach them — not scored: "
                     f"{', '.join(offpath)}")
    L.append("")
    # ROBIS: the overall is the phase-3 judgement, made in the light of domains
    # 1-4 — not the worst of them. A phase-2 concern that the interpretation
    # addressed (3A Yes) can still end Low; 2.0.0 rated it High at exit 0.
    over = inst.meta.get("overall_from")
    basis = [over] if over in groups else list(groups)
    rank = {"low": 0, "some": 1, "high": 2}
    if incomplete:
        heads = ", ".join(inst.heading(d) for d in incomplete)
        msg = (f"  Implied overall: INCOMPLETE — {heads}: unanswered or invalid questions, or "
               f"N/A where the routing asks them; no overall judgement until every slot is "
               f"answered.")
        if any(d in flagged_high or tier.get(d) == "high" for d in basis):
            msg += (" (Already at least HIGH / SERIOUS: "
                    + (f"{inst.heading(over)} is at the top tier.)" if over in groups
                       else "one high-risk domain sets the overall.)"))
        L.append(msg)
        L.final = False
    elif over in groups:
        head = inst.heading(over)
        flagged = [inst.heading(d) for d in groups if d != over and tier[d] != "low"]
        L.append({"low": f"  Implied overall: LOW — {head}, the overall judgement",
                  "some": f"  Implied overall: SOME CONCERNS — {head}, the overall judgement",
                  "high": f"  Implied overall: HIGH / SERIOUS — {head}, the overall judgement"
                  }[tier[over]]
                 + (f"; concerns in {', '.join(flagged)} feed it, they do not set it."
                    if flagged else "."))
        if inst.meta.get("overall_note"):
            L.append(f"  {inst.meta['overall_note']}")
    else:
        worst = max((tier[d] for d in basis), key=rank.get, default="low")
        L.append({"low": "  Implied overall: LOW — but only if every domain is genuinely low.",
                  "some": "  Implied overall: SOME CONCERNS — driven by the unresolved domains above.",
                  "high": "  Implied overall: HIGH / SERIOUS — one domain at high risk sets the overall."
                  }[worst])
        if inst.meta.get("overall_note"):
            L.append(f"  {inst.meta['overall_note']}")
    tiers = [t.strip() for t in inst.meta.get("tiers", "").split("|") if t.strip()]
    if len(tiers) == 3:
        # Lower-case on purpose: the upper-case tier names are what readers of
        # this output search for, and a legend must not match those searches.
        L.append(f"  The three tiers in {inst.short_name}'s own terms: low = {tiers[0]}, "
                 f"middle = {tiers[1]}, high = {tiers[2]}"
                 + (" or worse (that call is yours)." if len(inst.verdicts) > 3 else "."))
    L.append("  This is what the recorded answers force. It is NOT the published "
             "flowchart: conditional questions count only where their routing reaches "
             "them, and a domain is raised only as far as the answers decide it — where "
             "the published criteria turn on a judgement the answers do not record (how "
             "substantial, how strongly related), check the domain against the source "
             "and say so if you override this.")
    return L


# --------------------------------------------------------------------------- RoB 2

_Y = frozenset({"yes", "probably yes"})
_N = frozenset({"no", "probably no"})
_NI = frozenset({"no information"})
_TIER = {"low": "LOW", "some": "SOME CONCERNS / UNCLEAR", "high": "HIGH / SERIOUS"}
_RANK = {"low": 0, "some": 1, "high": 2}


class _Stop(Exception):
    """The algorithm reached a question it cannot use (blank, invalid or N/A)."""

    def __init__(self, iid: str, kind: str):
        super().__init__(iid)
        self.iid, self.kind = iid, kind


def _worse(*tiers: str) -> str:
    return max(tiers, key=_RANK.get)


# One function per domain, each the RoB 2 (22 August 2019) algorithm: the
# criteria tables of the guidance (reproduced e.g. in PMC8191126) and the
# answer groupings of the template's conditional questions ("If Y/PY/NI to
# 2.4"). `ask` returns the canonical answer and records the path; NI is treated
# exactly where the algorithm puts it, which is not always the middle tier.

def _rob2_d1(ask) -> str:
    concealed = ask("1.2")
    if concealed in _N:
        return "high"
    baseline = ask("1.3")
    if concealed in _NI:
        return "high" if baseline in _Y else "some"
    random_ = ask("1.1")                     # NI here is compatible with Low
    return "some" if baseline in _Y or random_ in _N else "low"


def _rob2_d2_assignment(ask) -> str:
    participants, carers = ask("2.1"), ask("2.2")
    if participants in _N and carers in _N:
        part1 = "low"
    else:
        context = ask("2.3")
        if context in _N:
            part1 = "low"
        elif context in _NI:
            part1 = "some"
        elif ask("2.4") in _N:
            part1 = "some"
        else:                                   # 2.4 Y/PY/NI
            part1 = "some" if ask("2.5") in _Y else "high"
    if ask("2.6") in _Y:
        part2 = "low"
    else:                                       # 2.6 N/PN/NI
        part2 = "some" if ask("2.7") in _N else "high"
    return _worse(part1, part2)


def _rob2_d2_adherence(ask) -> str:
    problem = False
    participants, carers = ask("2.1"), ask("2.2")
    if not (participants in _N and carers in _N):
        problem |= ask("2.3", na_ok=True) in (_N | _NI)
    problem |= ask("2.4", na_ok=True) in (_Y | _NI)
    problem |= ask("2.5", na_ok=True) in (_Y | _NI)
    if not problem:
        return "low"
    return "some" if ask("2.6") in _Y else "high"    # 2.6 N/PN/NI -> High


def _rob2_d3(ask) -> str:
    if ask("3.1") in _Y:
        return "low"
    if ask("3.2") in _Y:
        return "low"
    if ask("3.3") in _N:
        return "low"
    return "some" if ask("3.4") in _N else "high"     # 3.4 Y/PY/NI -> High


def _rob2_d4(ask) -> str:
    if ask("4.1") in _Y:                       # NI follows the N/PN branch
        return "high"
    differ = ask("4.2")
    if differ in _Y:
        return "high"
    floor = "some" if differ in _NI else "low"
    if ask("4.3") in _N or ask("4.4") in _N:
        return floor
    return "some" if ask("4.5") in _N else "high"     # 4.5 Y/PY/NI -> High


def _rob2_d5(ask) -> str:
    outcomes, analyses = ask("5.2"), ask("5.3")
    if outcomes in _Y or analyses in _Y:
        return "high"
    if outcomes in _N and analyses in _N:
        return "low" if ask("5.1") in _Y else "some"
    return "some"                               # NI at 5.2 or 5.3, neither Yes


def rollup_rob2(inst: Instrument, answers: dict[str, str], items: list[dict]) -> Lines:
    """RoB 2 domain and overall judgements by the published 2019 algorithm.

    2.0.0 scored RoB 2 with the generic polarity tags, and tags cannot express
    an algorithm in which one answer opens a gate for the next: 3.1 'No' with
    3.2 'Yes' is Low, not a flag, but was rated HIGH at exit 0; 2.3 NI and
    4.4 Yes / 4.5 No are Some concerns but came out LOW; NI at 2.5, 2.7 and 4.5
    is the High branch but came out Some concerns. Each domain is now walked
    question by question, the way the template routes it.

    A blank or invalid answer anywhere in a domain still makes it INCOMPLETE,
    and so does N/A at a question the walk reaches.
    """
    adherence = any("adherence" in inst.tags(it) for it in items)
    algo = {"1": _rob2_d1,
            "2": _rob2_d2_adherence if adherence else _rob2_d2_assignment,
            "3": _rob2_d3, "4": _rob2_d4, "5": _rob2_d5}
    valid, invalid, _ = _partition(inst, answers, items)
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it["domain"], []).append(it)

    L = Lines()
    tier: dict[str, str] = {}
    flagged_high: list[str] = []
    incomplete: list[str] = []
    for dom, rows in groups.items():
        ids = [it["id"] for it in rows]
        missing = [i for i in ids if i not in valid and i not in invalid]
        bad = [i for i in ids if i in invalid]
        path: list[str] = []

        def ask(iid: str, na_ok: bool = False) -> str:
            if iid in invalid:
                raise _Stop(iid, "invalid")
            a = valid.get(iid)
            if a is None:
                raise _Stop(iid, "blank")
            n = inst.norm(a)
            path.append(f"{iid} '{a}'")
            if n == "n/a" and not na_ok:
                raise _Stop(iid, "n/a")
            return n

        result, stop = None, None
        try:
            result = algo[dom](ask) if dom in algo else None
        except _Stop as e:
            stop = e
        title = inst.domains.get(dom, dom)
        why: list[str] = []
        if missing or bad or stop is not None or result is None:
            verdict = "INCOMPLETE"
            if missing:
                why.append(f"unanswered: {', '.join(missing)}")
            if bad:
                why.append(f"answer not offered by the item at {', '.join(bad)}")
            if stop is not None and stop.kind == "n/a":
                prior = " → ".join(path[:-1]) or "the answers above"
                why.append(f"N/A at {stop.iid}, but {prior} leads to it — answer it")
            if result is not None:
                why.append(f"the answered questions already give {_TIER[result]} "
                           f"({' → '.join(path)})")
                if result == "high":
                    flagged_high.append(dom)
            incomplete.append(dom)
        else:
            verdict = _TIER[result]
            tier[dom] = result
            why.append("2019 algorithm: " + " → ".join(path))
        L.append(f"  {inst.heading(dom)} ({title[:42]}): {verdict}  — {'; '.join(why)}")
        walked = {p.split(" ", 1)[0] for p in path}
        off = [f"{i} '{valid[i]}'" for i in ids
               if i in valid and i not in walked and inst.norm(valid[i]) != "n/a"]
        if off and verdict != "INCOMPLETE":
            L.append(f"  {'':<12}answered, but not on the algorithm's path for these "
                     f"answers: {', '.join(off)}")
    L.append("")
    if incomplete:
        heads = ", ".join(inst.heading(d) for d in incomplete)
        msg = (f"  Implied overall: INCOMPLETE — {heads}: unanswered, invalid or N/A where "
               f"the algorithm needs an answer; no overall judgement until they are answered.")
        if flagged_high or "high" in tier.values():
            msg += " (Already at least HIGH / SERIOUS: one high-risk domain sets the overall.)"
        L.append(msg)
        L.final = False
    else:
        worst = max(tier.values(), key=_RANK.get, default="low")
        L.append({
            "low": "  Implied overall: LOW — every domain is at low risk of bias.",
            "some": "  Implied overall: SOME CONCERNS — at least one domain has some concerns "
                    "and none is high. RoB 2 also allows High when several domains with some "
                    "concerns together substantially lower confidence in the result: that is "
                    "a judgement — state it and why if you make it.",
            "high": "  Implied overall: HIGH / SERIOUS — one domain at high risk sets the overall.",
        }[worst])
    L.append(f"  Domain verdicts follow the RoB 2 algorithms of the 22 August 2019 guidance "
             f"({'effect of adhering' if adherence else 'effect of assignment'} variant of "
             f"domain 2). For a published assessment, cross-check with the official Excel "
             f"tool; an override is legitimate when it is stated with its reason.")
    return L


def rollup_amstar2(inst: Instrument, answers: dict[str, str],
                   items: list[dict]) -> Lines:
    """AMSTAR 2's rating IS an algorithm, and this one is reproduced exactly.

    Critical items: 2, 4, 7, 9, 11, 13, 15. One critical flaw -> Low. More than
    one -> Critically low. No critical flaw, up to one non-critical weakness ->
    High. No critical flaw, more than one non-critical weakness -> Moderate.
    "No meta-analysis conducted" (N/A) on 11, 12 and 15 is neither — in 1.x it
    was counted as a flaw and a narrative review came out Critically low.

    "Partial yes" is counted as a non-critical weakness on every item that offers
    it (2, 4, 7, 8, 9). That is this tool's convention, not a rule of the paper,
    which says only that it marks partial adherence; 2.0.0 applied it to the
    critical items and silently treated a Partial yes on item 8 as met.
    """
    critical = {c.strip() for c in inst.meta.get("critical", "").split(",") if c.strip()}
    valid, invalid, unanswered = _partition(inst, answers, items)
    crit_flaws, noncrit_flaws, na = [], [], []
    for it in items:
        a = valid.get(it["id"])
        if a is None:
            continue
        n = inst.norm(a)
        if n == "n/a":
            na.append(it["id"])
            continue
        if n in YES_ISH:
            if n == "partial yes":
                # Partial adherence: a weakness, never a critical flaw, and the
                # same on item 8 as on the critical items 2, 4, 7 and 9.
                noncrit_flaws.append(it["id"])
            continue
        (crit_flaws if it["id"] in critical else noncrit_flaws).append(it["id"])

    if len(crit_flaws) > 1:
        rating = "CRITICALLY LOW"
    elif len(crit_flaws) == 1:
        rating = "LOW"
    elif len(noncrit_flaws) > 1:
        rating = "MODERATE"
    else:
        rating = "HIGH"

    L = Lines([f"  Critical flaws ({len(crit_flaws)}): {', '.join(crit_flaws) or 'none'}",
               f"  Non-critical weaknesses ({len(noncrit_flaws)}): "
               f"{', '.join(noncrit_flaws) or 'none'}"])
    if na:
        L.append(f"  No meta-analysis conducted (N/A — neither flaw nor weakness): "
                 f"{', '.join(na)}")
    L += ["", f"  OVERALL CONFIDENCE IN THE RESULTS: {rating}"]
    if unanswered:
        L += ["", f"  {len(unanswered)} item(s) unanswered ({', '.join(unanswered)}) — "
                  "the rating above is provisional until they are filled."]
    if invalid:
        L += ["", "  Not scored — an answer the item does not offer: " + "; ".join(
            f"{i} '{a}' (offers {inst.allowed_text(i)})" for i, a in invalid.items())
            + ". The rating above is provisional until they are corrected."]
    L.final = not unanswered and not invalid
    partial = [it["id"] for it in items
               if valid.get(it["id"]) and inst.norm(valid[it["id"]]) == "partial yes"]
    L += ["", "  Convention used here: 'Partial yes' counts as a non-critical weakness on "
              "every item that offers it (2, 4, 7, 8, 9)"
              + (f" — here {', '.join(partial)}" if partial else "")
              + ". The AMSTAR 2 paper says only that it marks partial adherence; some "
              "appraisals count it as met. State the convention you used.",
          "  The rating scheme is advisory: Box 2's footnote allows several non-critical "
          "weaknesses to move Moderate down to Low, and the critical domains of Box 1 are "
          "a suggestion appraisers may add to or substitute. Any such change is a "
          "judgement — state it and why.",
          "  Items 9 and 11 hold the worse of the RCT and NRSI judgements when the review "
          "includes both designs."]
    L += ["", "  AMSTAR 2 rates CONFIDENCE IN THE RESULTS of the review, not the quality "
              "of the included studies and not the certainty of the evidence. Say that "
              "explicitly; readers conflate it with GRADE constantly."]
    return L


def rollup_nos(inst: Instrument, answers: dict[str, str],
               items: list[dict]) -> Lines:
    """Newcastle-Ottawa: count the stars, and refuse to pretend the thresholds are official.

    One star per item, two for comparability. A partial star exists only on the
    two-star comparability items; 1.x gave one for "Partial yes" anywhere.

    One form per study: the cohort and the case-control scales are 8 items and
    9 stars each, and a count across both ("9/18 stars") is refused.
    """
    forms = {s for s in inst.scope_names if s != "all"}
    used = {t for it in items for t in inst.tags(it)} & forms
    if len(used) > 1:
        L = Lines([f"  Not counted: these items mix the {' and '.join(sorted(used))} forms. "
                   f"The Newcastle-Ottawa scale is one 8-item, 9-star form per study design; "
                   f"rerun with --scope {' or --scope '.join(sorted(used))}."])
        L.final = False
        return L
    valid, invalid, unanswered = _partition(inst, answers, items)
    stars = 0
    total_possible = 0
    per_domain: dict[str, int] = {}
    partial_one_star: list[str] = []
    for it in items:
        m = re.search(r"(\d+)\s*star", it["scope"], re.I)
        max_stars = int(m.group(1)) if m else 1
        total_possible += max_stars
        per_domain.setdefault(it["domain"], 0)
        a = valid.get(it["id"])
        if a is None:
            continue
        n = inst.norm(a)
        got = 0
        if n == "yes":
            got = max_stars
        elif n == "partial yes":
            if max_stars > 1:
                got = 1
            else:
                partial_one_star.append(it["id"])
        stars += got
        per_domain[it["domain"]] += got
    L = Lines(["  Stars by domain: " + ", ".join(f"{k}={v}" for k, v in per_domain.items()),
               f"  TOTAL: {stars}/{total_possible} stars"])
    if unanswered:
        L += ["", f"  {len(unanswered)} item(s) unanswered ({', '.join(unanswered)}) — "
                  "the star count above is provisional until they are filled."]
    bad = [f"{i} '{a}' (offers {inst.allowed_text(i)})" for i, a in invalid.items()] \
        + [f"{i} 'Partial yes'" for i in partial_one_star]
    if bad:
        partial = partial_one_star or any(inst.norm(a) == "partial yes"
                                          for a in invalid.values())
        L += ["", f"  Not scored: {'; '.join(bad)} — the star count above is provisional "
                  "until they are answered."
                  + (" Only the two-star comparability items can earn a partial (one of two) "
                     "star; every other item is Yes or no star." if partial else "")
                  + (" The scale has no not-applicable answer: an item either earns its "
                     "star or it does not." if any(inst.norm(a) == "n/a"
                                                     for a in invalid.values()) else "")]
    L.final = not unanswered and not bad
    L += ["", "  There is NO official threshold. The 7-9 = good / 4-6 = fair / 0-3 = poor "
              "cut-offs come from an AHRQ conversion that the scale's authors never "
              "published, and summing ordinal stars across incomparable domains is the "
              "documented weakness of this instrument. Report the per-domain stars, state "
              "whichever threshold you use and where it came from, and prefer ROBINS-I or "
              "ROBINS-E when the review will be scrutinised."]
    return L


def rollup_grade(inst: Instrument, answers: dict[str, str],
                 items: list[dict]) -> Lines:
    """Start high or low by design, subtract for the five, add for the three.

    Nothing is assumed. 1.x started from High when 0.1 was blank and printed a
    certainty for a table with one answer in it; publication bias "Suspected"
    and "Strongly suspected" both silently counted as no downgrade.
    """
    valid, invalid, unanswered = _partition(inst, answers, items)
    start: str | None = None
    downs = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    ups = 0
    detail = []
    unresolved: list[tuple[str, str]] = []
    strongly = False
    for it in items:
        a = valid.get(it["id"])
        if a is None:
            continue
        n = inst.norm(a)
        dom = it["domain"]
        name = inst.domains.get(dom, dom)[:34]
        if dom == "0":
            if n.startswith("low") or "observational" in n or "nrsi" in n:
                start = "low"
            elif n.startswith("high"):
                start = "high"
            continue
        if dom == "5":
            if n == "strongly suspected":
                downs["5"] = 1
                strongly = True
                detail.append(f"-1 {name} (strongly suspected)")
            elif n in ("suspected", "could not be assessed"):
                unresolved.append((it["id"], a))
            continue
        if dom in downs:
            # "not serious" CONTAINS "serious". A substring test downgraded every
            # domain the assessor had explicitly cleared, and turned a High body
            # of evidence into Very low without a single serious concern in it.
            if n.startswith("very serious"):
                step = 2
            elif n.startswith("serious"):
                step = 1
            else:
                step = 0
            downs[dom] = step
            if step:
                detail.append(f"-{step} {name}")
        elif dom in ("6", "7", "8"):
            if n == "very large" and dom == "6":
                ups += 2
                detail.append(f"+2 {name} (very large)")
            elif n == "yes":
                ups += 1
                detail.append(f"+1 {name}")

    levels = ["very low", "low", "moderate", "high"]
    down = sum(downs.values())

    def level(extra_down: int = 0) -> str:
        idx = levels.index(start or "high") - down - extra_down
        if down + extra_down == 0:
            idx += ups
        return levels[max(0, min(3, idx))]

    L = Lines()
    if start is None:
        L.append("  Start: NOT RECORDED — 0.1 must say High (randomised trials) or Low "
                 "(observational studies); nothing is assumed.")
    else:
        L.append(f"  Start: {start.upper()} ({'RCT' if start == 'high' else 'observational'})")
    L += [f"  Adjustments: {', '.join(detail) or 'none'}", ""]
    if start is None or unanswered or invalid:
        what = []
        if unanswered:
            what.append(f"unanswered: {', '.join(unanswered)}")
        if invalid:
            what.append("not offered by the item: " + "; ".join(
                f"{i} '{a}' (offers {inst.allowed_text(i)})" for i, a in invalid.items()))
        L.append(f"  CERTAINTY: INCOMPLETE — {'; '.join(what) or 'no starting level'}. "
                 "No certainty is computed from a partial table.")
        L.final = False
    elif unresolved:
        for iid, a in unresolved:
            L.append(f"  UNRESOLVED: publication bias recorded as '{a}' at {iid} — a decision is "
                     "still owed. Re-answer it 'Undetected' (no downgrade) or 'Strongly "
                     "suspected' (−1), with the reason in the evidence column.")
        L.append(f"  CERTAINTY: UNRESOLVED — {level(0).upper()} without a publication-bias "
                 f"downgrade, {level(1).upper()} with one.")
        L.final = False
    else:
        L.append(f"  CERTAINTY: {level().upper()}")
    if strongly:
        L += ["", "  Publication bias 'Strongly suspected' is −1 here. GRADE also allows −2 for "
                  "a very strong suspicion; that is a manual call — state it and the reason "
                  "if you take it."]
    if ups and down:
        L += ["", "  Upgrade factors were recorded alongside downgrades and were NOT "
                  "applied: GRADE only upgrades a body of evidence that has not been "
                  "downgraded. Resolve the downgrades first."]
    L += ["", "  Certainty is rated PER OUTCOME, never per study and never per review. "
              "If more than one outcome matters, this table has to be repeated for each, "
              "and the Summary of Findings reports them separately."]
    return L


ROLLUPS = {
    "rob2": rollup_rob2,
    "amstar2": rollup_amstar2,
    "nos": rollup_nos,
    "grade": rollup_grade,
}


def rollup(path: Path, inst: Instrument, scope: str) -> int:
    text = path.read_text(encoding="utf-8")
    legacy = detect_legacy(text, inst)
    if legacy:
        _legacy_message(inst, legacy, str(path), scope)
        return 1
    answers, bad = read_record(text, inst, scope)
    if not answers:
        print("  Egyetlen kitöltött tétel sincs a fájlban. A --rollup a rögzített "
              "válaszokból számol; előbb töltsd ki a --skeleton táblát.")
        return 1
    items = inst.scoped(scope)
    n_valid = sum(1 for i, a in answers.items() if not inst.invalid(i, a, scope))
    print(f"ROLLUP — {inst.name}   ({n_valid}/{len(items)} answered)")
    print("-" * 70)
    if bad:
        print("  Not read — not an answer in this instrument's vocabulary: "
              + "; ".join(f"{i} '{c}'" for i, c in bad.items()))
        print()
    fn = ROLLUPS.get(inst.key, rollup_signalling)
    lines = fn(inst, answers, items)
    print("\n".join(lines))
    final = getattr(lines, "final", True) and not bad
    applic = _applicability_domains(inst)
    if applic:
        app, app_bad = read_applicability(text, inst)
        print("")
        print(f"  Applicability concerns (domains {applic[0]}-{applic[-1]}, judged against the "
              f"review question; no signalling question feeds them):")
        for d in applic:
            shown = app.get(d) or (f"not recognised ('{app_bad[d]}')" if d in app_bad
                                   else "NOT RECORDED")
            print(f"    domain {d} — {inst.domains.get(d, d)}: {shown}")
        if len(app) == len(applic):
            vals = {v.lower() for v in app.values()}
            word = "high" if "high" in vals else "unclear" if "unclear" in vals else "low"
            print(f"    overall applicability: {word} concern"
                  + (" — every domain is of low concern." if word == "low" else
                     " — at least one domain is not of low concern."))
        else:
            print("    no applicability conclusion until each of these domains is judged.")
            final = False
    if not final:
        print("\n  (exit 1: this verdict is not final — see above.)")
    return 0 if final else 1


# --------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--route", metavar="DESIGN")
    ap.add_argument("--skeleton", metavar="TOOL")
    ap.add_argument("--verify", type=Path)
    ap.add_argument("--rollup", type=Path)
    ap.add_argument("--migrate", type=Path, metavar="OLD_FILE",
                    help="rewrite a validator 1.x appraisal to the current item numbering")
    ap.add_argument("--tool")
    ap.add_argument("--scope", default="all")
    ap.add_argument("--counts", action="store_true")
    args = ap.parse_args(argv)

    tools = load_all()
    if not tools:
        sys.exit(f"nincs egyetlen műszer sem itt: {REF}")

    def _get(name: str) -> Instrument:
        inst = tools.get(name)
        if not inst:
            sys.exit(f"ismeretlen műszer: {name}\n  van: {', '.join(sorted(tools))}")
        # An unknown scope used to filter down to nothing: '--scope cohorts'
        # printed a 0-slot skeleton and an empty file verified "0/0 complete".
        if not inst.valid_scope(args.scope):
            valid = [s for s in inst.scope_names if s != "all"] + ["all"]
            ap.error(f"{inst.key}: unknown --scope '{args.scope}'. Valid: {', '.join(valid)}")
        # Newcastle-Ottawa is two separate forms, cohort and case-control, of 8
        # items and 9 stars each. Without a scope the engine merged them into a
        # 16-slot form and reported "9/18 stars" — a denominator the scale never has.
        if inst.meta.get("scope_required") and inst.resolve_scope(args.scope) == "all":
            forms = " or ".join(f"--scope {s}" for s in inst.scope_names if s != "all")
            ap.error(f"{inst.key}: choose {forms}. {inst.meta['scope_required']}")
        return inst

    if args.list:
        print("Elérhető műszerek:\n")
        for key, inst in sorted(tools.items()):
            scopes = inst.meta.get("scopes", "")
            print(f"  {key:<12} {inst.name}")
            if inst.meta.get("engine"):
                print(f"  {'':<12} saját motor: scripts/{inst.meta['engine']}")
                n = len(inst.items)
            else:
                n = len(inst.scoped("all"))
            per = ", ".join(f"{s} {len(inst.scoped(s))}" for s in inst.scope_names
                            if s != "all" and not inst.meta.get("engine"))
            count = (f"egy űrlap vizsgálatonként, --scope kötelező ({per})"
                     if inst.meta.get("scope_required")
                     else f"{n} tétel" + (f" ({per})" if per else ""))
            print(f"  {'':<12} {count}"
                  + f" · válaszok: {' / '.join(inst.answers)}"
                  + (f" · scope: {scopes}" if scopes else ""))
            if inst.shorthand_text():
                print(f"  {'':<12} rövidítések: {inst.shorthand_text()}")
            if inst.meta.get("use_for"):
                print(f"  {'':<12} → {inst.meta['use_for']}")
            print()
        print("Melyiket? →  appraise.py --route \"<vizsgálati elrendezés>\"")
        return 0

    if args.route:
        hits = route(args.route)
        if not hits:
            print(f"Nem ismertem fel elrendezést ebben: \"{args.route}\"")
            print("A felismert kulcsszavakat lásd: --list, és a SKILL.md "
                  "\"Choosing the instrument\" táblája.")
            return 1
        print(f"\"{args.route}\" →")
        for tool, why in hits:
            inst = tools.get(tool)
            print(f"  {tool:<12} {inst.name if inst else '(hiányzó referencia)'}")
            print(f"  {'':<12} {why}")
        if len(hits) > 1:
            print("\nTöbb műszer illik rá. Ez normális: egy szisztematikus review-t "
                  "AMSTAR 2-vel ÉS ROBIS-szal is lehet nézni, és egy prediktív modell "
                  "vizsgálatához PROBAST (minőség) és TRIPOD (jelentés) is tartozik. "
                  "Mondd meg, melyik kérdésre válaszolsz, és futtasd azt.")
        return 0

    def _redirect(inst: Instrument, action: str, scope: str) -> int:
        """Some instruments cannot be expressed by the generic model. Say so.

        PROBAST+AI answers domains 1-3 TWICE — once judging development quality,
        once judging evaluation risk of bias — and the generic parser has one
        slot per item id. Letting it print a 27-slot skeleton for a 34-slot
        instrument would be exactly the silent under-count this whole script
        exists to prevent, so it refuses and points at the engine that handles it.
        """
        tool = {"probast-ai": "probast", "tripod-ai": "tripod"}.get(inst.key, inst.key)
        target = (f"--skeleton {tool}" if action == "skeleton"
                  else f"--verify <file> --tool {tool}")
        print(f"{inst.name} saját motorral fut ({inst.meta['engine']}).")
        print(f"  python3 scripts/{inst.meta['engine']} {target}"
              f" --scope {scope if scope != 'all' else 'both'}")
        if inst.meta.get("note"):
            print(f"  Miért: {inst.meta['note']}")
        return 2

    if args.skeleton:
        inst = _get(args.skeleton)
        if inst.meta.get("engine"):
            return _redirect(inst, "skeleton", args.scope)
        print(skeleton(inst, args.scope))
        return 0

    if args.verify or args.rollup or args.migrate:
        if not args.tool:
            sys.exit("--verify / --rollup / --migrate mellé --tool kell")
        inst = _get(args.tool)
        if inst.meta.get("engine"):
            return _redirect(inst, "verify", args.scope)
        path = args.verify or args.rollup or args.migrate
        if not path.exists():
            sys.exit(f"nincs ilyen fájl: {path}")
        if args.migrate:
            return migrate(path, inst, args.scope)
        return verify(path, inst, args.scope) if args.verify else rollup(path, inst, args.scope)

    if args.counts:
        bad = 0
        for key, inst in sorted(tools.items()):
            if inst.meta.get("engine"):
                print(f"  {key:<12} {'—':>3}        saját motor: "
                      f"{inst.meta['engine']} --counts")
                continue
            expected = inst.meta.get("published_items", "")
            n = len(inst.scoped("all"))
            if inst.meta.get("scope_required"):
                # One form per study: there is no instrument-wide total to check.
                per = []
                for sc, exp_s in _pairs(inst.meta.get("published_by_scope", ""), "="):
                    got = len(inst.scoped(sc))
                    ok = exp_s.isdigit() and int(exp_s) == got
                    per.append(f"{sc} {got}{' ok' if ok else f' ≠ {exp_s} MISMATCH'}")
                    bad += 0 if ok else 1
                print(f"  {key:<12} {'—':>3}        formánként: {' · '.join(per)}")
                continue
            note = ""
            if expected:
                try:
                    exp = int(expected)
                    if exp != n:
                        note = f"  MISMATCH — a publikált eszköz {exp} tétel"
                        bad += 1
                    else:
                        note = "  ok"
                except ValueError:
                    note = f"  (várt: {expected})"
            per = []
            for sc, exp_s in _pairs(inst.meta.get("published_by_scope", ""), "="):
                got = len(inst.scoped(sc))
                ok = exp_s.isdigit() and int(exp_s) == got
                per.append(f"{sc} {got}{'' if ok else f' ≠ {exp_s} MISMATCH'}")
                bad += 0 if ok else 1
            print(f"  {key:<12} {n:>3} tétel{note}" + (f"  ({' · '.join(per)})" if per else ""))
        if bad:
            print("\n  A referenciafájl és a publikált műszer nem egyezik. Egy hiányzó "
                  "tétel némán csökkenti az értékelést; javítsd, mielőtt használod.")
        return 1 if bad else 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
