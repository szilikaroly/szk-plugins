#!/usr/bin/env python3
"""Journal blacklist — MTMT "Norvég lista" (kifogásolható gyakorlatot folytató folyóiratok).

Source: https://www.mtmt.hu/norveg_lista/  (backend: POST /backend/norveg.php, ev=<year>)
Policy (user decision, 2026-09-18): listed journals are banned BOTH as publication
venues AND as cited sources.

Data lives in ~/.szk-blacklist/norveg_lista.json (override with $SZK_BLACKLIST).
`update` also maps every listed ISSN to its NLM abbreviations (MedAbbr/IsoAbbr from
https://ftp.ncbi.nlm.nih.gov/pubmed/J_Medline.txt) so references written in
Vancouver/AMA style ("Curr Opin Endocrinol Diabetes Obes") match offline.

Verdicts:
  BLOCKED  ISSN match, or an exact journal segment equal to a listed journal's NLM
           abbreviation (NLM abbreviations are unique)
  SUSPECT  only the MTMT title matches — a same-named legitimate journal is
           possible; confirm the ISSN before acting

This file is the canonical copy; szk-plugins vendor it verbatim as
scripts/journal_blacklist.py. Library API: load(), Blacklist.check_issns(),
.check_title(), .check_reference(text), .check_doi(doi) (network).

CLI:
  journal_blacklist.py update [--year 2026]        refresh from MTMT (+ NLM abbreviations)
  journal_blacklist.py check  <ISSN|DOI|title> ...  check venues (DOI -> Crossref ISSN)
  journal_blacklist.py refs   <file> [--offline]    scan a manuscript / reference list
  journal_blacklist.py stats
Exit code: 2 if anything BLOCKED, 1 if only SUSPECT, 0 if clean.
"""
import json, re, sys, os, html, urllib.request, urllib.parse, unicodedata, datetime, subprocess

DEFAULT_DIR = os.path.join(os.path.expanduser("~"), ".szk-blacklist")
DATA = os.environ.get("SZK_BLACKLIST") or os.path.join(DEFAULT_DIR, "norveg_lista.json")
ISSN_RE = re.compile(r"\b(\d{4})-?(\d{3}[\dXx])\b")
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>;,]+[^\s\"<>;,.)\]])", re.I)
# Crossref's polite pool wants a contact address; taken from the environment
# so no address is baked into the published plugins.
_MAIL = os.environ.get("CROSSREF_MAILTO") or os.environ.get("NCBI_EMAIL") or ""
UA = "szk-blacklist/1.1" + (f" (mailto:{_MAIL})" if _MAIL else "")
NLM_URL = "https://ftp.ncbi.nlm.nih.gov/pubmed/J_Medline.txt"
# single-word abbreviations that are ordinary English words: a bare segment
# "Commentary." is more likely an article-title fragment than the journal
GENERIC = {"current", "change", "insight", "commentary", "nursing", "involve",
           "microscope", "complexity", "formulary", "futurist", "soundings",
           "montana", "albion", "orbis", "ponte", "critica", "rn", "stal"}


def norm_title(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def norm_issn(a, b):
    return f"{a}-{b.upper()}"


def issns_in(text):
    return list(dict.fromkeys(norm_issn(a, b) for a, b in ISSN_RE.findall(text)))


# ------------------------------------------------------------------ update --
def _http(url, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout).read()


def _nlm_abbrevs():
    """ISSN -> set of NLM abbreviations, from the MEDLINE journal catalogue."""
    raw = _http(NLM_URL, timeout=180).decode("utf-8", "replace")
    out = {}
    for rec in raw.split("-" * 20):
        f = dict(l.split(": ", 1) for l in rec.strip().splitlines() if ": " in l)
        ab = {f.get("MedAbbr", "").strip(), f.get("IsoAbbr", "").strip()} - {""}
        for k in ("ISSN (Print)", "ISSN (Online)"):
            m = ISSN_RE.search(f.get(k, ""))
            if m and ab:
                out.setdefault(norm_issn(*m.groups()), set()).update(ab)
    return out


def update(year, path=DATA):
    rows = json.loads(_http("https://www.mtmt.hu/backend/norveg.php",
                            urllib.parse.urlencode({"ev": year}).encode()))
    if not rows:
        sys.exit(f"MTMT returned no data for {year}")
    try:
        nlm = _nlm_abbrevs()
    except Exception as e:
        print(f"warning: NLM catalogue unavailable ({e}); abbreviations skipped", file=sys.stderr)
        nlm = {}
    out = []
    for mtmt_id, raw, since, url in rows:
        issns = sorted({norm_issn(a, b) for a, b in ISSN_RE.findall(raw)})
        abbr = sorted(set().union(*(nlm.get(i, set()) for i in issns)) if issns else set())
        out.append({"mtmt_id": mtmt_id, "title": ISSN_RE.sub("", raw).strip(" ,;"),
                    "issn": issns, "nlm_abbr": abbr, "since": since,
                    "kanalregister": url, "raw": raw})
    doc = {"source": "https://www.mtmt.hu/norveg_lista/", "list_year": year,
           "fetched": datetime.date.today().isoformat(), "count": len(out),
           "policy": "banned for publication AND citation", "journals": out}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)  # atomic: concurrent readers never see a half-written file
    n_ab = sum(1 for j in out if j["nlm_abbr"])
    print(f"{len(out)} journals saved ({year}), {n_ab} with NLM abbreviations -> {path}")


# ----------------------------------------------------------------- library --
class Blacklist:
    def __init__(self, doc):
        self.doc = doc
        self.by_issn, self.by_title, self.by_abbr = {}, {}, {}
        for j in doc["journals"]:
            for i in j["issn"]:
                self.by_issn[i] = j
            self.by_title.setdefault(norm_title(j["title"]), j)
            for a in j.get("nlm_abbr", []):
                self.by_abbr.setdefault(norm_title(a), j)
        self._cr = {}

    def check_issns(self, issns):
        for i in issns:
            if i in self.by_issn:
                return "BLOCKED", self.by_issn[i], f"ISSN {i}"
        return "OK", None, ""

    def check_title(self, title, issns=()):
        """Verdict for a journal name (full or NLM-abbreviated)."""
        v = self.check_issns(issns)
        if v[0] != "OK" or not title:
            return v
        t = norm_title(title)
        if t in self.by_abbr and not issns:
            if t in GENERIC:
                return "SUSPECT", self.by_abbr[t], "generic one-word abbreviation — confirm it is the journal"
            return "BLOCKED", self.by_abbr[t], "NLM abbreviation match"
        j = self.by_title.get(t) or self.by_abbr.get(t)
        if j:
            if issns and j["issn"]:
                return "SUSPECT", j, "title matches, ISSN differs (likely a namesake — verify)"
            return "SUSPECT", j, "title match (no ISSN to confirm)"
        return "OK", None, ""

    def check_reference(self, ref):
        """Offline verdict for one reference entry: ISSN in text, else any
        '.'-delimited segment equal to a listed journal name/abbreviation."""
        v = self.check_issns(issns_in(ref))
        if v[0] != "OK":
            return v
        best = ("OK", None, "")
        for seg in re.split(r"[.?!]\s+|\s*[;:]\s*", ref):
            seg = re.sub(r"\s*\(?\d{4}\)?.*$", "", seg.strip())  # drop trailing year/volume
            if len(seg) < 3:
                continue
            r = self.check_title(seg)
            if r[0] == "BLOCKED":
                return r
            if r[0] == "SUSPECT" and best[0] == "OK" and (
                    len(norm_title(seg).split()) >= 2 or norm_title(seg) in self.by_abbr):
                best = r
        return best

    def crossref(self, doi):
        if doi in self._cr:
            return self._cr[doi]
        try:
            m = json.loads(_http("https://api.crossref.org/works/" + urllib.parse.quote(doi),
                                 timeout=30))["message"]
            r = (issns_in(" ".join(m.get("ISSN", []))),
                 html.unescape((m.get("container-title") or [""])[0]))
        except Exception:
            r = None
        self._cr[doi] = r
        return r

    def check_doi(self, doi):
        cr = self.crossref(doi)
        if cr is None:
            return "UNRESOLVED", None, "Crossref lookup failed", ""
        issns, title = cr
        v = self.check_title(title, issns)
        return (*v, f"{title}; {', '.join(issns)}")


def load(path=DATA):
    """Return a Blacklist, or None if the data file is missing."""
    if not os.path.exists(path):
        return None
    return Blacklist(json.load(open(path, encoding="utf-8")))


def describe(j):
    return f"{j['raw']} (MTMT {j['mtmt_id']}, on the Norvég lista since {j['since']})"


# --------------------------------------------------------------------- CLI --
def _report(results):
    worst = 0
    for q, v, j, why in results:
        if v == "OK":
            continue
        worst = max(worst, 2 if v == "BLOCKED" else 1 if v == "SUSPECT" else worst)
        print(f"[{v}] {q}\n    {why}" + (f" -> {describe(j)}" if j else ""))
    c = lambda s: sum(r[1] == s for r in results)
    print(f"\n{len(results)} checked: {c('OK')} OK, {c('BLOCKED')} BLOCKED, "
          f"{c('SUSPECT')} SUSPECT, {c('UNRESOLVED')} UNRESOLVED")
    return worst


def _read_text(path):
    """doctotext / pdftotext when on PATH, else pandoc, else the raw .docx XML —
    Git Bash on Windows has no doctotext, and a crash there hid every result."""
    low = path.lower()
    if not low.endswith((".docx", ".doc", ".pdf", ".odt", ".rtf")):
        return open(path, encoding="utf-8", errors="replace").read()
    if low.endswith(".pdf"):
        tools = [["pdftotext", "-layout", path, "-"]]
    else:
        tools = [["doctotext", path], ["pandoc", path, "-t", "plain", "--wrap=none"]]
    for cmd in tools:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout
        except FileNotFoundError:
            continue
    if low.endswith(".docx"):
        import zipfile
        xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "replace")
        xml = xml.replace("</w:p>", "\n")
        return html.unescape(re.sub(r"<[^>]+>", "", xml))
    sys.exit(f"cannot extract text from {path}: install doc-tools or pandoc")


def _check_query(bl, q):
    q = q.strip()
    m = DOI_RE.search(q)
    if m:
        v, j, why, meta = bl.check_doi(m.group(1))
        return f"{q}  [{meta}]", v, j, why
    iss = issns_in(q)
    rest = ISSN_RE.sub("", q).strip()
    return (q, *bl.check_title(rest, iss)) if rest else (q, *bl.check_issns(iss))


def _ref_lines(text):
    """Reference-list entries: text after a References heading, one per line.
    A list flattened into one paragraph is split after every DOI, so no entry
    hides behind the first DOI on its line."""
    m = list(re.finditer(r"^\s*(references|bibliography|irodalom(jegyz[eé]k)?|literature cited)\s*$",
                         text, re.I | re.M))
    body = text[m[-1].end():] if m else text
    out = []
    for l in body.splitlines():
        l = l.strip()
        cut = 0
        for d in DOI_RE.finditer(l):  # Vancouver entries end in their DOI
            out.append(l[cut:d.end()].strip())
            cut = d.end()
        out.append(l[cut:].strip())
    return [l for l in out if len(l) > 20]


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "update":
        year = int(rest[rest.index("--year") + 1]) if "--year" in rest else datetime.date.today().year
        update(year); return 0
    bl = load()
    if bl is None:
        sys.exit(f"no blacklist data at {DATA}; run: journal_blacklist.py update")
    if cmd == "stats":
        d = bl.doc
        print(f"{d['count']} journals, list year {d['list_year']}, fetched {d['fetched']}, "
              f"{len(bl.by_issn)} ISSNs, {len(bl.by_abbr)} NLM abbreviations; policy: {d['policy']}")
        return 0
    if cmd == "check":
        return _report([_check_query(bl, q) for q in rest])
    if cmd == "refs":
        offline = "--offline" in rest
        text = _read_text([a for a in rest if a != "--offline"][0])
        items, seen = [], set()
        for line in _ref_lines(text):
            v, j, why = bl.check_reference(line)
            if v == "OK" and not offline:
                d = DOI_RE.search(line)
                if d:
                    v, j, why, _ = bl.check_doi(d.group(1).rstrip("."))
            key = (v, j["mtmt_id"] if j else None, line[:80])
            if key not in seen:
                seen.add(key)
                items.append((line[:140], v, j, why))
        return _report(items)
    print(__doc__); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
