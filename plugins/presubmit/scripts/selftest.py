#!/usr/bin/env python3
"""Self test: plant ten known mistakes in a manuscript and assert every one is
caught (and that a clean manuscript passes). Exit 0 = pass.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pc_lib
import pc_checks as C
import pc_extract

# A manuscript missing Methods, missing email, missing COI + funding, with a
# duplicate reference (same DOI), a reference with no year, an out-of-range
# citation, an uncited reference, and a repeated word.
BAD = """A Study of Hearts in Mice
John Smith, Jane Doe
Department of Cardiology, Example University

Abstract
This is a short abstract about hearts.

Keywords
heart, mice, cardiology, study

Introduction
The the study begins here. We cite the first work [1] and the second [2].
We also cite a reference that does not exist [99].

Results
Hearts were observed.

Discussion
This matters.

Conclusions
Done.

References
1. Smith J, Doe A. A study of hearts. Cardiology Journal. 2019;10:1-5. doi:10.1000/abc123
2. Brown B. Another paper without a year. Some Journal. doi:10.1000/xyz789
3. Smith J, Doe A. A study of hearts. Cardiology Journal. 2019;10:1-5. doi:10.1000/abc123
"""

# A clean-enough manuscript that should produce no ERRORs.
GOOD = """Cardiac Outcomes After Intervention
John Smith, Jane Doe
Department of Cardiology, Example University. Corresponding: js@example.edu

Abstract
""" + ("This study evaluates cardiac outcomes in a controlled cohort. " * 20) + """

Keywords
heart, outcomes, cardiology, intervention

Introduction
We cite the first work [1] and the second [2]. Neither addresses outcomes after
discharge, which is the gap this study fills.

Methods
We did methods.

Results
We found results.

Discussion
We discuss. A limitation is the single-centre design, which biases toward
healthier patients.

Conclusions
We conclude.

Conflict of Interest
The authors declare no conflicts of interest.

Funding
This research received no specific funding.

References
1. Smith J, Doe A. A study of hearts. Cardiology Journal. 2019;10:1-5. doi:10.1000/abc123
2. Brown B. Vessels and flow. Vascular Reports. 2020;5:22-30. doi:10.1000/xyz789
"""


# An opinion-format manuscript carrying the mistakes a real editorial round
# actually produced: a declared word count over the limit, more references than
# the format allows, an ethics block that belongs on the disclosure form, a
# placeholder, subgroup estimates without confidence intervals, a study named
# only by acronym, the same study described twice, and the authors' own trial
# promoted in the closing. Synthetic throughout — no real manuscript text.
OPINION = """Why Treatment Duration Deserves a Trial
Alex Roe, Kim Lee
Department of Medicine, Example University. Corresponding: ar@example.edu

Word Count: 1400
References: 11
Running head: Treatment duration

Ethics approval: This work was approved by the Example University ethics board and
registered at ClinicalTrials.gov before enrollment.

Consider a patient finishing a long course of therapy. The question is common and, on
present evidence, unanswerable.

In EXAMPLAR, treatment reduced events by a fifth (relative risk, 0.74; 95% CI, 0.61
to 0.89) (1). The relative risk was higher with longer courses (2.13) than with
shorter ones (1.02) (2).

A shorter course was tested in a randomized open-label pilot of 88 adults with chronic
kidney disease, and fewer of them stopped early (3). TBD: add the follow-up numbers
here.

A shorter course was tested in a randomized open-label pilot of 88 adults with chronic
kidney disease, and fewer of them stopped early, which improved adherence (3).

Our own program is enrolling; a randomized comparison is planned, not begun. Future
trials should settle the duration.

References
1. Author A, Author B. A trial of something. Journal of Trials. 2024;1:1-9. doi:10.1000/aaa111
2. Author C. A meta-analysis of harms. Harms Journal. 2023;2:10-20. doi:10.1000/bbb222
3. Author D. A pilot of titration. Pilot Journal. 2025;3:30-40. doi:10.1000/ccc333
4. Author E. Fourth work. Journal Four. 2021;4:1-2. doi:10.1000/ddd444
5. Author F. Fifth work. Journal Five. 2021;5:1-2. doi:10.1000/eee555
6. Author G. Sixth work. Journal Six. 2021;6:1-2. doi:10.1000/fff666
7. Author H. Seventh work. Journal Seven. 2021;7:1-2. doi:10.1000/ggg777
8. Author I. Eighth work. Journal Eight. 2021;8:1-2. doi:10.1000/hhh888
9. Author J. Ninth work. Journal Nine. 2021;9:1-2. doi:10.1000/iii999
10. Author K. Tenth work. Journal Ten. 2021;10:1-2. doi:10.1000/jjj000
11. Author L. Eleventh work. Journal Eleven. 2021;11:1-2. doi:10.1000/kkk111
"""

_DOCX_DOC = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:body><w:p>'
    '<w:commentRangeStart w:id="0"/>'
    '<w:r><w:t>The dose was </w:t></w:r>'
    '<w:ins w:id="1" w:author="An Editor" w:date="2026-01-01T00:00:00Z">'
    '<w:r><w:t>probably </w:t></w:r></w:ins>'
    '<w:del w:id="2" w:author="An Editor" w:date="2026-01-01T00:00:00Z">'
    '<w:r><w:delText>certainly </w:delText></w:r></w:del>'
    '<w:r><w:t>too high.</w:t></w:r>'
    '<w:commentRangeEnd w:id="0"/>'
    '<w:r><w:commentReference w:id="0"/></w:r>'
    '</w:p></w:body></w:document>')

_DOCX_COMMENTS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:comment w:id="0" w:author="An Editor" w:date="2026-01-01T00:00:00Z">'
    '<w:p><w:r><w:t>Please clarify this sentence.</w:t></w:r></w:p>'
    '</w:comment></w:comments>')

_DOCX_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Target="word/document.xml" Type="http://schemas.openxmlformats.'
    'org/officeDocument/2006/relationships/officeDocument"/></Relationships>')


def _docx_with_revisions():
    """A minimal .docx that still carries tracked changes and one comment."""
    import zipfile
    p = Path(tempfile.mktemp(suffix=".docx"))
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("_rels/.rels", _DOCX_RELS)
        z.writestr("word/document.xml", _DOCX_DOC)
        z.writestr("word/comments.xml", _DOCX_COMMENTS)
    return p

# A review that omits the guards the later referee cohorts asked for. Every
# code in REVIEWER_EXPECT came from a real report; see
# skills/presubmit/references/reviewer-patterns.md.
REVIEWER_BAD = """A Systematic Review of Gut Signals in Early Detection of Heart Failure
John Smith, Jane Doe
Department of Cardiology, Example University. Corresponding: js@example.edu

Abstract
""" + ("This review synthesises microbiome classifiers for heart failure. " * 15) + """

Keywords
heart, microbiome, review, screening

Introduction
Heart failure remains a growing burden [1]. No previous review has integrated
these areas. Screening for heart failure is proposed here; screening is
cheap, screening is fast, screening is scalable, screening is acceptable,
screening is feasible, screening is needed, screening is overdue. The ABT
result is combined with the ABT threshold [citation needed].
A significant proportion of patients are undiagnosed.
Dietary fibre prevents heart failure in cohort and case-control data.

Methods
We read the literature. Studies were included if relevant.

Results
Classifier A reached AUC 0.91 and classifier B AUC 0.88; AUC 0.84, AUC 0.79,
AUC 0.90 and AUC 0.77 were reported elsewhere, with 95% CI given in each.
The approach is not yet validated. We recommend that stepwise example
care should be adopted in routine practice. The target of 3 mmol per week
during follow-up guides escalation. Our ongoing trial compares the two
strategies.
In two small trials no adverse events were reported, so the intervention is safe.

Discussion
""" + ("The findings are discussed at length in this paragraph. " * 60) + """

Conclusions
We conclude that the next step is a trial.

Conflict of Interest
The authors declare no conflicts of interest. A large language model
(ChatGPT) was used for language editing.

Funding
This research received no specific funding.

References
1. Smith J, Doe A. A study of hearts. Cardiology Journal. 2015;10:1-5. doi:10.1000/abc1 {Smith J; 2015; Cardiology Journal}
2. Brown B. Vessels and flow. Vascular Reports. 2014;5:22-30. doi:10.1000/xyz2 {Brown B; 2014; Vascular Reports}
3. Green G. Pumps. Pump Journal. 2013;1:1-2. doi:10.1000/pq3 {Green G; 2013; Pump Journal}
4. White W. Valves. Valve Journal. 2012;2:3-4. doi:10.1000/vv4 {White W; 2012; Valve Journal}
5. Black K. Flow. Flow Journal. 2011;3:5-6. doi:10.1000/ff5 {Black K; 2011; Flow Journal}
6. Grey G. Beats. Beat Journal. 2010;4:7-8. doi:10.1000/bb6 {Grey G; 2010; Beat Journal}
7. Gold A. Rhythm. Rhythm Journal. 2010;4:9-10. doi:10.1000/rr7 {Gold A; 2010; Rhythm Journal}
8. Blue B. Tone. Tone Journal. 2010;4:11-12. doi:10.1000/tt8 {Blue B; 2010; Tone Journal}
"""

REVIEWER_EXPECT = [
    ("editorial placeholder", "editorial-placeholder"),
    ("'systematic' in title with no machinery", "systematic-label-unsupported"),
    ("review with no reproducible search", "search-not-reported"),
    ("no limitations anywhere", "limitations-absent"),
    ("effect sizes in prose, no table", "evidence-table-absent"),
    ("recommendation despite 'not yet validated'", "recommendation-outruns-evidence"),
    ("numeric target with no source", "numeric-target-unsourced"),
    ("own trial with no registration", "own-study-registration-unstated"),
    ("absolute novelty claim", "novelty-unhedged"),
    ("undefined abbreviation", "abbreviation-undefined"),
    ("reference entries doubled in a second format", "reference-entry-double-format"),
    ("AI disclosed, references not verified", "ai-references-verification-unstated"),
    ("references not current", "references-not-current"),
    ("screening without harms", "screening-harms-unstated"),
    ("share with no number", "vague-quantifier"),
    ("causal verb on observational evidence", "causal-verb-on-observational"),
    ("absence of harm read as safety", "absence-of-harm-as-safety"),
]


# An empirical study that omits the guards the open-peer-review cohort asked for
# (38 PeerJ / F1000Research manuscripts, 608 referee objections).
OPEN_BAD = """Gut Bacteria and Blood Pressure in Adults
John Smith, Jane Doe
Department of Cardiology, Example University. Corresponding: js@example.edu

Abstract
""" + ("We measured the GBA index and SBP in adults using QIIME. " * 12) + """

Keywords
gut, blood pressure, adults, cross-sectional

Introduction
Blood pressure is common. Bacteria are common too. Many things are known.
""" + ("This paragraph describes the background of the problem at some length without any reference to the literature, which a referee will notice. " * 3) + """
""" + ("Another paragraph describes more background at length without any reference to the literature either, and it goes on for a while. " * 3) + """
""" + ("A third paragraph describes still more background at length without any reference to the literature, and it too goes on for a while. " * 3) + """

Methods
Adults were studied in a cross-sectional design. Participants completed a questionnaire.
Data were analysed in SPSS and QIIME. A t-test and a Kruskal-Wallis test were used.
Blood pressure is measured with a cuff. Samples are collected in tubes. Data are analyzed in R.
Sequencing of the 16S gene was performed. We used either DADA2 or Deblur for denoising.

Results
Bacteria were 2.5-fold higher in one group. The difference was significant (p = 0.07, a trend).
Values were 12.3456 and 13.4567 and 14.5678 and 15.6789 and 16.7890.
The OR was 1.40 (95% CI 0.90-2.10) so exposure was associated with higher pressure.
Ten comparisons gave p = 0.01, p = 0.02, p = 0.03, p = 0.04, p = 0.01, p = 0.02, p = 0.03, p = 0.04, p = 0.01, p = 0.02.

Discussion
""" + ("The effect of bacteria leads to higher pressure and this is what we found. " * 30) + """

Conclusions
The effect of bacteria causes higher pressure. These findings provide new insights and pave the way for future work.

Conflict of Interest
The authors declare no conflicts of interest.

Funding
This research received no specific funding.

References
1. Smith J, Doe A. A study of hearts. Cardiology Journal. 2019;10:1-5. doi:10.1000/abc123
"""

OPEN_EXPECT = [
    ("many p-values, no correction", "multiplicity-uncorrected"),
    ("Kruskal named, never reported", "test-named-not-reported"),
    ("p = 0.07 called a trend", "marginal-p-called-significant"),
    ("t-test with no normality check", "normality-unassessed"),
    ("over-precise decimals", "over-precise-decimals"),
    ("fold claim with no interval", "fold-claim-without-interval"),
    ("CI spanning 1 called an association", "ci-spans-null-called-association"),
    ("causal language in a cross-sectional study", "cross-sectional-causal-language"),
    ("software with no version", "software-without-version"),
    ("no data-collection period", "collection-period-unstated"),
    ("no sample-size statement", "sample-size-unjustified"),
    ("no eligibility criteria", "eligibility-criteria-absent"),
    ("16S data with no accession", "sequence-data-accession-absent"),
    ("'either … or' in the Methods", "either-or-in-methods"),
    ("no aim or hypothesis", "aim-or-hypothesis-absent"),
    ("uncited introduction paragraphs", "introduction-paragraphs-uncited"),
    ("conclusion boilerplate", "conclusion-boilerplate"),
    ("abbreviation in the abstract with no expansion", "abstract-abbreviation-undefined"),
    ("analysed/analyzed mixed", "spelling-variants-mixed"),
    ("present-tense Methods", "methods-present-tense"),
]


# A Hungarian cross-sectional questionnaire survey that omits every guard the
# cohort 7 referees asked for (codes G-R1..3; see
# skills/presubmit/references/reviewer-patterns.md). Invented throughout: topic,
# wording and numbers are synthetic. It is deliberately wordy:
# `is_hungarian` counts function words, so a four-sentence fixture is not
# recognised as Hungarian and the language-specific rules stay silent.
SURVEY_BAD = """Felnőttek ismeretei a napvédelemről – keresztmetszeti kérdőíves vizsgálat
Kiss Anna dr., Nagy Béla dr.
Példa Egyetem, Egészségtudományi Kar. Levelező szerző: kiss.anna@pelda.hu

Összefoglalás
Bevezetés: A nyári leégés gyakori, és a kimenetelt a megelőző viselkedés is befolyásolja.
Módszer: Keresztmetszeti kérdőíves vizsgálatot végeztünk, amelyben 127 felnőtt vett részt.
Eredmények: A válaszadók 52,4%-a számolt be korábbi ismeretekről.
Következtetés: A célzott lakossági tájékoztatás indokolt.

Summary
Introduction: Summer sunburn is common and the outcome depends on preventive behaviour.
Methods: A cross-sectional questionnaire survey was carried out among 127 adults.
Results: Overall, 54.4% of respondents reported previous knowledge.
Conclusion: Targeted public information is warranted.

Rövidítésjegyzék
UPF (ultraviolet protection factor) – ultraibolya-védelmi tényező
OR (odds ratio) – esélyhányados
q – FDR-korrigált p-érték

Bevezetés
A nyári leégés a lakosság nagy részét érinti, és az esetek mintegy 70%-a megelőzhető [1]. A szabadban dolgozók azért veszélyeztetettek, mert a munkakörnyezet és a szokások is meghatározók, ezért a családokra jelentős terhet okozva [1]. A hazai adatok szerint a leégés nagy része nyaraláskor történik, és a megelőzés összetett szemléletet igényel, amely nem csupán a fényvédő használatát jelenti [2]. Az ellátórendszerre szintén jelentős terhet okozva [2]. Bár a témáról több közlemény jelent meg, hazai adat alig áll rendelkezésre arról, hogy a felnőtt lakosság mit tud a teendőkről, és milyen forrásból tájékozódik [3]. A korábbi vizsgálatok azt mutatják, hogy a felnőttek ismeretei nem egységesek, és a tájékoztatás tartalma is eltérő, amely nehezíti az összehasonlítást. Fontos, hogy a tájékoztatás ne csak a kockázatokra terjedjen ki, hanem arra is, hogy mit kell tenni leégés után, és hogy mit nem szabad tenni. A szakirodalom szerint a megelőzés minősége nem független attól, hogy a felnőtt részt vett-e képzésen, vagy csak informális forrásból tájékozódott, amely különbség a gyakorlatban is megjelenik.

Módszer
Keresztmetszeti vizsgálatot végeztünk, amelyben a toborzás online, közösségi oldalakon történt, és az adatgyűjtés 2024. december 9. és 2025. január 17. között zajlott. A saját szerkesztésű, 18 tételes kérdőív nem esett át formális validáláson. A vizsgálatban 127 fő vett részt, és a válaszadási arány 100%-os volt. A folytonos változókat átlaggal és SD-vel jellemeztük, mert az eloszlás nem tért el a normálistól. A háziorvosi elérés prediktorait logisztikus regresszióval vizsgáltuk. A vizsgálat a helyi bizottság engedélye alapján zajlott, engedélyszáma: 41. A jelentés STROBE szerint készült.

Eredmények
A válaszadók többsége nő volt (115 fő; 90,6%), és a felsőfokú végzettségűek aránya 41,7% volt. A tudásindex mediánja 4 pont volt, amely nem különbözött a két csoport között. Leégésnél 27 fő ecetes borogatást jelölt, ami hibás. Kánikulában 41 fő déli napozást javasolna, ami szintén helytelen, és ezt a kérdőív nem különítette el. Részletek: 1. táblázat. Megoszlás: 2. táblázat. Tényezők: életkor. Kalapot senki. A háziorvost megjelölők aránya magasabb volt az idősebbek körében (OR = 2,31; 95% CI 1,18–5,02; p = 0,021).

1. ábra A leégés leggyakoribb életkora
2. ábra Az információforrások megoszlása
3. ábra A teendők forrásai
4. ábra A leégés helyszínei
5. ábra A családban előfordult esetek
6. ábra A tájékoztatás színterei
7. ábra A helyes teendőt megjelölők aránya
8. ábra A fényvédő használata
9. ábra A háziorvost megjelölők aránya alcsoportonként

Megbeszélés
A helyes teendők ismerete széles körű, de az ellenjavallt teendők elkerülése nem, és ez a különbség iskolázottság szerint is megmutatkozott (OR = 2,31; 95% CI 1,18–5,02; p = 0,021; q = 0,040). A háziorvosi elérés az idősebbek körében volt gyakoribb (OR = 2,12; 95% CI 1,09–4,37; p = 0,026; q = 0,040), amely összefüggés a többváltozós modellben is megmaradt. A minta összetétele miatt az eredmények óvatosan értelmezendők, mert a kitöltők nagy része nő volt. Eredményeink arra utalnak, hogy a hiányosság nem az ismeret hiánya, hanem az, hogy a téves hiedelmek tovább élnek, és ezek cáfolata nem történik meg sem a képzéseken, sem a mindennapi tájékoztatásban. Ez azért lényeges, mert a téves teendő nem semleges, hanem árt, és ezért a passzív tájékozódás nem elegendő. A részletes életkori bontás a kiegészítő anyagban olvasható. A nemzetközi összevetés a kiegészítő anyagban szerepel. A módszertani háttér a kiegészítő anyagban található.

Következtetések
A célzott tájékoztatásnak a téves hiedelmek cáfolatára kell irányulnia, és a háziorvosi rendelő ebben meghatározó szerepet tölt be. További kutatás javasolt nagyobb, reprezentatív mintán.

Érdekeltségek
A szerzőknek nincsenek érdekeltségeik.

Anyagi támogatás
A kutatás anyagi támogatásban nem részesült.

Irodalom
1. Kiss A, Nagy B. Napvédelem. Példa Folyóirat. 2023; 10: 1–5.
2. Nagy B, Kiss A. Megelőzés a gyakorlatban. Példa Szemle. 2022; 9: 11–15.
3. Tóth C. Lakossági ismeretek. Példa Lapok. 2023; 8: 21–26.
"""

SURVEY_EXPECT = [
    ("questionnaire not validated, content validity unmentioned", "instrument-validation-unexplained"),
    ("self-developed instrument, no domains described", "instrument-development-undescribed"),
    ("online recruitment with no platform or sampling method", "recruitment-undescribed"),
    ("100% response rate on an open link", "response-rate-without-denominator"),
    ("nine-tenths one sex, selection bias unnamed", "sample-skew-bias-unnamed"),
    ("fieldwork over the winter holidays", "fieldwork-over-holidays"),
    ("mean/SD promised, medians reported, no IQR", "descriptive-statistics-inconsistent"),
    ("regression with no covariate rule", "model-covariate-selection-unstated"),
    ("responses judged wrong with no guideline", "answer-key-unsourced"),
    ("Discussion re-reports the statistics", "discussion-restates-statistics"),
    ("Discussion sentences that only point at the supplement", "supplement-carries-discussion"),
    ("nine figures for a small sample", "figure-table-overload"),
    ("abbreviation listed but never used", "abbreviation-list-unused"),
    ("notation in the abbreviation list (q)", "abbreviation-list-non-abbreviation"),
    ("abbreviation used but not listed (STROBE)", "abbreviation-list-incomplete"),
    ("repeated unfinished sentence ending", "sentence-left-unfinished"),
    ("note-form sentences in the body", "telegraphic-sentences"),
    ("approval number with no year", "approval-number-without-year"),
    ("Hungarian and English abstracts differ in their numbers", "bilingual-abstract-mismatch"),
]


# Cohort 9 — a model evaluated only in simulation. Synthetic throughout.
SIM_BAD = """A Self-Learning AI-Driven Predictive Model of Example Disease Risk
Alex Roe, Kim Lee
Department of Medicine, Example University. Corresponding: ar@example.edu

Abstract
We present a self-learning risk model built as a Bayesian framework. The model reached an AUC of 0.91 and a likelihood ratio of 8.2. Parameters were entered into a Monte Carlo simulation, and the simulation produced repeated results on simulated cases. The simulated population was large.

Keywords: risk, model, example, simulation

Introduction
Example disease is under-recognised [1]. A risk model could help.

Methods
Parameters were entered into the framework. We ran a Monte Carlo simulation of 10,000 simulated cases and the simulation was repeated with a synthetic cohort. The within-person biological variation was taken from healthy volunteers.

Results
The model reached an AUC of 0.91 and a sensitivity of 0.88. The simulation showed a positive predictive value of 0.41. The loop confirms 6 of 14 markers. A run over 900 people confirms a gain of 3 points.

Discussion
The framework behaves as designed.

Conclusions
The model reached an AUC of 0.91.

Conflict of Interest
None declared.

Funding
None.

References
1. Author A. A title. Journal One. 2024;1:1-9. doi:10.1000/aaa111
"""

SIM_EXPECT = [
    ("simulated metric quoted unlabelled", "simulation-metric-unlabelled"),
    ("maturity vocabulary on an unvalidated model", "model-maturity-overclaimed"),
    ("no development cohort", "development-cohort-absent"),
    ("parameter from the wrong population", "parameter-population-mismatch"),
    ("borrowed parameter with no sensitivity analysis", "borrowed-parameter-no-sensitivity"),
    ("model output stated as fact", "projection-language-unmarked"),
]

_ENDNOTE_DOC = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:body>'
    '<w:p><w:r><w:t>Introduction</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>A cited claim.</w:t></w:r>'
    '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>1,3-4</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>References</w:t></w:r></w:p>'
    '<w:sdt><w:sdtContent>'
    '<w:p><w:r><w:t>1. Author A. Work one. Journal One. 2024;1:1-2.</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>2. Author B. Work two. Journal Two. 2024;2:3-4.</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>3. Author C. Work three. Journal Three. 2024;3:5-6.</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>4. Author D. Work four. Journal Four. 2024;4:7-8.</w:t></w:r></w:p>'
    '</w:sdtContent></w:sdt>'
    '</w:body></w:document>')


def _docx_endnote():
    """A .docx whose bibliography sits in a content control and whose citations
    are superscript runs: what a field-managed EndNote file looks like."""
    import zipfile
    p = Path(tempfile.mktemp(suffix=".docx"))
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels", _DOCX_RELS)
        z.writestr("word/document.xml", _ENDNOTE_DOC)
    return p


# Cohorts 10-13: a narrative review that pools its own numbers and omits the
# guards referees asked for. Synthetic throughout; no referee or manuscript text.
SYNTH_BAD = """Example Therapy and Example Outcomes in Older Adults: Where Next
Alex Roe, Kim Lee
Department of Medicine, Example University. Corresponding: ar@example.edu

Abstract
""" + ("This narrative review summarises example therapy and example outcomes in older adults. " * 8) + """

Keywords: therapy, outcome, adults, example

Introduction
""" + ("Example therapy matters for older adults and the question deserves a proper account here. " * 16) + """ [1]

Methods
This work used a non-systematic design with single-reviewer screening. Titles were screened by a large language model and data were extracted with a script. Only papers from journals with an impact factor above 3 were included. The 120 records gave 140 unique records after de-duplication. For cohorts, the published risk-of-bias judgements were mapped to the domains of the tool. Pooling required at least three studies. The outcome was taken as defined by the study. Estimates were pooled with DerSimonian-Laird random-effects meta-analysis, and risk ratios and odds ratios were pooled together. The latest measurement was used (post hoc). The main analysis was post hoc. A subgroup was post hoc. A further split was post hoc.

Results
Figure 3 shows the search. Figure 1 shows the flow and Figure 2 the trials. Two trials gave a pooled RR 0.71 (0.44-0.998). The pool of three cohorts had I2 = 61%, which reflects precision rather than real differences. Egger's test was non-significant (p = 0.27). The hazard ratio was 0.80 (0.70-0.92). Without them, the estimate was 0.86 (0.71-1.11). The dose-response curve showed a plateau beyond 420 minutes per week.
The cohort data show that therapy was protective at every age. In cohort analyses the observational estimate was beneficial for 12 groups and was protective in others.
Our model of 2,000 adults found 310 averted events and a break-even price, and QALYs rose by 2.
""" + "".join(f"The term x = log(a) + exp(b) = {i} applies.\n" for i in range(9)) + """

Discussion
""" + ("The findings are discussed at length here. " * 60) + """ The wrong question has been asked, and it is time to change it. The evidence is limited.

Conclusions
Regular review of every patient is mandatory.

Conflict of Interest
None declared.

Funding
None.

References
""" + "\n".join(f"{i}. Author A. A work number {i}. Journal Name. 2024;{i}:1-9. https://doi.org/10.3390/xxxxx" for i in range(1, 41))

SYNTH_EXPECT = [
    ("odds and risk ratios in one pool", "effect-measures-mixed"),
    ("high I2 put down to precision", "heterogeneity-unexplored"),
    ("non-significant Egger read alone", "egger-null-as-absence"),
    ("pooled estimate from two trials", "few-studies-pooled-unqualified"),
    ("DerSimonian-Laird on very few studies", "dl-estimator-few-studies"),
    ("meta-analysis inside a narrative review", "meta-in-narrative-unjustified"),
    ("outcomes as each study defined them", "outcome-definition-not-harmonised"),
    ("minimum study count with no source", "pooling-minimum-unsupported"),
    ("sensitivity result missing from the abstract", "fragile-result-not-in-abstract"),
    ("third decimal keeping the interval off 1", "ci-bound-false-precision"),
    ("post hoc rule behind the main analysis", "post-hoc-as-primary"),
    ("post hoc analyses unseparated in the abstract", "post-hoc-unseparated-in-abstract"),
    ("review not named in the title", "review-design-label-missing"),
    ("machine screening with no measured check", "extraction-pipeline-unvalidated"),
    ("human independence unstated", "ai-screening-independence-unstated"),
    ("risk of bias inherited from sources", "rob-inherited-from-sources"),
    ("single-reviewer screening not carried forward", "methods-limitation-not-carried"),
    ("narrative review with no standard", "narrative-standard-absent"),
    ("impact factor as eligibility", "impact-factor-eligibility"),
    ("more records after de-duplication", "dedup-count-impossible"),
    ("dose-response threshold with no derivation", "dose-response-threshold-underived"),
    ("evaluative words on observational data", "evaluative-word-on-observational"),
    ("economic model with no structure", "economic-model-unspecified"),
    ("mandate in the conclusions", "conclusion-mandate-language"),
    ("stock argumentative phrases", "rhetorical-register"),
    ("placeholder DOI", "placeholder-doi-or-url"),
    ("thin Introduction citations", "introduction-citation-sparse"),
    ("figures cited out of order", "display-items-out-of-order"),
    ("equations in the main text", "equation-dense-main-text"),
]

# what the first versions of these rules fired on, and must not fire on again
SYNTH_QUIET = [
    ("per-unit OR with three decimals on both limits", "ci-bound-false-precision",
     "Higher dose predicted the outcome (OR 1.052 per unit, 1.007-1.091) in this study."),
    ("a limit reported to two decimals", "ci-bound-false-precision",
     "Trials gave RR 0.71 (0.44-1.00) overall in this analysis of women."),
    ("an author verifying AI output is the guard", "extraction-pipeline-unvalidated",
     "Author A verified all AI-assisted search results, extracted values and citation checks."),
    ("odds ratios converted by a named method", "effect-measures-mixed",
     "Odds ratios were converted with the Zhang-Yu method, and risk ratios and odds ratios were combined."),
    ("a sentence denying the conversion", "effect-measures-mixed",
     "Risk ratios and odds ratios were never pooled together in any analysis."),
]


def _docx_bold():
    """Running text with bold emphasis in six paragraphs, plus a run-in heading."""
    import zipfile
    filler = "This sentence is ordinary running text that goes on for a while before anything happens. "
    paras = ['<w:p><w:r><w:t>Introduction</w:t></w:r></w:p>']
    for _ in range(6):
        paras.append(f'<w:p><w:r><w:t xml:space="preserve">{filler}</w:t></w:r>'
                     '<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">this matters most </w:t></w:r>'
                     f'<w:r><w:t>{filler}</w:t></w:r></w:p>')
    p = Path(tempfile.mktemp(suffix=".docx"))
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels", _DOCX_RELS)
        z.writestr("word/document.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   '<w:body>' + "".join(paras) + '</w:body></w:document>')
    return p


def _codes(text, profile_name="generic"):
    tmp = Path(tempfile.mktemp(suffix=".txt"))
    tmp.write_text(text, encoding="utf-8")
    doc = pc_extract.load(tmp)
    prof = pc_lib.load_profile(profile_name)
    findings = []
    for fn in C.ALL_CHECKS.values():
        findings.extend(fn(doc, prof))
    return findings


def _write(text):
    p = Path(tempfile.mktemp(suffix=".txt"))
    p.write_text(text, encoding="utf-8")
    return p


def _ok(name, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    return cond


def run():
    print("presubmit selftest")
    passed = True

    findings = _codes(BAD)
    codes = {f.code for f in findings}
    expect = [
        ("missing Methods section", "missing-section"),
        ("no corresponding email", "no-corresponding-email"),
        ("duplicate DOI", "ref-dup-doi"),
        ("duplicate reference text", "ref-duplicate"),
        ("reference without a year", "ref-no-year"),
        ("citation out of range [99]", "cite-out-of-range"),
        ("uncited reference", "ref-uncited"),
        ("repeated word", "repeated-word"),
        ("missing conflict-of-interest", "missing-conflict-of-interest"),
        ("missing funding", "missing-funding"),
    ]
    for label, code in expect:
        passed &= _ok(f"caught: {label}", code in codes)

    # sections detected correctly (title/authors NOT treated as sections)
    tmp = Path(tempfile.mktemp(suffix=".txt")); tmp.write_text(BAD)
    doc = pc_extract.load(tmp)
    order = doc.sections.get("_order", [])
    passed &= _ok(f"sections parsed = {order}",
                  "abstract" in order and "references" in order
                  and "a study of hearts in mice" not in order)
    passed &= _ok("author block kept in preamble (email check meaningful)",
                  "Example University" in doc.sections.get("_preamble", ""))

    # an en-dash range is a citation, not a gap: MDPI style writes [26–85]
    _t = Path(tempfile.mktemp(suffix=".txt"))
    _t.write_text("Introduction\nA claim [26\u201330] and another [4].\n\nReferences\n1. x\n")
    passed &= _ok("en-dash citation range expands",
                  C._cited_numbers(pc_extract.load(_t)) == {4, 26, 27, 28, 29, 30})

    # the reviewer rules must fire on a manuscript that omits their guards, or
    # the category is decorative
    rv = [f for f in _codes(BAD) if f.category == "reviewer"]
    passed &= _ok(f"reviewer rules fire on the flawed fixture "
                  f"({[f.code for f in rv]})", len(rv) >= 1)

    # the later cohorts: every rule that came from a referee's point must fire
    # on the fixture that omits its guard
    rcodes = {f.code for f in _codes(REVIEWER_BAD) if f.category == "reviewer"}
    for label, code in REVIEWER_EXPECT:
        passed &= _ok(f"reviewer caught: {label}", code in rcodes)

    # cohort 8 — the open-peer-review corpus
    ocodes = {f.code for f in _codes(OPEN_BAD) if f.category == "reviewer"}
    for label, code in OPEN_EXPECT:
        passed &= _ok(f"open-review caught: {label}", code in ocodes)

    # cohort 7: the survey-methods rules, on a manuscript that omits each guard
    scodes = {f.code for f in _codes(SURVEY_BAD) if f.category == "reviewer"}
    for label, code in SURVEY_EXPECT:
        passed &= _ok(f"survey caught: {label}", code in scodes)

    # cohorts 10-13
    ycodes = {f.code for f in _codes(SYNTH_BAD) if f.category == "reviewer"}
    for label, code in SYNTH_EXPECT:
        passed &= _ok(f"synthesis caught: {label}", code in ycodes)
    import pc_reviewer_synth as Y
    for label, code, sentence in SYNTH_QUIET:
        txt = ("Title of a Review on Example Outcomes Here\nAlex Roe\n\nAbstract\nAn abstract of a review.\n\n"
               "Methods\nRandom-effects meta-analysis was fitted using REML. " + sentence + "\n\nReferences\n1. A\n")
        passed &= _ok(f"synthesis quiet: {label}",
                      code not in {f.code for f in Y.check_synth(pc_extract.load(_write(txt)), {})})
    passed &= _ok("synthesis rules stay out of an ordinary primary study",
                  not ({c for _, c in SYNTH_EXPECT} - {"display-items-out-of-order"})
                  & {f.code for f in _codes(GOOD)})
    passed &= _ok("caught: bold emphasis inside running text",
                  "bold-emphasis-in-body" in {f.code for f in Y.check_synth(pc_extract.load(_docx_bold()), {})})
    passed &= _ok("synthesis abbreviation rule reads the main text only",
                  "abbreviation-before-definition" in {
                      f.code for f in Y.check_synth(pc_extract.load(_write(
                          "A Title of Sufficient Length for the Test\n\nIntroduction\n"
                          + "The BMI and the CRP were high in this group of people, as often. " * 30
                          + "Body mass index (BMI) and C-reactive protein (CRP) were then measured.\n"
                          )), {})})

    # GOOD manuscript: zero ERRORs
    gf = _codes(GOOD)
    errs = [f for f in gf if f.severity == pc_lib.ERROR]
    passed &= _ok(f"clean manuscript has no ERRORs (got {len(errs)}: "
                  f"{[f.code for f in errs]})", len(errs) == 0)

    # ---- what an editorial round teaches: opinion-format mistakes -----------
    of = _codes(OPINION, "annals")
    ocodes = {f.code for f in of}
    for label, code in [
        ("declared word count over the format limit", "declared-over-limit"),
        ("more references than the format allows", "too-many-references"),
        ("ethics block that belongs on the disclosure form", "discouraged-disclosure"),
        ("trial registration in the manuscript", "registration-in-text"),
        ("placeholder left in the text", "placeholder-left"),
        ("estimate without a confidence interval", "estimate-without-ci"),
        ("study named only by acronym", "acronym-study-undescribed"),
        ("same reference described twice", "duplicate-citation-description"),
        ("authors' own study in the closing", "own-study-in-conclusion"),
    ]:
        passed &= _ok(f"caught: {label}", code in ocodes)

    # the subgroup estimates, not the one that already carries its CI
    naked = {f.message for f in of if f.code == "estimate-without-ci"}
    passed &= _ok("CI check is parenthetical-level, not sentence-level",
                  any("2.13" in m for m in naked) and any("1.02" in m for m in naked)
                  and not any("0.74" in m for m in naked))

    # no abstract and no keywords is correct for this format, not an error
    passed &= _ok("opinion format is not asked for an abstract",
                  "no-abstract" not in ocodes and "no-keywords" not in ocodes)

    # ---- a .docx that still carries revisions and comments ------------------
    dp = _docx_with_revisions()
    import pc_docx
    facts = pc_docx.inspect(dp)
    passed &= _ok(f"docx revisions seen (ins={facts.insertions}, del={facts.deletions}, "
                  f"comments={facts.comments})",
                  facts.insertions == 1 and facts.deletions == 1 and facts.comments == 1
                  and facts.revision_authors == ["An Editor"])

    class _D:
        pass
    d = _D()
    d.path, d.text, d.paragraphs, d.sections = dp, "The dose was too high.", [], {}
    dcodes = {f.code for f in C.check_submission(d, pc_lib.load_profile("annals"))}
    passed &= _ok("caught: tracked changes left in the .docx",
                  "tracked-changes-left" in dcodes)
    passed &= _ok("caught: comments left in the .docx", "comments-left" in dcodes)

    # a title page that declares "References: 10" is not a References heading
    tmp2 = Path(tempfile.mktemp(suffix=".txt"))
    tmp2.write_text("Title Here\nWord Count: 900\nReferences: 3\n\nBody text here.\n\n"
                    "References\n1. Author A. Work. Journal. 2024;1:1-2.\n", encoding="utf-8")
    d2 = pc_extract.load(tmp2)
    passed &= _ok("title-page declaration is not read as a section heading",
                  len(C._reference_entries(d2)) == 1)

    # ---- the parts of each merged line that had no test of their own --------
    # cohort 9: the simulation-only rules, gated, on a fixture that omits each guard
    mcodes = {f.code for f in _codes(SIM_BAD) if f.category == "reviewer"}
    for label, code in SIM_EXPECT:
        passed &= _ok(f"simulation caught: {label}", code in mcodes)
    passed &= _ok("simulation rules stay silent on an ordinary study",
                  not ({c for _, c in SIM_EXPECT} & {f.code for f in _codes(OPEN_BAD)}))

    # EndNote: bibliography in <w:sdt>, citations as superscript runs
    ep = _docx_endnote()
    ed = pc_extract.load(ep)
    passed &= _ok("EndNote bibliography inside a content control is read",
                  len(C._reference_entries(ed)) == 4)
    passed &= _ok(f"superscript citations harvested with ranges ({sorted(ed.sup_citations)})",
                  C._cited_numbers(ed) == {1, 3, 4})
    passed &= _ok("uncited reference found through superscripts",
                  "ref-uncited" in {f.code for f in C.check_references(ed, pc_lib.load_profile("generic"))})
    passed &= _ok("the .docx path and the citations both reach the Document",
                  ed.path == ep and ed.source == "docx")

    # an inline Kulcsszavak line counts, and a profile that needs no keywords stays quiet
    tk = Path(tempfile.mktemp(suffix=".txt"))
    tk.write_text("Cím\nÖsszefoglalás\nRövid szöveg.\nKulcsszavak: egy, kettő, három\n\n"
                  "Bevezetés\nSzöveg.\n", encoding="utf-8")
    kd = pc_extract.load(tk)
    passed &= _ok("inline Hungarian keyword line is found",
                  "no-keywords" not in {f.code for f in C.check_abstract(kd, pc_lib.load_profile("generic"))})
    passed &= _ok("orvosi-hetilap profile loads",
                  bool(pc_lib.load_profile("orvosi-hetilap").get("name")))

    # journal blacklist: offline, on a fixture list
    import journal_blacklist as jbl
    bl = jbl.Blacklist({"journals": [{"title": "Journal of Example Fraud", "issn": ["12345678"],
                                      "nlm_abbr": ["J Ex Fraud"]}]})
    passed &= _ok("blacklist: ISSN hit is BLOCKED",
                  bl.check_issns(["12345678"])[0] == "BLOCKED")
    passed &= _ok("blacklist: an unrelated title is OK",
                  bl.check_title("Journal of Honest Work")[0] == "OK")

    # --online: parsing and the reporting path, with the network stubbed out
    import pc_online
    import pc as pc_cli
    passed &= _ok("online: AMA citation parsed",
                  (pc_online.parse_citation("Roe A, Lee K. A title. Journal of Examples. "
                                            "2024;12(3):101-110.") or ("",))[0] == "Journal of Examples")
    real_check = pc_online.check
    try:
        pc_online.check = lambda entries: ([(1, "retraction", "Retracted.", "PMID 1")], None)
        rcodes2 = {f.code for f in pc_cli._online_findings(pc_extract.load(_write(BAD)))}
        pc_online.check = lambda entries: ([], "no network")
        scodes2 = {f.code for f in pc_cli._online_findings(pc_extract.load(_write(BAD)))}
    finally:
        pc_online.check = real_check
    passed &= _ok("online: a retraction is reported", "reference-retraction" in rcodes2)
    passed &= _ok("online: a failed lookup says so rather than reporting clean",
                  "online-check-skipped" in scodes2)

    print(f"\n{'ALL PASSED' if passed else 'FAILURES PRESENT'}")
    return passed


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
