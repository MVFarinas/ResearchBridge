# Precision of in-text definition detection

**Status: PROVISIONAL.** Definition detection (`rbscores.burden.definitions`) removes a term the
text explains from the prior-knowledge burden score. A false definition therefore hides a real
term from the score and from the ranked-term list, so its precision matters more than its
recall. This note records a hand-labelled precision check made in review fix round 1
(finding C-C1). Recall has not been measured.

## Method

**What counts as correct.** A detection is correct when the text, at that place, tells the
reader what the recorded term is or means: an abbreviation's expansion, a synonym, a
description ("a coprophilous fungus"), or the thing it names. Only the term matters to the
score; a correct term with a badly cut explanation (for example "suggested" for "bZIP
proteins") counts as correct, and the table shows the explanation as recorded. A detection is
wrong when the term is not explained there: a stock parenthetical, a list item, a field label,
the reverse direction of a gloss, or a misparse.

**Samples.** One labeller (the agent that made the fix) labelled every detection in each sample.
There was no second labeller, so no agreement figure exists.

1. **Committed JATS fixtures, before the fix:** all 85 detections in four CC BY fixtures under
   `libs/rbcore/tests/fixtures/jats/` (`elife-61907`, `elife-65180` and `elife-93719` from PMC,
   and `plos-pmed-1004542`; the Europe PMC duplicate of `elife-93719` was left out). Every
   detection is in an abstract or body paragraph, none in a figure caption.
2. **Same fixtures, after the fix:** all 37 detections. These texts were inspected while the
   fix was developed, so this figure is optimistic.
3. **Held-out sample, after the fix:** validation 1's abstracts and lay summaries
   (BioLaySumm 2025 eLife and PLOS validation splits; see
   [validation_1.md](validation_1.md)). While developing the fix, 80 pairs drawn with
   `random.Random(20261013).sample(pairs, 80)` were inspected. After the last change to the
   code, 120 *other* pairs were drawn with `random.Random(4242)`, all 411 detections in them
   collected, and 50 sampled with the same generator. Nothing was changed after labelling them.

## Results

| Sample | Detections labelled | Correct | Precision (95% Wilson CI) |
|---|---|---|---|
| Fixtures, before the fix | 85 (all) | 36 | 42.4% (32.4-53.0) |
| Fixtures, after the fix (inspected during the fix) | 37 (all) | 31 | 83.8% (68.9-92.3) |
| **Held-out validation-split sample, after the fix** | **50** | **44** | **88.0% (76.2-94.4)** |

Before the fix, by kind on the fixtures: gloss 9 of 39 correct, appositive 7 of 18, copular 4 of
10, naming 9 of 9, abbreviation 7 of 9. Glosses and appositives were the main source of error.

In the held-out sample, abbreviations (Schwartz-Hearst) were 28 of 29 correct and the other kinds
16 of 21 (76%). Parenthetical glosses remain the weakest: 2 of 6 correct. The remaining errors
are a parenthetical that names a category rather than explains ("excitatory (NKB)"), list
items ("grooming sequences, or other behaviors"), and misparses.

The fixtures, after the fix, still show two known kinds of error: a field label after a list
item ("plastic synapses (neuroscience)") and a gloss read in the wrong direction ("a different
shape (membrane remodelling)").

## What changed

Before the fix, stock parentheticals ("data not shown", "arrows", "Methods", "wild type",
"two-tailed t-test"), comma lists of names, proper names and clauses were recorded as
definitions. The fix (`burden/definitions.py`, `burden/abbreviations.py`, `burden/references.py`):

- requires both sides of a gloss or appositive to be noun phrases;
- rejects explanations that are stock phrases, statistics, numbers, lists or proper names alone;
- rejects parentheticals that open like a clause ("which ...", "but not ...", "as ...", "e.g.");
- requires appositive sides to be adjacent and outside any coordinated list;
- accepts a main-clause copular definition only with a relative or participle clause, and never
  a negated or modal one;
- ignores Schwartz-Hearst "short forms" inside citations ("(Pavlov, 1927)");
- requires the short form in the "SF (long form)" order to look like an abbreviation.

The regression cases are parametrised in `scores/tests/test_definitions.py` and
`scores/tests/test_abbreviations.py`.

## Effect on validation 1

Re-running validation 1 with the fix changed the burden results only slightly (pooled, full
texts: 75.1% to 75.2%; length-matched: 82.3% to 82.6%). Ignoring definitions is still equal or
better on every group (length-matched pooled 85.1% vs 82.6%, exact McNemar p < 0.001). That test
cannot reward definition detection: abstracts define about as many terms as lay summaries,
mostly abbreviations, and the genre label says nothing about whether a defined term costs a
reader anything. The "terms I don't know" study (docs/data-formats/) is the test that can.

## Labelled detections

### Held-out sample (after the fix)

| # | Pair | Kind | Term | Explanation recorded | Correct |
|---|---|---|---|---|---|
| 1 | `plos-validation-1308` (abstract) | abbreviation | tkv | thickveins | yes |
| 2 | `plos-validation-1328` (lay) | abbreviation | CDT | Cytolethal Distending Toxin | yes |
| 3 | `plos-validation-799` (lay) | abbreviation | IFN | interferon | yes |
| 4 | `plos-validation-673` (lay) | abbreviation | Type II | (Type I) and interference-insensitive | no |
| 5 | `plos-validation-865` (lay) | appositive | vasoconstriction | the other blood volume | no |
| 6 | `plos-validation-766` (abstract) | gloss | H1–H16 | sixteen distinct subtypes | yes |
| 7 | `plos-validation-924` (abstract) | gloss | 2nd | wound closure | no |
| 8 | `plos-validation-657` (lay) | appositive | ciliopathies | a group of diseases caused by dysfunctional cilia | yes |
| 9 | `plos-validation-301` (lay) | copular | DNA methylation | an important chromatin modification that prevents the expression and … | yes |
| 10 | `plos-validation-1203` (lay) | abbreviation | DALY | Disability Adjusted Life Year | yes |
| 11 | `plos-validation-589` (abstract) | gloss | brucei vs T. b. rhodesiense | subspecies designation | no |
| 12 | `plos-validation-589` (abstract) | abbreviation | Tbr | T. b. rhodesiense | yes |
| 13 | `plos-validation-842` (lay) | abbreviation | PGCs | primordial germ cells | yes |
| 14 | `plos-validation-347` (abstract) | abbreviation | ESD | environmental sex determination | yes |
| 15 | `plos-validation-238` (lay) | appositive | Ae. aegypti | The primary dengue vector | yes |
| 16 | `plos-validation-94` (abstract) | abbreviation | Ov | Onchocerca volvulus | yes |
| 17 | `plos-validation-477` (lay) | naming | demyelination | the progressive disruption | yes |
| 18 | `plos-validation-269` (abstract) | abbreviation | SSD | ‘sterol-sensing domain’ | yes |
| 19 | `plos-validation-1065` (abstract) | abbreviation | CAS | castanospermine | yes |
| 20 | `plos-validation-799` (lay) | abbreviation | EC | Elite controllers | yes |
| 21 | `plos-validation-94` (lay) | abbreviation | LIPS | luciferase immunoprecipitation systems | yes |
| 22 | `plos-validation-516` (lay) | abbreviation | IDPs | Intrinsically disordered proteins | yes |
| 23 | `elife-validation-52` (lay) | naming | nodule | an organ | yes |
| 24 | `plos-validation-477` (abstract) | abbreviation | Mrs2 | MRS2 magnesium homeostasis factor (Saccharomyces cerevisiae) | yes |
| 25 | `elife-validation-218` (lay) | naming | bZIP63 | a bZIP protein | yes |
| 26 | `elife-validation-218` (lay) | naming | bZIP proteins | suggested | yes |
| 27 | `plos-validation-662` (abstract) | appositive | Borrelia burgdorferi | the etiologic agent of Lyme disease | yes |
| 28 | `plos-validation-40` (abstract) | abbreviation | HPV | human PV | yes |
| 29 | `elife-validation-8` (lay) | gloss | grooming sequences | other behaviors that involve a sequence of tasks | no |
| 30 | `elife-validation-131` (lay) | naming | amidation | peptide modification | yes |
| 31 | `plos-validation-1195` (lay) | naming | dengue hemorrhagic fever | the severe manifestations | yes |
| 32 | `plos-validation-413` (abstract) | abbreviation | RNA-seq | RNA sequencing | yes |
| 33 | `elife-validation-52` (abstract) | appositive | Lotus japonicus | the legume | yes |
| 34 | `plos-validation-1044` (lay) | abbreviation | DRE | DNA Replication–related Element | yes |
| 35 | `plos-validation-842` (lay) | abbreviation | Hmgcr | 3-Hydroxy-3-Methylglutaryl Coenzyme A reductase | yes |
| 36 | `plos-validation-1000` (abstract) | copular | tsutsugamushi | an obligate intracellular bacterium that mainly infects endothelial c… | yes |
| 37 | `plos-validation-197` (lay) | abbreviation | RDTs | rapid diagnostic tests | yes |
| 38 | `plos-validation-222` (lay) | abbreviation | HY5 | HYPOCOTYL 5 | yes |
| 39 | `plos-validation-94` (abstract) | abbreviation | Ll | Loa loa | yes |
| 40 | `plos-validation-94` (abstract) | gloss | QLIPS | format | yes |
| 41 | `plos-validation-197` (lay) | abbreviation | HAT | human African trypanosomiasis | yes |
| 42 | `plos-validation-154` (lay) | abbreviation | LRV | Leishmania RNA Virus | yes |
| 43 | `plos-validation-781` (abstract) | abbreviation | NMDA | N-methyl-D-aspartic acid | yes |
| 44 | `plos-validation-862` (abstract) | abbreviation | TALEs | transcription activator-like effectors | yes |
| 45 | `plos-validation-222` (abstract) | abbreviation | HYH | HY5 HOMOLOG | yes |
| 46 | `elife-validation-52` (lay) | naming | NFR1 | chemical signals | yes |
| 47 | `plos-validation-831` (abstract) | abbreviation | PCECV | purified chick-embryo cell rabies vaccine | yes |
| 48 | `elife-validation-180` (abstract) | gloss | NKB | excitatory | no |
| 49 | `plos-validation-117` (abstract) | appositive | CDR3 | the hypervariable region | yes |
| 50 | `plos-validation-477` (abstract) | abbreviation | CNS | central nervous system | yes |

### Committed fixtures (after the fix)

| # | Fixture | Kind | Term | Explanation recorded | Correct |
|---|---|---|---|---|---|
| 1 | `elife-61907-pmc-s3` | copular | Gelber | a remarkable scientist whose absence from the historical record testi… | yes |
| 2 | `elife-61907-pmc-s3` | naming | Hebbian synapse | A plastic synapse | yes |
| 3 | `elife-61907-pmc-s3` | gloss | connectionism | connections | no |
| 4 | `elife-61907-pmc-s3` | gloss | synapses | neuroscience | no |
| 5 | `elife-61907-pmc-s3` | naming | computational theory | The information-processing tradition in cognitive science, sometimes … | yes |
| 6 | `elife-61907-pmc-s3` | abbreviation | CR | conditioned response | yes |
| 7 | `elife-61907-pmc-s3` | copular | Loeb | a behaviorist in his sympathies | yes |
| 8 | `elife-61907-pmc-s3` | gloss | Paramecia | another ciliate | yes |
| 9 | `elife-61907-pmc-s3` | appositive | Roland Clark Davis | a leading proponent of ‘psychophysiology’, which sought to establish … | yes |
| 10 | `elife-61907-pmc-s3` | gloss | conjugation | sexual reproduction | yes |
| 11 | `elife-61907-pmc-s3` | gloss | engram | the memory trace | yes |
| 12 | `elife-61907-pmc-s3` | naming | reminiscence | a phenomenon | yes |
| 13 | `elife-61907-pmc-s3` | appositive | Jensen | another psychologist working with Paramecia | yes |
| 14 | `elife-61907-pmc-s3` | gloss | CS | the wire | no |
| 15 | `elife-61907-pmc-s3` | naming | biopsychology | behavioral problems | yes |
| 16 | `elife-61907-pmc-s3` | gloss | cellula | the small rooms | yes |
| 17 | `elife-65180-pmc-s3` | gloss | autoimmune inflammatory disorders | the hygiene hypothesis | no |
| 18 | `elife-65180-pmc-s3` | naming | inflammaging | the sterile, aging-associated inflammation | yes |
| 19 | `elife-65180-pmc-s3` | abbreviation | COPD | chronic obstructive pulmonary disease | yes |
| 20 | `elife-65180-pmc-s3` | appositive | dysbiosis | an imbalance in the composition of the intestinal microbiome | yes |
| 21 | `elife-65180-pmc-s3` | abbreviation | MS | multiple sclerosis | yes |
| 22 | `elife-65180-pmc-s3` | gloss | anthropophilic helminths | only true old friends | no |
| 23 | `elife-65180-pmc-s3` | abbreviation | CRP | C-reactive protein | yes |
| 24 | `elife-65180-pmc-s3` | appositive | Heligmosomoides polygyrus | the intestinal murine roundworm | yes |
| 25 | `elife-65180-pmc-s3` | appositive | Nippostrongylus brasiliensis | a gastrointestinal roundworm of rodents | yes |
| 26 | `elife-65180-pmc-s3` | abbreviation | CIA | collagen-induced arthritis | yes |
| 27 | `elife-65180-pmc-s3` | gloss | Opisthorchis felineus | cat liver fluke | yes |
| 28 | `elife-93719-pmc-s3` | naming | MreB | a protein | yes |
| 29 | `elife-93719-pmc-s3` | abbreviation | ATP | adenosine triphosphate | yes |
| 30 | `elife-93719-pmc-s3` | abbreviation | ADP | adenosine di-phosphate | yes |
| 31 | `elife-93719-pmc-s3` | naming | hydrolysis | a chemical reaction | yes |
| 32 | `elife-93719-pmc-s3` | naming | treadmilling | This process is also known as treadmilling, as the molecules lost at … | yes |
| 33 | `elife-93719-pmc-s3` | appositive | Geobacillus | the bacterium | yes |
| 34 | `elife-93719-pmc-s3` | naming | Spiroplasma | another bacterium | yes |
| 35 | `elife-93719-pmc-s3` | gloss | remodelling | a different shape | no |
| 36 | `plos-pmed-1004542` | abbreviation | ICMJE | International Committee of Medical Journal Editors | yes |
| 37 | `plos-pmed-1004542` | abbreviation | NIH | National Institutes of Health | yes |

## Attribution

The fixture texts are CC BY articles from eLife and PLOS Medicine; see
`libs/rbcore/tests/fixtures/jats/README.md`. The held-out texts are from PLOS and eLife research
articles (CC BY 4.0), via T. Goldsack, Z. Zhang, C. Lin and C. Scarton, "Making Science Simple:
Corpora for the Lay Summarisation of Scientific Literature", EMNLP 2022, as redistributed for the
BioLaySumm 2025 shared task. Only the short term and explanation strings above are quoted.
