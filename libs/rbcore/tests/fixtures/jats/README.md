# JATS test fixtures: attribution and provenance

Real JATS XML files used by the rbcore tests. Each file is an unmodified copy of an open-access
article distributed under the **Creative Commons Attribution 4.0 International licence (CC BY
4.0)**, <https://creativecommons.org/licenses/by/4.0/>. They are redistributed here, unchanged,
as test data. `manifest.json` records the exact source URL and SHA-256 of each file, and a test
checks that the files still match. Retrieved 2026-10-13.

PMC Cloud Service copies come from the `pmc-oa-opendata` bucket of the US National Library of
Medicine (NLM). We acknowledge NLM as the source of those files; this use does not imply NLM
endorsement. The PMC `license_code` for every PMC copy below is `CC BY`.

| File | Article | Source | Why it is here |
|---|---|---|---|
| `elife-93719-pmc-s3.xml` | Bapat M, Pande V, Gayathri P. "Getting bacterial cells into shape." *eLife* 2023;12:e93719. doi:[10.7554/eLife.93719](https://doi.org/10.7554/eLife.93719). © 2023, Bapat et al. | PMC Cloud Service (PMC10718527.1) | Short eLife Insight; licence as `ali:license_ref`; COI footnote. |
| `elife-93719-europepmc.xml` | The same article. | Europe PMC `fullTextXML` | Europe PMC's copy has **only `license-p` prose** (no machine-readable licence) and moves back matter into the body: the real-world fail-closed case. |
| `elife-65180-pmc-s3.xml` | Zhang B, Gems D. "Gross ways to live long: Parasitic worms as an anti-inflammaging therapy?" *eLife* 2021;10:e65180. doi:[10.7554/eLife.65180](https://doi.org/10.7554/eLife.65180). © 2021, Zhang and Gems. | PMC Cloud Service (PMC7853715.1) | Figure 1 carries **three permissions blocks of its own**, one per reproduced panel: CC BY-NC 4.0 for panel 1a (top), and two copyright-only blocks ("not covered by the CC-BY 4.0 licence") for panels 1a (bottom) and 1b, inside a CC BY article; funding awards. |
| `elife-61907-pmc-s3.xml` | Gershman SJ, Balbi PEM, Gallistel CR, Gunawardena J. "Reconsidering the evidence for learning in single cells." *eLife* 2021;10:e61907. doi:[10.7554/eLife.61907](https://doi.org/10.7554/eLife.61907). © 2021, Gershman et al. | PMC Cloud Service (PMC7781593.1) | Figure 1 carries its **own permissions block with only prose** ("not covered by the CC-BY 4.0 licence"): the figure must fail closed. Also has a table. |
| `plos-pmed-1004542.xml` | Laine C, Babski D, Bachelet VC, et al. "Predatory journals: What can we do to protect their prey?" *PLOS Medicine* 2025;22(4):e1004542. doi:[10.1371/journal.pmed.1004542](https://doi.org/10.1371/journal.pmed.1004542). © 2025 Laine et al. | PLOS (publisher JATS) | Publisher-native PLOS JATS: licence as `license/@xlink:href`, external DTD reference, `fn-type="conflict"`, funding statement, body paragraphs before the first section. |

Note on `elife-61907-pmc-s3.xml`: its Figure 1 image (© 1960, USA TODAY NETWORK) is **not**
covered by the article's CC BY licence. Only the XML text is included here, never the image.

Synthetic snippets used by the tests are written inline in the test files and named as
synthetic there; none of them is presented as a real article.
