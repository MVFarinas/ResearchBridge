# Recorded metadata responses: attribution and provenance

Real responses recorded on 2026-10-13 for the metadata, search, lookup and credibility tests, so
that no test needs the network. `manifest.json` lists each file's exact request URL and SHA-256;
`tests/test_metadata_fixtures.py` checks them. Files are byte-for-byte as served, except where the
manifest says `modified`. Requests carried the neutral ResearchBridge User-Agent, no API key and no
personal identifier.

| Files | Source and terms |
|---|---|
| `openalex-*.json` | [OpenAlex](https://openalex.org/) API. OpenAlex data is released under **CC0**. One work by DOI for the PLOS Medicine paper also used in `../pmc/` (doi:10.1371/journal.pmed.1004542), one for a retracted Lancet paper (doi:10.1016/S0140-6736(97)11096-0, metadata only), and one keyless search for "predatory journals" (10 results). |
| `icite-40173335.json` | [NIH iCite](https://icite.od.nih.gov/) API for PMID 40173335 (the same PLOS Medicine paper). iCite data is in the **public domain** (NIH Open Citation Collection). |
| `crossref-*.json` | [Crossref](https://www.crossref.org/) REST API work records: open metadata, including Retraction Watch data (Retraction Watch Database, The Center for Scientific Integrity, distributed by Crossref). `crossref-10.1159-000494475.json` had its `abstract` removed (the abstract text belongs to its authors); see the manifest. The other two records had no abstract. |
| `idconv-*.json` | NCBI [PMC ID Converter](https://pmc.ncbi.nlm.nih.gov/tools/idconv/) responses (identifiers only). |

Only metadata is recorded here: no article text from the Lancet or Karger papers, which are not
openly licensed. Synthetic variations used by the tests (error statuses, a one-result search
wrapper, altered payloads) are built in the test code and named as synthetic there.
