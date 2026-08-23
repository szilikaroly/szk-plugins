#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self test for the 5D gate and the PROSPERO rules. Offline. Exit 0 = pass.

No network: the three authorities are stubbed with the exact records that
produced each of the real false positives and false negatives found while
building this. If one of these regresses, the gate starts admitting references
it cannot vouch for, or rejecting real papers — and both failures look like
success in the summary line.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate5d as V      # noqa: E402
import prospero as P        # noqa: E402


def _ok(label: str, cond: bool) -> bool:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    return bool(cond)


class Stub(V.Fetcher):
    """A Fetcher that never touches the network."""

    def __init__(self):
        super().__init__(None, "selftest@example.org", offline=True)


def run() -> bool:
    ok = True

    print("\n[name normalisation]")
    ok &= _ok("Thøgersen folds to ASCII", V.surname_key("Thøgersen") == "thogersen")
    ok &= _ok("Núñez-Cortés folds and joins",
              V.surname_key("Núñez-Cortés") == "nunezcortes")
    ok &= _ok("leading particles stripped: 'van der Meer' -> 'meer'",
              V.surname_key("van der Meer") == "meer")
    ok &= _ok("particle kept by one authority still matches",
              V.surnames_match("van der Meer", "Meer"))
    ok &= _ok("accents do not create a mismatch",
              V.surnames_match("Núñez-Cortés", "Nunez-Cortes"))
    ok &= _ok("different surnames still differ",
              not V.surnames_match("Smith", "Jones"))
    ok &= _ok("empty name never matches", not V.surnames_match("", "Smith"))

    print("\n[journal titles]")
    ok &= _ok("ISO abbreviation matches the full title",
              V.journals_match(["Br J Nutr"], ["British Journal of Nutrition"]))
    ok &= _ok("identical titles match",
              V.journals_match(["Nutrients"], ["Nutrients"]))
    # This one legitimately does NOT match by title — it is why a third
    # authority exists. Europe PMC carries both forms and settles it.
    ok &= _ok("a translated title does not silently match "
              "(Bratislavske lekarske listy / Bratislava Medical Journal)",
              not V.journals_match(["Bratislavske lekarske listy"],
                                   ["Bratislava Medical Journal"]))
    ok &= _ok("unrelated journals do not match",
              not V.journals_match(["Nutrients"], ["The Lancet"]))

    print("\n[dimension comparison]")
    local = {"doi": "10.1000/x", "elso_szerzo": "Kiss",
             "szerzok": ["Kiss", "Nagy", "Tóth"],
             "folyoirat": ["Nutrients"], "kotet": "16", "elocator": "2885",
             "issn": ["2072-6643"]}
    canon = dict(local, szerzok=["Kiss", "Nagy", "Tóth", "Szabó", "Fekete"])
    dims = V.compare(local, canon)
    ok &= _ok("'et al.' truncation is not a mismatch",
              dims["szerzok"][0] == "ok" and "csonkolt" in dims["szerzok"][1])

    bad_author = V.compare(local, dict(canon, elso_szerzo="Horvath"))
    ok &= _ok("a different first author IS a mismatch",
              bad_author["elso_szerzo"][0] == "mismatch")

    # MDPI/BMC/Frontiers: PubMed esummary leaves `pages` empty and often has no
    # volume; Crossref carries the e-locator in `article-number`. Comparing
    # `volume` blindly flags every article-number journal in a modern corpus.
    art = V.compare(dict(local, kotet=""), dict(canon, kotet=""))
    ok &= _ok("article-number journal falls back to the e-locator, and says so",
              art["kotet"][0] == "ok" and "cikkszám" in art["kotet"][1])
    art_bad = V.compare(dict(local, kotet="", elocator="2885"),
                        dict(canon, kotet="", elocator="9999"))
    ok &= _ok("a differing e-locator is still a mismatch",
              art_bad["kotet"][0] == "mismatch")

    no_doi = V.compare(dict(local, doi=""), canon)
    ok &= _ok("a missing DOI is 'missing', not 'ok'", no_doi["doi"][0] == "missing")
    junk = V.compare(dict(local, doi="not-a-doi"), canon)
    ok &= _ok("a malformed DOI is a mismatch", junk["doi"][0] == "mismatch")

    print("\n[the gate]")
    allok = {d: ("ok", "") for d in V.DIMENSIONS}
    ok &= _ok("5/5 + full text -> admitted",
              V.verdict_of(allok, True)[0] == "befogadva")
    ok &= _ok("5/5 but no full text -> held, not admitted",
              V.verdict_of(allok, False)[0] == "fuggoben")
    ok &= _ok("a gap -> held",
              V.verdict_of(dict(allok, kotet=("missing", "")), True)[0] == "fuggoben")

    ident = dict(allok, elso_szerzo=("mismatch", "x"))
    ok &= _ok("an IDENTITY mismatch rejects",
              V.verdict_of(ident, True)[0] == "elutasitva")

    # Biopolymers -> Peptide Science (renamed, new ISSN) and the Slovak/English
    # title pair both arrived as journal mismatches on correct references.
    label = dict(allok, folyoirat=("mismatch", "Biopolymers vs Peptide Science"))
    state, why, adjusted = V.verdict_of(label, True)
    ok &= _ok("a LABEL mismatch with identity intact is held as a variant, "
              "not rejected", state == "fuggoben")
    ok &= _ok("and the dimension is relabelled 'variant'",
              adjusted["folyoirat"][0] == "variant")
    label_no_id = dict(label, doi=("missing", ""))
    ok &= _ok("but a label mismatch WITHOUT identity rejects",
              V.verdict_of(label_no_id, True)[0] == "elutasitva")

    print("\n[three authorities, majority rule]")
    # The real case: Crossref's deposit for 10.1186/s12916-024-03503-y lists 18
    # authors because four consortium members' GIVEN names were deposited as
    # family names. PubMed and Europe PMC both have the correct 14.
    good = ["Pérez-Prieto", "Vargas", "Salas-Espejo", "Lüll", "Canha-Gouveia",
            "Pérez", "Fontes", "Salumets", "Andreson", "Aasmets",
            "Estonian Biobank research team", "Whiteson", "Org", "Altmäe"]
    broken = good[:11] + ["Mait", "Andres", "Lili", "Tõnu"] + good[11:]

    row = {"pmid": "39020289", "doi": "10.1186/s12916-024-03503-y",
           "cim": "Gut microbiome in endometriosis",
           "folyoirat": "BMC medicine", "kotet": "22",
           "szerzok": "; ".join(good), "elso_szerzo": good[0],
           "oldalak": "294", "issn": "1741-7015", "fajl": ""}

    base = {"doi": "10.1186/s12916-024-03503-y", "elso_szerzo": good[0],
            "folyoirat": ["BMC Medicine"], "kotet": "22", "elocator": "294",
            "issn": ["1741-7015"], "ev": "2024", "cim": "x"}

    V_crossref = dict(base, szerzok=broken)
    V_epmc = dict(base, szerzok=good)

    saved = (V.crossref_record, V.pubmed_summary, V.europepmc_record,
             V.from_crossref, V.from_europepmc)
    V.crossref_record = lambda doi, f: {"_": "stub"}
    V.pubmed_summary = lambda pmid, f: None
    V.europepmc_record = lambda doi, pmid, f: {"_": "stub"}
    V.from_crossref = lambda msg: dict(V_crossref)
    V.from_europepmc = lambda rec: dict(V_epmc)
    try:
        with redirect_stdout(io.StringIO()):
            res = V.validate_row(row, Stub(), require_fulltext=False)
        ok &= _ok(f"a malformed Crossref author list does not reject a real paper "
                  f"(got {res['allapot']})", res["allapot"] == "befogadva")
        ok &= _ok("and the Crossref data defect is reported, not hidden",
                  "Crossref-adathiba" in res["megjegyzes"])

        # If BOTH counter-authorities disagree, it must still reject.
        V.from_europepmc = lambda rec: dict(base, szerzok=broken)
        with redirect_stdout(io.StringIO()):
            res2 = V.validate_row(row, Stub(), require_fulltext=False)
        ok &= _ok(f"two authorities disagreeing with the record still rejects "
                  f"(got {res2['allapot']})", res2["allapot"] == "elutasitva")
    finally:
        (V.crossref_record, V.pubmed_summary, V.europepmc_record,
         V.from_crossref, V.from_europepmc) = saved

    print("\n[PROSPERO rules]")
    def check(rec) -> int:
        with redirect_stdout(io.StringIO()):
            return P.check(rec)

    full = P.scaffold("A systematic review of X", "x")
    for key, _, required in P.FIELDS:
        if required and key not in ("stage",) and not full.get(key):
            full[key] = "filled"
    full["prospero_id"] = "CRD42026000001"
    ok &= _ok("a complete systematic-review record passes", check(full) == 0)

    narrative = dict(full, review_type="Narrative review")
    ok &= _ok("a narrative review is refused (PROSPERO does not register it)",
              check(narrative) == 1)
    scoping = dict(full, review_type="Scoping review")
    ok &= _ok("a scoping review is refused", check(scoping) == 1)

    late = dict(full, stage=dict(full["stage"], data_extraction="completed"))
    ok &= _ok("registration after data extraction is refused", check(late) == 1)

    incomplete = dict(full, review_question="")
    ok &= _ok("an empty mandatory field is refused", check(incomplete) == 1)

    bad_stage = dict(full, stage=dict(full["stage"], formal_screening="maybe"))
    ok &= _ok("an invalid stage value is refused", check(bad_stage) == 1)

    md = P.export_md(full)
    ok &= _ok("export names the registration", "CRD42026000001" in md)
    ok &= _ok("export renders the stage table", "| Stage | Status |" in md)

    print("\n[collect: bibliographic extraction]")
    try:
        # `collect` has no .py extension, so spec_from_file_location cannot
        # infer a loader — it has to be handed one explicitly.
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("collect_mod",
                                                      str(HERE / "collect"))
        spec = importlib.util.spec_from_file_location("collect_mod",
                                                      str(HERE / "collect"),
                                                      loader=loader)
        collect = importlib.util.module_from_spec(spec)
        # @dataclass resolves its annotations through sys.modules[__module__],
        # so the module has to be registered BEFORE it is executed.
        sys.modules[spec.name] = collect
        spec.loader.exec_module(collect)
    except SystemExit:
        print("  SKIP  collect not importable here (biopython/requests missing "
              "on this interpreter) — run with the Anaconda python3 its shebang names")
        collect = None
    except Exception as exc:                                   # pragma: no cover
        print(f"  SKIP  collect not importable: {exc}")
        collect = None

    if collect is not None:
        art = {
            "AuthorList": [{"LastName": "Kiss", "ForeName": "A"},
                           {"LastName": "Nagy", "ForeName": "B"},
                           {"CollectiveName": "Study Group"}],
            "Journal": {"Title": "Nutrients", "ISOAbbreviation": "Nutrients",
                        "ISSN": "2072-6643",
                        "JournalIssue": {"Volume": "16", "Issue": "17",
                                         "PubDate": {"Year": "2024"}}},
            "Pagination": {"MedlinePgn": "2885"},
        }
        authors = collect.get_authors(art)
        ok &= _ok("authors extracted in order, collective names kept",
                  authors == ["Kiss", "Nagy", "Study Group"])
        bits = collect.get_journal_bits(art)
        ok &= _ok("volume, issue, pages, ISSN and ISO abbreviation extracted",
                  bits["kotet"] == "16" and bits["szam"] == "17"
                  and bits["oldalak"] == "2885" and bits["issn"] == "2072-6643"
                  and bits["folyoirat_rovid"] == "Nutrients")
        ok &= _ok("the Article dataclass carries all five gate fields",
                  {"elso_szerzo", "szerzok", "folyoirat", "kotet", "validacio"}
                  <= set(collect.Article.__dataclass_fields__))

    print(f"\n{'ALL PASSED' if ok else 'FAILURES PRESENT'}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
