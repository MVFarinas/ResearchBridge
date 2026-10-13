# Recorded PMC and ESearch responses: attribution and provenance

Responses recorded on 2026-10-13 for the ingestion tests, so that no test needs the network.
`manifest.json` lists the exact source URL and SHA-256 of every file; `tests/test_fixtures.py`
checks them. Files are byte-for-byte as served.

**NLM acknowledgement.** Listings, metadata and the article XML below come from the NIH National
Library of Medicine (NLM) PubMed Central Article Datasets on AWS
(<https://registry.opendata.aws/ncbi-pmc/>, bucket `pmc-oa-opendata`), accessed 2026-10-13. Their
use here does not imply NLM endorsement. ESearch responses come from NCBI E-utilities.

| File | What | Licence |
|---|---|---|
| `PMC*-listing.xml` | ListObjectsV2 responses: the version prefixes of one article. | Bucket listing (factual; no article content). |
| `PMC10718527.1.json`, `PMC7853715.1.json`, `PMC7781593.1.json` | Metadata of three eLife articles whose PMC XML is already a verbatim fixture in `libs/rbcore/tests/fixtures/jats/` (the tests reuse those files; their MD5 matches the `md5` in this metadata). | Article metadata; the articles are CC BY 4.0 (attribution in the rbcore fixtures README). |
| `PMC11964404.1.json`, `PMC11964404.1.xml` | Laine C, Babski D, Bachelet VC, et al. "Predatory journals: What can we do to protect their prey?" *PLOS Medicine* 2025;22(4):e1004542. doi:[10.1371/journal.pmed.1004542](https://doi.org/10.1371/journal.pmed.1004542). © 2025 Laine et al. The PMC copy of a PLOS article (the route PLOS papers take into the corpus). | **CC BY 4.0**, <https://creativecommons.org/licenses/by/4.0/>. Redistributed unchanged as test data. |
| `PMC13641010.1.json` | Metadata of an NIH author manuscript with `license_code` `TDM`. **Only the metadata is recorded**: the article itself is not openly licensed, and the pipeline never downloads it. | Article metadata only (NLM). |
| `esearch-hypertension-2024-cc-by.json` | An ESearch response (five PMC IDs and a count). | NCBI E-utilities response (identifiers only). |

Synthetic variations used by the tests (for example a retracted flag, a second version, or an
invented permissions block) are built in the test code and named as synthetic there; none is
presented as real data.
