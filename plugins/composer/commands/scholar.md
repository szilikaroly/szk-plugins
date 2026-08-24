---
description: Google Scholar learatás — kiegészítő forrás, ugyanazzal az 5D befogadási kapuval
allowed-tools: Bash, Read
---
Run a Composer Google Scholar sweep. What the user asked for: $ARGUMENTS

**Say this once, before running, and do not soften it.** Google Scholar has no
API: the script reads the public result pages, which Google's terms do not allow
and which Google blocks after sustained querying. A Scholar search is also not
reproducible — the ranking is personalised, the "About N results" figure is a
rounded estimate, and only ~1000 results are reachable. Cochrane and PRISMA-S
therefore treat Scholar as a **supplementary** source. If the user has not run a
database search (PubMed via `/composer:harvest`, and ideally Embase or CENTRAL
by hand), run that first — Scholar on its own is not a defensible search base.

1. **Rewrite the query into Scholar syntax.** PubMed field tags are meaningless
   to Scholar; the script refuses a query containing them, and it is right to.
   Scholar understands `"quoted phrases"`, `AND` / `OR`, `-excluded`,
   `intitle:`, `author:"Surname"`, `source:"Journal"`. Show the user the exact
   string before running it.
2. **Start small.** `--retmax 20 --no-pdf` on a new topic. A large first run is
   how the IP gets a CAPTCHA, and then nothing works for hours.
3. Run:

```
"${CLAUDE_PLUGIN_ROOT}/scripts/scholar" --outdir ~/Documents/PubMed_Downloads \
    --query '<SCHOLAR QUERY>' --query-name <SLUG> --retmax <N> --years <N> --xml-fallback
```

   Add `--after <SEARCH FOLDER>` when this sweep supplements a PubMed search —
   it stamps the parent log as "Scholar: run" and back-references the two
   directories, which is what PRISMA-S asks for per source. Normally you arrive
   here from the question `/composer:harvest` asks at the end of every run.
   Add `--protocol <file>` when one exists. `--min-citations N` is the cheapest
   way to cut Scholar's grey-literature noise. `--pause` (default 1.5s) is the
   politeness dial — raise it, never lower it.
4. **Read the resolution line out.** It says how many hits got a DOI from their
   own link, how many were matched to Crossref by title, how many stayed
   unidentified, and how many turned out to be in PubMed. A hit that stayed
   without a DOI cannot pass the 5D gate — that is the expected, honest outcome
   for a thesis or a non-indexed journal, and it is the user's decision whether
   such a record is worth chasing by hand.
5. Report the gate — admitted / held / rejected — and the duplicates against the
   existing corpus. A record already found by PubMed is not counted twice; its
   corpus row is stamped `PubMed; Google Scholar` instead.
6. Point at `keresesek/<stamp>_gs-<slug>/NAPLO.md`, which carries the Scholar
   limitations in a form that can go straight into the methods section, and
   offer the PRISMA step (`/composer:prisma`) next.
