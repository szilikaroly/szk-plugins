# Science Monitor

Kész kéziratok nyilvántartása **beadás szerint**: melyik folyóiratnál van, van-e
cover letter, **be van-e küldve**, mi jött vissza, és melyik bírálói pont
nincs még megválaszolva.

Két dolgot old meg, ami eddig fejben volt:

- **`/sm:context SLUG`** — egy kézirat teljes munkakontextusát behívja a
  sessionbe, egy lépésben, mérethatárral (nem önti be a 98 fájlt).
- **`/sm:review SLUG levél.txt`** — a beérkező bírálatot pontokra bontja,
  eltárolja, és onnantól követhető, melyikre van válasz.

Az adat lokális SQLite: `~/.science-monitor/monitor.db`. Semmi nem megy sehova.

## Parancsok

| Parancs | Mit csinál |
|---|---|
| `/sm:status` | Áttekintés: hol tart mi, mi sürgős |
| `/sm:scan [MAPPA]` | Kézirat-projektek keresése a lemezen, felvétele |
| `/sm:context SLUG` | Kontextus behívása a sessionbe |
| `/sm:submit SLUG` | Beadás rögzítése: folyóirat, cover letter, beküldve-e |
| `/sm:review SLUG [levél]` | Bírálat felvétele és pontokra bontása |
| `/sm:respond REVIEW_ID` | Response-to-reviewers összeállítása |
| `/sm:inbox` | Outlook/O365 (és Gmail) átnézése szerkesztői döntésekért (csak olvas) |
| `/sm:dashboard` | Dashboard — hiánylisták, checklistek, kattintható gombok |

### A dashboard két módja

```bash
sm.py serve        # élő: a pipák és gombok azonnal írnak az adatbázisba
sm.py dashboard    # statikus fájl: a gombok a parancsot másolják vágólapra
```

Az élő mód `127.0.0.1:8787`-en figyel, és minden POST-ot egy futásonként
generált tokenhez köt, amit csak a kiszolgált lap ismer. Kívülről nem elérhető.

Amit egy kattintás elintéz élő módban: checklist-tétel pipálása vagy `n/a`-ra
tétele, bírálói pont lezárása, cover letter állapotának léptetése
(nincs → piszkozat → kész), beküldve-jelölés (dátummal és státusszal együtt).
Amit nem — kontextus behívása, bírálat pontokra bontása, válaszlevél — az a
Claude Code dolga, azokra a gomb a `/sm:` parancsot másolja.

Mind egy-egy `scripts/sm.py` alparancs, tehát terminálból is megy:

```bash
python3 ~/Documents/claude/szk-plugins/plugins/science-monitor/scripts/sm.py status
```

## Adatmodell

**projects** — a kézirat. Egy slug, egy cím, egy gyökérmappa.

**submissions** — beadási kör. Egy kéziratnak több is lehet (elutasítás után új
folyóirat = új `seq`, a régi megmarad a történetben). Itt van külön mezőben:

- `cover_letter_state` — `missing` / `draft` / `ready`
- `submitted` + `submitted_at` — **külön a cover lettertől**: attól, hogy a
  cover letter kész, még nincs beküldve semmi. Ez a kettő soha nem egy mező.
- `status` — `drafting`, `ready`, `submitted`, `under_review`,
  `major_revision`, `minor_revision`, `revision_sent`, `accepted`, `rejected`,
  `withdrawn`

**files** — a projekt fájljai szerep szerint (`manuscript`, `cover_letter`,
`response`, `supplement`, `figure`, `table`, `refs`, `data`, `code`, `other`).
A `/sm:context` ebből építi az olvasási tervet.

**reviews** + **review_points** — a beérkezett levél és a belőle kibontott
pontok. Pontonként: bíráló, sorszám, súlyosság, mit érint, a válasz, a
megtett változtatás, és az állapot (`open` / `drafted` / `done` / `declined`).

**checklist** — beadási checklist beadásonként, a kézirat `kind` mezője szerint
szabva (systematic-review → PRISMA + RoB, hypothesis → falszifikálhatóság stb.).
Minden tétel `done` / `n/a` / nyitva.

**events** — idővonal minden kézirathoz.

A **hiánylista** nincs tárolva, mindig frissen számolódik (`sm.py gaps`): nincs
cover letter, kész de nincs beküldve, revíziót kértek de nincs bírálói levél,
nyilvántartott fájl hiányzik a lemezről, nyitott bírálói pont határidő közelében,
elutasítva de nincs új folyóirat. Minden hiány mellé jár a parancs, ami javítja.

## Tipikus menet

```bash
sm.py scan ~/Documents/claude --apply          # felvétel
sm.py set endo-ai-framework --title "..."      # rendes cím
sm.py submit endo-ai-framework --journal "Frontiers in Reproductive Health" \
     --cover ~/.../cover_letter.docx --status ready
sm.py submit endo-ai-framework --sent          # tényleg elment
sm.py review add endo-ai-framework --file letter.txt \
     --decision major_revision --due 2026-09-15
sm.py review points 1 --json points.json       # a /sm:review bontja ki
sm.py respond 1                                # válaszlevél váza
```

## Határok

- A `scan` heurisztikus. Előbb szárazon fut, és csak `--apply` esetén ír — a
  javaslatot nézd át (egy kódmappa is bekerülhet, ha van benne `.docx`).
  Egyetlen kész beadási csomagra: `sm.py scan MAPPA --single --apply`.
- A `/sm:inbox` **csak olvassa** a postafiókot — elsődlegesen az Outlook/O365
  fiókot (`szili.karoly@sze.hu`, ez a levelező szerzői cím), másodsorban a
  Gmailt. Nem küld, nem válaszol, nem címkéz, nem törli. Portálra semmit nem
  tölt fel, és a kiadói „transfer recommendation" ajánlatokra nem lép.
- A beküldés tényét soha nem következteti ki fájlokból — azt te erősíted meg.
- A dashboard lokális HTML. Kiadatlan címeket és bírálati adatot tartalmaz,
  szóval ne publikáld Artifactként.

## Telepítés

A `szk-plugins` marketplace része. Bekapcsolás után a `/sm:` parancsok
elérhetők. Külső függőség nincs, csak a rendszer Python 3-a.
