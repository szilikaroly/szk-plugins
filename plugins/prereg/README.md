# prereg — PROSPERO és OSF regisztráció a böngészőn keresztül

Egy systematic review regisztrációját végzi a PROSPERO vagy az OSF Registries űrlapján,
a megadott szempontokból, a belső böngészőben, a bejelentkezett felhasználóval. A protokoll
szövegét a spec-ből generálja (PROSPERO), de minden mondat a te döntésed.

**0.2.0 újdonságai:** csapattag-adatok az alap ORCID-listából (megerősítéssel), a célok (aims)
bekérése, a protokoll készítése és a feltöltés külön jóváhagyással (C kapu), a bejelentkezés
ellenőrzése minden munkamenet elején, és a PROSPERO-s szakaszonkénti jelölés gyakorlata.

## Mit csinál

1. **Útvonal** — PROSPERO-képes-e a review (narratív, scoping, állat-only, in vitro, Cochrane,
   és az, ha az adatkinyerés már elkezdődött, PROSPERO-ban nem regisztrálható). Ha nem, OSF.
2. **Hasonló regisztrációk** — OSF publikus API-ján és a PROSPERO keresőjében; átfedés esetén megáll.
   Konvenciókat (outcome-definíciók, RoB-eszközök, szintézis-leírás) javasol, szöveget nem másol.
3. **Három ellenőrzési kör** — mindegyik find → verify → fix, legfeljebb háromszor:
   - **1. kör, script** (`prereg.py check`): kötelező mezők, helyőrzők (`TBD`, `[AUTHOR-VERIFY …]`),
     ORCID-ellenőrző jegy, dátumok, a szakasztábla, nyelv, hasonló-rekord indoklás.
   - **2. kör, független bíráló** (friss subagent): kérdés–design–szintézis–keresés–időzítés
     összhangja. Nem kapja meg az én érveimet, csak a spec-et és a te eredeti szempontjaidat.
   - **3. kör, élő űrlap visszaolvasása**: a formon lévő értékek összevetése a jóváhagyott tervvel
     (`prereg.py readback`).
4. **Csapat és célok** — a csapattagok nevéhez az alap ORCID-listából (`references/orcid-registry.json`)
   ajánl azonosítót, de csak a te megerősítéseddel; a beleegyezést te adod meg. A célokat (aims) te adod meg.
5. **Protokoll** — a spec-ből készül (`prereg.py protocol`): `protocol.md`, `protocol.pdf` (ha van
   pandoc és xelatex), és `protocol.json` SHA-256 értékekkel. PROSPERO-hoz és OSF-hez egyaránt; a láthatóságot
   (`protocol_visibility`) te döntöd el, és a spec-ben rögzítjük.
6. **Három kapu** — (A) a tartalom jóváhagyása, mielőtt bármi a böngészőbe kerül; (C) a protokoll
   feltöltése, külön fájlra, külön igenedre; (B) minden beküldés külön, kifejezett jóváhagyása.
7. **Utána** — step-by-step tervek `prereg/<slug>/handoff/` alá: `composer`, `validator`,
   `metaANAL` (R-modul-terv), `praxist` (csak ha van futtatható modell).

## Mit nem csinál

- Nem jelentkezik be, nem hoz létre fiókot, nem ír be jelszót. A bejelentkezést minden munkamenet
  elején ellenőrzi, és ha nincs bejelentkezve, megáll.
- Nem jelöli be a nyilatkozatokat (konfliktus, hozzájárulás, „a adatok pontosak").
- Nem küld be, nem von vissza, nem embargóz és nem töröl semmit a te jóváhagyásod nélkül. Protokollt
  sem tölt fel a C kapu igenje nélkül.
- Nem talál ki nevet, ORCID-ot, forrást, dátumot, keresési stringet, azonosítót vagy hivatkozást.
  A törzsadat-lista egy név alapján sem jelent beleegyezést.
- Nem ír protokoll-szöveget kézzel: a protokoll a spec-ből jön, a spec-et te jóváhagyod.

## Használat

```
/prereg:start PROSPERO-ban regisztrálnám a dietary fibre és GDM dose-response review-t
```

Az `agents/prereg.md` eljárást a fő beszélgetésben kell futtatni, mert a két kapu a chatben válaszol.
Csak a 2. kör bíráló subagent.

Kézi parancsok (a script):

```bash
P="${CLAUDE_PLUGIN_ROOT}/scripts/prereg.py"
python3 "$P" route  prereg/<slug>/spec.json
python3 "$P" check  prereg/<slug>/spec.json --registry prospero
python3 "$P" plan   prereg/<slug>/spec.json --registry prospero --out prereg/<slug>/plan.json
python3 "$P" similar "gestational diabetes"
python3 "$P" fields prospero
python3 "$P" pubmed-count "(semaglutide[tiab] OR tirzepatide[tiab]) AND pregnan[tiab]" --maxdate 2026/08/05 --datetype edat
python3 "$P" orcid "Viktor Gulyás-Oldal"
python3 "$P" protocol prereg/<slug>/spec.json --registry prospero --out prereg/<slug>/protocol --pdf
python3 scripts/selftest.py
```

## Fájlok

| Út | Mi |
|---|---|
| `agents/prereg.md` | az eljárás: fázisok, három kör, két kapu, kézi és visszaolvasó lépések, a handoff |
| `commands/start.md` | `/prereg:start` — a fenti eljárás elindítása a fő beszélgetésben |
| `skills/prereg/SKILL.md` | szabályok (útvonal, időzítés, stage-tábla), PROSPERO mezőkódok, keresési szintaxis, ellenőrzések listája |
| `skills/prereg/references/prospero-form.json` | 48 PROSPERO mező két élő nyilvános rekordból (CRD420261486377, CRD420251001515) |
| `skills/prereg/references/osf-sr-form.json` | 61 kötelező OSF-kérdés, az OSF publikus sémájából generálva |
| `skills/prereg/references/orcid-registry.json` | az alap ORCID-lista: a társszerzők és a saját iD, bylinenként |
| `examples/spec.template.json` | üres spec (a `aims` mezővel) — ebből indul minden futás |
| `scripts/prereg.py` | route, check, plan, readback, similar, fields, orcid, protocol |
| `scripts/selftest.py` | 70 offline eset (hálózat nélkül) |

## Első éles futás előtt — ellenőrizendő

Ezeket a publikus rekordból és a sémából állítottam össze, nem a bejelentkezés utáni űrlapból:

- **PROSPERO kötelező-jelölései** (`prospero-form.json` `required`). A rekord mutatja, mit töltöttek ki,
  nem azt, mit kényszerít ki az űrlap. Az első futásnál ellenőrizd a bejelentkezett űrlapot, és
  javítsd a JSON-t, ha eltér.
- **PROSPERO feliratai.** A rekord felirata lehet más, mint az űrlapé. A böngésző-lépés a feliratokat
  jelentésük szerint feleltetteti meg, és eltérésnél szól.
- **OSF**: a plugin csak a *Generalized Systematic Review Registration* sémát térképezi. Nem
  szisztematikus review-khoz az *Open-Ended Registration* (`5df83f7dd28338001ac0ab0d`) való; ahhoz
  ugyanazzal a lekérdezéssel új térkép készül.

## Ismert korlátok

- A PROSPERO-űrlap nem látható bejelentkezés nélkül, ezért a mezőlista a rekordból van.
- A `similar` csak az OSF-et éri el API-n; a PROSPERO-keresés a böngészőben fut.
- A visszaolvasás azt ellenőrzi, amit a böngésző lát. Egy mező, amit az űrlap nem mutat vissza,
  nem ellenőrizhető.
- Az OSF *withdrawal* és *embargo* szabályai az OSF súgójából származnak (2026-10-12); a
  beküldés előtt érdemes az aktuális súgót megnézni.
