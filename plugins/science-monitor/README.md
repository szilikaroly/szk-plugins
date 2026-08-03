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
| `/sm:import MANIFEST` | Claude Science munkaegység-export beolvasása |
| `/sm:context SLUG` | Kontextus behívása a sessionbe |
| `/sm:submit SLUG` | Beadás rögzítése: folyóirat, cover letter, beküldve-e |
| `/sm:review SLUG [levél]` | Bírálat felvétele és pontokra bontása |
| `/sm:respond REVIEW_ID` | Response-to-reviewers összeállítása |
| `/sm:inbox` | Outlook/O365 (és Gmail) átnézése szerkesztői döntésekért (csak olvas) |
| `/sm:dashboard` | Dashboard — hiánylisták, checklistek, kattintható gombok |
| `/sm:journal SLUG` | Célújság választás — folyóirat-illesztés bizonyítékból |
| `/sm:repo pull\|push` | Szinkron a szerzőtársakkal egy közös git repón át |

### A dashboard két módja

```bash
sm.py serve        # élő: a pipák és gombok azonnal írnak az adatbázisba
sm.py dashboard    # statikus fájl: a gombok a parancsot másolják vágólapra
```

Az élő mód `127.0.0.1:8787`-en figyel, és minden POST-ot egy futásonként
generált tokenhez köt, amit csak a kiszolgált lap ismer. Kívülről nem elérhető.

Amit egy kattintás elintéz élő módban: **új kézirat felvétele** (űrlap a lap
tetején), **archiválás** és visszaállítás, a szerkesztői **verdikt** rögzítése
(beadva · peer-review · desk rejection · major/minor revision · elfogadva ·
elutasítva — dátummal együtt), checklist-tétel pipálása vagy `n/a`-ra tétele,
bírálói pont lezárása, cover letter állapotának léptetése, beküldve-jelölés.

**Elutasítás után** a kártyán megjelenik egy „Tovább innen" doboz a három valódi
lehetőséggel: **célújság választás** (`/sm:journal`), **újraírás**, **korrekció**
— plusz új beadási kör nyitása. Desk rejectionnél a célújság-váltás az
alapértelmezés, bírálat utáni elutasításnál az újraírás.

A checklistek alapból **összecsukva** vannak, nyíló szakaszként.
Amit nem — kontextus behívása, bírálat pontokra bontása, válaszlevél — az a
Claude Code dolga, azokra a gomb a `/sm:` parancsot másolja.

Mind egy-egy `scripts/sm.py` alparancs, tehát terminálból is megy:

```bash
python3 <plugin>/scripts/sm.py status
```

## Adatmodell

**projects** — a munkaegység. Egy slug, egy cím, egy gyökérmappa, plusz két
dimenzió:

- `state` — **folyamatban · hiánypótlás · korrekció · kész ✓ · elfogadva ·
  elutasítva**. Ez a munka állapota, függetlenül attól, van-e folyóirat.
  `sm.py state SLUG korrekcio`, vagy a dashboardon egy kattintás.
  `sm.py state --auto` kitölti a nyilvántartásból, de a kézzel beállított
  állapotot nem írja felül — kivéve, ha a beadás ténye cáfolja (elfogadva /
  elutasítva / revízió).
- `category` — `kutatas` (kézirat), `tamogato` (kutatás, de nem lesz belőle
  kézirat), `eszkoz` (agent/skill konfiguráció), `pelda`. Csak a `kutatas`
  kategóriától vár a hiánylista kéziratot, cover lettert és beadást; a többi
  ettől nem szemetel bele.

**submissions** — beadási kör. Egy kéziratnak több is lehet (elutasítás után új
folyóirat = új `seq`, a régi megmarad a történetben). Itt van külön mezőben:

- `cover_letter_state` — `missing` / `draft` / `ready`
- `submitted` + `submitted_at` — **külön a cover lettertől**: attól, hogy a
  cover letter kész, még nincs beküldve semmi. Ez a kettő soha nem egy mező.
- `status` — `drafting`, `ready`, `submitted` (beadva), `under_review`
  (peer-review), `desk_rejection`, `major_revision`, `minor_revision`,
  `revision_sent`, `accepted`, `rejected`, `withdrawn`

  A **desk rejection külön státusz** a bírálat utáni elutasítástól: a szerkesztő
  ki sem küldte, tehát a tudományról nem mond semmit — rendszerint scope vagy
  formátum. A dashboard ennek megfelelően más továbblépést ajánl.

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
sm.py scan ~/Documents --apply                 # felvétel
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
  fiókot (a `config mail_address` / `mail_provider` szerint — általában a
  levelező szerzői cím, ami gyakran nem az, amivel be vagy jelentkezve). Nem küld, nem válaszol, nem címkéz, nem törli. Portálra semmit nem
  tölt fel, és a kiadói „transfer recommendation" ajánlatokra nem lép.
- A beküldés tényét soha nem következteti ki fájlokból — azt te erősíted meg.
- A dashboard lokális HTML. Kiadatlan címeket és bírálati adatot tartalmaz,
  szóval ne publikáld Artifactként.

## Közös munka git-en

A lokális SQLite egy ember munkapéldánya. A megosztható igazság egy **privát**
git repóban van:

```
sm-repo.json                séma-verzió, szinkronizált szerepek
projects/<slug>.json        kéziratonként egy fájl: beadások, checklist,
                            bírálatok, bírálói pontok, fájlindex
documents/<hash>/<fájl>     a dokumentumok, tartalom szerint címezve
```

```bash
sm.py repo init ~/science-monitor-data    # létrehozás (a remote-ot te adod hozzá)
sm.py repo pull                           # munka elején
sm.py repo push -m "üzenet"               # munka végén
```

**Kéziratonként egy fájl** — ez a teljes merge-stratégia: két szerző különböző
kéziratokon dolgozva soha nem ér ugyanahhoz a fájlhoz, tehát a git nem kérdez.
A JSON rendezett és tördelt, így egy valódi ütközés emberi szemmel olvasható.

A repóba a `sync_roles` szerepek mennek — alapból kézirat, cover letter, válasz,
supplementary, hivatkozások. Az ábrák, adatok, kódok és a session-átiratok
helyben maradnak, de a bejegyzésük megőrzi, **melyik gépen** vannak, így a
szerzőtárs nem törött útvonalat lát, hanem azt, hogy a fájl máshol van.

⚠ A repo kiadatlan kéziratokat, cover lettereket és bírálói leveleket tartalmaz.
Csak privát remote-ra kerülhet.

## Beállítások

Minden gép- és személyfüggő adat a `~/.science-monitor/config.json`-ban van, nem
a kódban — ezért a plugin maga továbbadható:

```bash
sm.py config                                   # minden beállítás
sm.py config scan_roots ~/Documents,~/work     # hol keressen kéziratot
sm.py config mail_provider outlook             # outlook | gmail
sm.py config mail_address nev@intezmeny.hu     # a levelező szerzői cím
sm.py config sync_roles manuscript,cover_letter,response,supplement,refs
```

## Telepítés

A `szk-plugins` marketplace része. Bekapcsolás után a `/sm:` parancsok
elérhetők. Külső függőség nincs, csak a rendszer Python 3-a.
