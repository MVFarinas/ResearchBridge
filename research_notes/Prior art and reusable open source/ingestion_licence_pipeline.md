# Ingestion and licence pipeline: open full-text sources, licence metadata, and reusable parsers (status as of 2026-10-13)

Method note: Many findings below come from live API calls I made on 2026-10-13 (arXiv OAI-PMH and Atom API, PMC Cloud S3 bucket, Europe PMC REST, OpenAlex, bioRxiv API, DOAJ API, Crossref, PLOS Solr, GitHub and Hugging Face APIs). For those, the cited URL is the exact endpoint queried, so the report writer can reproduce them. Counts change daily.

## 1. Licence metadata per source (arXiv, PMC, PLOS, DOAJ, Europe PMC, Crossref, Unpaywall/OpenAlex, bioRxiv/medRxiv)

### Takeaway
The best machine-readable per-paper licences are in the **PMC Cloud Service JSON** (`license_code`), the **Europe PMC REST `license` field**, the **arXiv OAI-PMH `arXiv` metadata format** (`<license>` URI), and the **bioRxiv/medRxiv API** (`license` field). The arXiv Atom search API does **not** expose licence at all. DOAJ gives licence only at journal level. Crossref, Unpaywall and OpenAlex are useful cross-checks but are aggregators with inclusive definitions of "open". PMC retired its FTP service, OA Web Service API and legacy file lists (oa_comm/oa_noncomm/oa_other) in the week of 24 August 2026. The only bulk route now is the per-article AWS S3 bucket.

### Cited Findings

**arXiv**
- Submitters choose one of six licences: CC BY 4.0, CC BY-SA 4.0, CC BY-NC-SA 4.0, CC BY-NC-ND 4.0, the arXiv.org perpetual non-exclusive licence 1.0, or CC0. The choice is irrevocable. arXiv **metadata** is CC0. — [arXiv licence help](https://info.arxiv.org/help/license/index.html)
- The non-exclusive licence gives arXiv limited distribution rights and "limits re-use of any type from other entities or individuals". — [arXiv licence help](https://info.arxiv.org/help/license/index.html)
- arXiv API Terms of Use say e-print redistribution "requires permission from the copyright holder". Most e-prints use the non-exclusive licence, and only a small subset carry licences that permit redistribution. Users must not "Store and serve arXiv e-prints (PDFs, source files, or other content) from your servers" unless the licence or the rights holder permits it. arXiv encourages linking to the abstract page instead. — [arXiv API Terms of Use](https://info.arxiv.org/help/api/tou.html)
- The OAI-PMH `arXiv` metadata format carries the licence as a URI in `<license>`. arXiv's own help says that for default-licence papers "it is necessary to obtain permission from the article authors before the article may be copied to another repository." — [arXiv OAI help](https://info.arxiv.org/help/oa)
- **Verified live:** `GetRecord` for 2310.06825 with `metadataPrefix=arXiv` returned `<license>http://creativecommons.org/licenses/by/4.0/</license>` at both `oaipmh.arxiv.org/oai` and `export.arxiv.org/oai2`. — [arXiv OAI-PMH endpoint](https://oaipmh.arxiv.org/oai?verb=GetRecord&identifier=oai:arXiv.org:2310.06825&metadataPrefix=arXiv)
- **Verified live:** the Atom API response for the same paper contains no licence or rights element. — [arXiv API query](https://export.arxiv.org/api/query?id_list=2310.06825)

**PubMed Central (PMC)**
- Timeline from the NLM Technical Bulletin, posted 17 February 2026:
  - **Early Feb 2026:** NLM began updating the PMC Cloud Service.
  - **March 2026:** FTP datasets moved to a new location.
  - **August 2026:** "you will need to access full text article data files through the PMC Cloud Service". The FTP article datasets, the **PMC OA Web Service API**, and the legacy Cloud files are removed.
  - The new structure has "no compressed packages or bulk packages". Cloud XML matches the OAI-PMH and E-utilities eFetch XML. — [NLM Tech Bulletin, Changes to PMC Article Dataset Distribution Services 2026](https://www.nlm.nih.gov/pubs/techbull/jf26/jf26_Changes_to_PMC_ArtDsDistribServs_2026.html)
- Legacy files were moved under `deprecated/` paths on 13 April 2026. A 30 July 2026 update said they would be unavailable on or after 24 August. — [PMC FTP Service page](https://pmc.ncbi.nlm.nih.gov/tools/ftp/) (via search summary)
- The PMC Cloud page notice dated 26 August 2026 says the changes are complete and "legacy files on the FTP and Cloud Services were removed the week of August 24, 2026". It also says a CSV inventory is updated daily and kept for 30 days. — [PMC Cloud Service](https://pmc.ncbi.nlm.nih.gov/tools/cloud/)
- Automated retrieval is allowed only via the Cloud Service, PMC OAI-PMH, E-utilities and the BioC API. Bulk retrieval by any other automated means is prohibited. — [PMC Open Access Subset page](https://pmc.ncbi.nlm.nih.gov/tools/openftlist/)
- The new bucket is `s3://pmc-oa-opendata` (us-east-1, world-readable, no login), with about 8 million article versions under prefixes like `PMC13901.1/`. Each version has `.xml` (JATS), `.txt` (extracted from the XML), `.json` metadata, and, "when permissible by the publishers' licenses", a PDF, images and supplementary files. — [PMC Cloud README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)
- The JSON metadata fields are `pmcid`, `version`, `pmid`, `doi`, `title`, `citation`, `is_pmc_openaccess`, `is_manuscript`, `is_historical_ocr`, `is_retracted`, `license_code`, `xml_url`, `pdf_url`, `media_urls` and `text_url`. — [PMC Cloud README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)
  - `license_code` either "corresponds to the Creative Commons license codes" or is **`TDM`** for author manuscripts. `TDM` means the text may be text-mined and used consistent with fair use; it is **not** a reuse licence. — same source
  - **Verified live:** the sample record `PMC10000000.1.json` has `"license_code": "CC0"` and `"is_pmc_openaccess": true`. — [sample JSON](https://pmc-oa-opendata.s3.amazonaws.com/PMC10000000.1/PMC10000000.1.json)
- Bucket terms of use (from the README):
  - Users must acknowledge NLM and must not use the PMC logo or wordmark or imply NLM endorsement.
  - Redistributors must "only distribute data that are licensed for redistribution".
  - Redistributors must "maintain the most current version of all distributed data", or clearly state that their product does not reflect the most current data. — [PMC Cloud README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)
- Legacy OA-subset groupings, as described in a search summary of the openftlist page:
  - **Commercial use allowed:** CC0, CC BY, CC BY-SA, CC BY-ND.
  - **Non-commercial:** CC BY-NC variants.
  - **"Other":** no machine-readable CC licence, no licence, or a custom licence.
  
  These groupings belonged to the now-removed file lists. The current openftlist page (last modified 24 Aug 2026) no longer describes them and just says "License terms vary. Please refer to the license statement in each article". — [PMC OA Subset page](https://pmc.ncbi.nlm.nih.gov/tools/openftlist)

**Europe PMC**
- The REST `search` endpoint with `resultType=core` returns a per-record `license` field (for example `'cc by'`), plus `isOpenAccess` and `inEPMC`. Search supports a `LICENSE:"cc by"` filter. — [Europe PMC REST search, verified with PMCID:PMC10009416](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PMCID:PMC10009416&format=json&resultType=core)
- Full-text JATS is available per article from the `/{PMCID}/fullTextXML` endpoint. **Verified live:** for PMC10009416 the XML has a `<license>` element with `<license-p>` text but no `xlink:href` or `ali:license_ref` attribute. The machine-readable licence had to come from the search API field, not from the XML. — [Europe PMC fullTextXML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10009416/fullTextXML)

**PLOS**
- PLOS content is licensed "in accordance with the Creative Commons Attribution (CC BY) license or other comparable license that allows free and unrestricted use (such as ... CC0 ... or Open Governmental License)". This applies "Unless otherwise indicated" and also covers peer reviews. — [PLOS Terms of Use](https://plos.org/terms-of-use/)
- DOAJ's journal record for PLoS ONE shows licence `CC BY` 4.0 with the author retaining copyright. — [DOAJ journal API](https://doaj.org/api/search/journals/bibjson.title:plos?pageSize=1)

**DOAJ**
- **Verified live:** DOAJ article records have `bibjson.license: null` in the sampled article, which came from MDPI's *Cells*. Article records carry a full-text link to the publisher's HTML (`content_type: text/html`), not the text itself. Journal records carry structured licence flags (`BY`, `NC`, `ND`, `SA`, `type`, `url`) and copyright info. — [DOAJ article API](https://doaj.org/api/search/articles/bibjson.title:cancer?pageSize=1); [DOAJ journal API](https://doaj.org/api/search/journals/bibjson.title:plos?pageSize=1)

**Crossref**
- **Verified live:** Crossref `license` is an array of `{URL, start, content-version, delay-in-days}`. For example, PLOS DOI 10.1371/journal.pone.0000217 has `http://creativecommons.org/licenses/by/4.0/` with content-version `unspecified`. — [Crossref works API](https://api.crossref.org/works/10.1371/journal.pone.0000217)
- 84,689,284 Crossref works have `has-license:true`. — [Crossref API filter](https://api.crossref.org/works?filter=has-license:true&rows=0)

**OpenAlex / Unpaywall**
- OpenAlex "errs toward inclusiveness" and treats even restrictive licences such as CC BY-NC-ND as open. Users who need stricter standards must filter on the licence value. When a repository supplies no licence metadata, Unpaywall falls back to parsing licence statements from full text, which is less accurate. — [OpenAlex help: What is an OA license](https://help.openalex.org/hc/en-us/articles/41193820509079-What-is-an-OA-license); [OpenAlex docs: open access](https://help.openalex.org/data/works/open-access.md) (via search summary)
- OpenAlex introduced API keys and usage-based pricing on 13 Feb 2026:
  - Daily allowance is about $0.10 without a key and $1 with a free key.
  - Single-record lookups are free. List/filter calls cost $0.0001, search calls $0.001, and full-text PDF/XML downloads $0.01 each.
  - A CASRAI article says keys are now mandatory, which conflicts with the official docs. — [OpenAlex authentication docs](https://developers.openalex.org/api-reference/authentication); [CASRAI news](https://casrai.org/news/openalex-api-keys-mandatory-usage-based-pricing-2026)
  - **Verified live:** API responses now include a `cost_usd` field (0.0001 for a group_by call). — [OpenAlex API](https://api.openalex.org/works?filter=primary_location.source.id:S4306400194&group_by=primary_location.license)
- No published accuracy audit of the Unpaywall/OpenAlex licence field turned up. A 2026 chemistry-corpus study (Lit2Vec) harmonised licences from Crossref, Unpaywall and OpenAlex. All three agreed on 62.6% of records, and it reported no licence conflicts under its rule. — [Lit2Vec, arXiv 2604.12498](https://arxiv.org/pdf/2604.12498) (via search summary)

**bioRxiv / medRxiv**
- Licence options are CC BY, CC BY-NC, CC BY-ND, CC BY-NC-ND, CC0, and "no reuse". By posting, authors "explicitly consent to text mining of their work". — [bioRxiv About](https://www.biorxiv.org/about-biorxiv)
- **Verified live:** the API `details` endpoint returns a per-preprint `license` field with values `cc_by`, `cc_by_nc`, `cc_by_nd`, `cc_by_nc_nd`, `cc0`, `cc0_ng` and `cc_no`. — [bioRxiv API](https://api.biorxiv.org/details/biorxiv/2025-09-01/2025-09-10/0)

### Inferences
- **ResearchBridge licence mapping:**
  - Use arXiv OAI-PMH (`metadataPrefix=arXiv`) or the bulk metadata as the licence source of truth. Never use the Atom API for this.
  - Treat `arxiv.org/licenses/nonexclusive-distrib/1.0/` as "never ingest", the same as all-rights-reserved.
  - Map PMC `license_code=TDM` and bioRxiv `cc_no` to "never ingest".
  - Map `CC BY-ND`, `CC BY-NC-ND` and arXiv `CC BY-NC-ND 4.0` to display-only.
- **PMC "commercial use allowed" is not the same as "derivative-permitting".** PMC's legacy commercial bucket included CC BY-ND, so ResearchBridge needs its own per-licence gate rather than PMC's subset grouping.
- **For PMC, the authoritative licence field is now `license_code`** in the Cloud JSON. Any pipeline or library built around `oa_file_list.csv`, `oa_comm`/`oa_noncomm` tarballs or the OA Web Service (`oa.fcgi`) is broken as of late August 2026. This likely affects older tutorials and libraries, but I did not verify which ones.
- **DOAJ is a discovery layer, not a full-text or article-licence source.** Article licences have to be inferred from the journal licence or fetched from the publisher, PMC or Europe PMC.
- **Use Crossref, OpenAlex and Unpaywall only as secondary signals** or for discovery. Licence URLs there can describe publisher TDM licences or "unspecified" content versions. Gate on the licence that ships with the full text: PMC JSON, Europe PMC, arXiv OAI or bioRxiv API.

### Gaps
- I could not confirm the arXiv native-HTML launch date or conversion success rate from arXiv's page, which gives no dates or rates.
- I did not verify whether medRxiv's licence options are identical to bioRxiv's. The API shares the same structure (`api.biorxiv.org/details/medrxiv/...`) but I didn't sample medRxiv.
- I did not verify whether the full list of PMC `license_code` values includes non-CC codes beyond `TDM`, for example a code for "other" or custom licences. A full pass over the metadata inventory would answer this.
- I could not confirm whether an arXiv paper's licence can differ between versions. arXiv says the licence is irrevocable, but per-version licence fields in OAI were not tested.

## 2. Approximate counts of derivative-permitting (CC BY / CC BY-SA / CC0) papers per source

### Takeaway
As of October 2026:
- **Europe PMC / PMC:** roughly **5.4 million** full-text OA articles under CC BY/CC BY-SA/CC0, versus about 2.4 million under NC or ND licences.
- **arXiv:** only an estimated **~0.2–0.3 million** papers are CC BY/BY-SA/CC0. The large majority use the non-exclusive licence.
- **bioRxiv:** only about **30%** of recent preprints are CC BY/CC0.
- **PLOS:** essentially all of the roughly 0.3–0.4 million documents are CC BY.

### Cited Findings
- **Europe PMC** (queried 2026-10-13; filter `OPEN_ACCESS:y AND IN_EPMC:y AND HAS_FT:y`, full text held by Europe PMC). — [Europe PMC REST search](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=LICENSE:%22cc%20by%22%20AND%20OPEN_ACCESS:y%20AND%20IN_EPMC:y%20AND%20HAS_FT:y&format=json&pageSize=1)

  | Licence | Full-text OA articles |
  |---|---|
  | CC BY | 5,336,633 |
  | CC BY-SA | 3,512 |
  | CC0 | 60,833 |
  | CC BY-ND | 13,140 |
  | CC BY-NC | 1,013,707 |
  | CC BY-NC-ND | 1,101,782 |
  | CC BY-NC-SA | 298,802 |

  - Total `OPEN_ACCESS:y` = 8,311,361. `IN_PMC:y` = 12,038,547, of which 8,235,275 are open access.
  - Without the full-text filter, `LICENSE:"cc by"` = 6,538,249, including 656,343 preprint records (`SRC:PPR`). Only 76,397 preprint records have full text in Europe PMC.
- **PMC Cloud:** about 8 million article versions, including author manuscripts and historical OCR. This is not limited to CC licences. — [PMC Cloud README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)
- **arXiv via OpenAlex** (source S4306400194, queried 2026-10-13): 1,382,627 works have arXiv as primary location, with licences as follows. The remaining ~1.12M have no licence value, which is consistent with the non-exclusive licence. — [OpenAlex group_by](https://api.openalex.org/works?filter=primary_location.source.id:S4306400194&group_by=primary_location.license)

  | Licence | Works |
  |---|---|
  | CC BY | 198,653 |
  | CC BY-NC-ND | 25,637 |
  | CC BY-NC-SA | 18,936 |
  | CC BY-SA | 9,504 |
  | CC0 | 7,584 |
  | "other OA" | 3,355 |
  | CC BY-NC | 271 |
  | CC BY-ND | 26 |

- arXiv itself describes its corpus as "over 2 million papers". — [arXiv accessible HTML page](https://info.arxiv.org/about/accessible_HTML.html)
- **Common Pile v0.1** `arxiv_papers_filtered` has **304,048** arXiv documents (about 29.3B tokens) under CC BY, CC BY-SA or CC0. The card warns that licensing metadata can be wrong. — [Common Pile arXiv dataset card](https://huggingface.co/datasets/common-pile/arxiv_papers_filtered/blob/refs%2Fpr%2F1/README.md); [Common Pile paper, arXiv 2506.05209](https://arxiv.org/pdf/2506.05209)
- **bioRxiv sample** (my sample of 2,007 preprints posted 1–10 Sep 2025, via the API). — [bioRxiv API](https://api.biorxiv.org/details/biorxiv/2025-09-01/2025-09-10/0)

  | Licence | Preprints | Share |
  |---|---|---|
  | cc_by_nc_nd | 591 | 29.4% |
  | cc_by | 567 | 28.3% |
  | cc_no (no reuse) | 492 | 24.5% |
  | cc_by_nc | 242 | 12.1% |
  | cc_by_nd | 70 | 3.5% |
  | cc0 | 23 | 1.1% |
  | cc0_ng | 22 | 1.1% |

- **PLOS:** the Solr search API returns `numFound` 417,786 for `doc_type:full`, which may include non-research article types. — [PLOS search API](https://api.plos.org/search?q=doc_type:full&rows=0&wt=json)
  - This conflicts with a Europe PMC query, `PUBLISHER:"Public Library of Science" AND OPEN_ACCESS:y`, which returned only 121,956. The PUBLISHER field likely undercounts. — [Europe PMC REST](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PUBLISHER:%22Public%20Library%20of%20Science%22%20AND%20OPEN_ACCESS:y&format=json&pageSize=1)
- **All article-type works in OpenAlex** by `best_oa_location.license`. — [OpenAlex group_by](https://api.openalex.org/works?filter=type:article&group_by=best_oa_location.license)

  | Licence | Works |
  |---|---|
  | CC BY | 18,536,384 |
  | CC BY-NC-ND | 7,262,835 |
  | CC BY-NC | 4,831,762 |
  | CC BY-SA | 2,915,823 |
  | other OA | 2,355,597 |
  | CC BY-NC-SA | 2,311,119 |
  | CC0 | 1,170,377 |
  | CC BY-ND | 253,235 |

- **Historical context:** OASPA (2022) reported CC BY on almost 81% of articles in fully OA journals and around 60% in hybrid journals. — [OASPA](https://www.oaspa.org/?p=4459)

### Inferences
- **PMC/Europe PMC is by far the largest derivative-permitting source with clean XML.** About 5.4M CC BY/BY-SA/CC0 articles means roughly two-thirds of its OA full text supports both display and rewrite.
- **arXiv's derivative-permitting share is small**, roughly 10–15% of the corpus: about 0.2–0.3M of more than 2M papers. Most arXiv papers would be excluded under ResearchBridge's rule.
- **bioRxiv** yields only about 30% rewrite-eligible preprints (cc_by plus cc0) and about 33% display-only (ND variants). Roughly 25% must never be ingested.
- **Europe PMC's `CC BY-SA` count looks implausibly low** (3.5k) relative to OpenAlex's 2.9M. OpenAlex's count is across all publishers, including non-biomedical repositories, so the two are not comparable. Some Europe PMC records may store SA under a different string.

### Gaps
- There is no official arXiv licence breakdown. The OpenAlex figure covers only about 1.38M arXiv works, fewer than arXiv's own total of over 2M. An exact count needs the arXiv bulk metadata (Kaggle snapshot or a full OAI-PMH harvest), which I did not download.
- I did not compute a PMC Cloud `license_code` distribution. It requires the roughly 8M-row inventory plus JSON fetches.
- I found no DOAJ per-article licence counts, because article-level licence is mostly null.

## 3. Full-text formats: which give clean structured text without PDF parsing

### Takeaway
**PMC/Europe PMC JATS XML** and **PLOS JATS XML** are the cleanest: native sections, paragraphs, figures with captions, references and licence elements. For arXiv, **native arXiv HTML (LaTeXML)** is now available even for older papers, and **ar5iv** remains online. Both give structured HTML from LaTeX source, though conversion quality varies. bioRxiv and DOAJ-listed journals usually need either publisher HTML/XML or PDF parsing.

### Cited Findings
- **PMC Cloud:**
  - Per-article NISO JATS XML, a plain-text rendering derived from the XML, JSON metadata, and PDF, images and supplements when licences permit.
  - There are no bulk tarballs any more, so files must be fetched per object. The S3 inventory is daily and kept 30 days.
  - Sample command: `curl "https://pmc-oa-opendata.s3.amazonaws.com/PMC10009402.1/PMC10009402.1.xml"`. — [PMC Cloud README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)
- **Europe PMC:** per-article JATS via the `/{PMCID}/fullTextXML` endpoint (verified for PMC10009416). — [Europe PMC fullTextXML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10009416/fullTextXML)
- **PLOS:** the `allofplos` tool (MIT, last pushed 2026-09-09) downloads "a larger than 7 Gb zip file (allofplos.zip) with all the XML files inside" and needs at least 30 GB of disk. — [PLOS/allofplos GitHub](https://github.com/PLOS/allofplos)
- **arXiv HTML:**
  - arXiv offers HTML alongside PDF in a beta, and is "gradually backfilling HTML for arXiv's corpus".
  - "a small percentage of papers will not have an HTML version". About 90% of submissions are TeX/LaTeX.
  - Layout differs from the PDF by design. — [arXiv accessible HTML](https://info.arxiv.org/about/accessible_HTML.html)
- **Verified live:** `arxiv.org/html/{id}` returned HTTP 200 for 2310.06825, 2401.00001 and 1706.03762 (a 2017 paper, so it was backfilled). The page carries LaTeXML generator markers (`ltx_document` classes and a comment "LaTeXML oxide (version 0.7.6)"). ar5iv (`ar5iv.labs.arxiv.org/html/1706.03762`) also returned 200, and `ar5iv.org` redirects there. — [arXiv HTML 1706.03762](https://arxiv.org/html/1706.03762); [ar5iv 1706.03762](https://ar5iv.labs.arxiv.org/html/1706.03762)
- **arXiv bulk source and PDFs:**
  - Available on S3 in **requester-pays** buckets in us-east-1: "The complete set of files as of April 2025 is about 9.2 TB", growing about 100 GB/month.
  - PDFs come in roughly 500 MB tar chunks. — [arXiv bulk data on S3](https://info.arxiv.org/help/bulk_data_s3.html)
- **arXiv API rate limit:** legacy APIs (OAI-PMH, RSS, arXiv API) allow at most 1 request every 3 seconds on a single connection, combined across all machines. — [arXiv API ToU](https://info.arxiv.org/help/api/tou.html)

### Inferences
- **ResearchBridge's preferred format path:**
  1. PMC/Europe PMC JATS for biomedical content.
  2. PLOS JATS (via allofplos or PMC, since PLOS is also deposited in PMC).
  3. arXiv native HTML (`arxiv.org/html/{id}v{n}`) for CC BY/CC BY-SA/CC0 arXiv papers.
  4. LaTeXML run locally on arXiv source as a fallback.
  5. PDF parsing (GROBID, Docling or MinerU) only for bioRxiv, medRxiv and DOAJ journals without XML.
- **Even CC-licensed arXiv papers are bounded by the 1 request per 3 seconds limit.** For scale, the requester-pays S3 source bundle plus local LaTeXML is the realistic path.

### Gaps
- I found no official arXiv statistic on the HTML conversion failure rate, and no official date when HTML became default or the backfill finished.
- bioRxiv has a full-text JATS/S3 requester-pays bulk feed. I know of it, but did not verify it in this session.

## 4. Open-source parsers: licences (code vs weights), quality, and maintenance (2025–2026)

### Takeaway
For a commercial product, the safest permissively licensed stack is:
- **GROBID** (Apache-2.0, active) for scholarly PDF to TEI, with sections and references.
- **Docling** (MIT code, Apache-2.0 for its Heron layout and Granite-Docling models, very active) for general layout.
- **LaTeXML** (public domain) and **ar5iv** (MIT) for arXiv LaTeX.
- **pubmed_parser** (MIT) for JATS.

Avoid or check carefully before using these:
- **Nougat:** weights CC-BY-NC, and the repository is dormant.
- **Marker/Surya:** code is now Apache-2.0, but the weights are under modified OpenRAIL-M, free only for orgs under $5M funding/revenue.
- **MinerU:** code is under a custom "Apache-2.0 + conditions" licence with an attribution obligation for online services. The HF card for its MinerU2.5 VLM is tagged AGPL-3.0.
- **CERMINE:** AGPL-3.0, dormant.

### Cited Findings
All repository data comes from the GitHub API on 2026-10-13: `license.spdx_id`, `pushed_at`, `releases/latest` and README licence sections.

**Actively maintained**

- **GROBID** (repo now `grobidOrg/grobid`; `kermitt2/grobid` redirects)
  - Code: Apache-2.0. Not archived. Last push 2026-10-12. Latest release 0.9.1 on 2026-08-04. — [GROBID GitHub](https://github.com/grobidOrg/grobid)
  - A Sep 2026 paper proposes layout-guided masking for GROBID in large-scale scientific PDF ingestion. It describes GROBID as a font-stream tool, not a full-page parser, so it has no OmniDocBench score. — [arXiv 2609.26381](https://arxiv.org/pdf/2609.26381) (via search summary)
- **Marker** (`datalab-to/marker`)
  - Code: "Our code is licensed under **Apache 2.0** — free to use, including commercially."
  - Weights: "a modified AI Pubs Open Rail-M license (free for research, personal use, and startups under $5M funding/revenue)". Commercial use beyond that requires a paid licence.
  - Latest release v2.0.0 on 2026-07-20; last push 2026-10-02. — [Marker README](https://github.com/datalab-to/marker)
- **Surya** (OCR/layout used by Marker)
  - Code: Apache-2.0. Weights under the same modified OpenRAIL-M terms.
  - Latest release v0.22.1 on 2026-07-20. — [Surya README](https://github.com/datalab-to/surya)
- **Docling** (`docling-project/docling`)
  - Code: MIT. "For individual model usage, please refer to the model licenses found in the original packages."
  - Hosted by the LF AI & Data Foundation.
  - Latest release v2.138.0 on 2026-10-12. — [Docling README](https://github.com/docling-project/docling)
  - Models: `docling-project/docling-layout-heron` and `ibm-granite/granite-docling-258M` are both tagged `apache-2.0` on Hugging Face. — [HF heron](https://huggingface.co/docling-project/docling-layout-heron); [HF granite-docling](https://huggingface.co/ibm-granite/granite-docling-258M)
- **MinerU** (`opendatalab/MinerU`)
  - Code: the "MinerU Open Source License", which is Apache-2.0 plus conditions:
    - A separate commercial licence is required if the user and its affiliates exceed **100M MAU or USD 20M monthly revenue**.
    - Online services must "clearly and prominently indicate" that MinerU is used.
    - Non-compliance means automatic termination.
  - Latest release 4.0.12 on 2026-10-11. — [MinerU LICENSE.md](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)
  - Weights: the `opendatalab/MinerU2.5-2509-1.2B` HF model is tagged `agpl-3.0`. — [HF MinerU2.5](https://huggingface.co/opendatalab/MinerU2.5-2509-1.2B)
- **olmOCR** (AllenAI)
  - Code: Apache-2.0. Latest release v0.4.27 on 2026-03-12.
  - Weights: `allenai/olmOCR-2-7B-1025` is tagged `apache-2.0`. — [olmOCR GitHub](https://github.com/allenai/olmocr); [HF olmOCR-2](https://huggingface.co/allenai/olmOCR-2-7B-1025)
- **Unstructured**: Apache-2.0. Release 0.27.25 on 2026-10-10. — [Unstructured GitHub](https://github.com/Unstructured-IO/unstructured)
- **LaTeXML**
  - Public domain: "developed at the National Institute of Standards and Technology ... not subject to copyright protection in the U.S.", with a CC0-equivalent waiver elsewhere.
  - Last push 2026-09-20. Last tagged release v0.8.8 on 2024-02-26. — [LaTeXML LICENSE](https://github.com/brucemiller/LaTeXML)
- **ar5iv** (`dginev/ar5iv`): MIT. Last push 2026-10-13. Last release 0.2.3 in 2023. — [ar5iv GitHub](https://github.com/dginev/ar5iv)
- **pubmed_parser**: MIT. Last push 2025-07-31. Latest release 0.5 on 2024-08-12. — [pubmed_parser GitHub](https://github.com/titipata/pubmed_parser)

**Dormant**

- **Nougat** (Meta)
  - Code: MIT. "Nougat model weights are licensed under CC-BY-NC." The HF model `facebook/nougat-base` is tagged `cc-by-nc-4.0`.
  - Last push 2025-02-21. Only release 0.1.0-base, from 2023-08-22. — [Nougat README](https://github.com/facebookresearch/nougat); [HF nougat-base](https://huggingface.co/facebook/nougat-base)
- **PaperMage**: Apache-2.0. Last push 2024-11-08. Last release v0.18.0 in 2024-03. — [PaperMage GitHub](https://github.com/allenai/papermage)
- **s2orc-doc2json**: Apache-2.0. Last push 2024-04-11. No releases. — [s2orc-doc2json GitHub](https://github.com/allenai/s2orc-doc2json)
- **Science Parse**: Apache-2.0. Last release v2.0.3 in 2018. Last push 2024-05. — [Science Parse GitHub](https://github.com/allenai/science-parse)
- **CERMINE**: AGPL-3.0. Last release 1.13 in 2017. Last push 2022-06. — [CERMINE GitHub](https://github.com/CeON/CERMINE)

**Benchmarks**

- On OmniDocBench v1.5, MinerU 2.5 scores 90.67 and olmOCR 81.79. These numbers are reproduced from the original reports or leaderboard in arXiv 2609.26381. — [arXiv 2609.26381](https://arxiv.org/pdf/2609.26381) (via search summary)
- OmniDocBench (CVPR 2025) covers nine document types, including academic papers. — [OmniDocBench paper](https://arxiv.org/html/2412.07626v2)
- PaddleOCR-VL reports 80.0 ± 1.0 on olmOCR-Bench. — [PaddleOCR-VL, arXiv 2510.14528](https://arxiv.org/pdf/2510.14528)
- An olmOCR-bench comparison reported in secondary coverage of Datalab's own release gave Marker 2 76.0% overall, MinerU pipeline 72.7% and Docling 50.3%. These are **vendor-reported, unverified** numbers, and the MinerU VLM backend was excluded. — [secondary coverage](https://gmagazine.it.com/?p=566); treat with caution.
- In one study on OmniDocBench v1.0 pages, MinerU processed 1,354 pages with 1 failure and Docling 1,342 pages with 13 failures. — [Evidence Units, arXiv 2604.00500](https://arxiv.org/pdf/2604.00500) (via search summary)

### Inferences
- **Marker appears to have relicensed its code** from GPL-3.0, as I recall it from earlier versions, to Apache-2.0. The model-weight restriction is what matters for a commercial ResearchBridge. Above $5M funding or revenue it needs a paid licence. Treat Marker as a "startup-phase only" option.
- **MinerU's attribution clause binds ResearchBridge if it runs MinerU server-side.** Its AGPL-tagged VLM weights could trigger source-disclosure obligations for a network service. Both issues need legal review before adoption.
- **For the primary pipeline, PDF parsing should be a fallback.** JATS from PMC/Europe PMC/PLOS and LaTeXML HTML from arXiv cover the largest CC BY pools without ML models.
  - GROBID (Apache-2.0) is the most mature permissive choice for scholarly PDFs, with citations and sections as TEI.
  - Docling and olmOCR are permissive options with layout and figure handling.
- **Nougat should not be used** in a commercial product, because its weights are NC.

### Gaps
- I could not verify the licences of GROBID's bundled deep-learning models (DeLFT) separately from the code. They are assumed to be Apache-2.0 but are unconfirmed.
- Docling's TableFormer model licence is unverified. The HF id `ds4sd/docling-models` returned an error, so it may have moved.
- I found no independent, same-harness benchmark comparing GROBID, Docling, Marker, MinerU and olmOCR specifically on scientific papers.
- I found no confirmation of when Marker switched code licence.

## 5. Existing open corpora with licence-filtered full text, and whether they can be used in a product

### Takeaway
Several corpora are usable as accelerators, but **the dataset licence (e.g. ODC-BY) covers the database, not the copyright in each paper**. ResearchBridge must still carry and gate on per-paper licences.
- **S2ORC/s2orc_v2** (ODC-By): requires a Semantic Scholar API key under an agreement that AI2 can terminate at any time and that bans redistribution of the API.
- **peS2o** (ODC-By): mixed licences.
- **Common Pile:** pre-filtered to CC BY/BY-SA/CC0, but warns about licence errors.
- **unarXive:** the full set is restricted, the open subset is permissive.
- **CORE:** recent dumps require a paid licence and its terms are under review.

The PMC Cloud bucket itself is the cleanest bulk "dataset", with a per-article `license_code`.

### Cited Findings
- **Semantic Scholar datasets** (release 2026-10-06):
  - `s2orc` is "Full-body paper text parsed from open-access PDFs ... 10M records". `s2orc_v2` is "16M records".
  - "Downloading the full data requires an API key". Licensing is per dataset README. — [S2 Datasets API, latest release](https://api.semanticscholar.org/datasets/v1/release/latest)
- **S2ORC licence:** "released under the ODC-By 1.0". The original files are no longer downloadable, and S2ORC is now offered via the S2 API. — [allenai/s2orc GitHub](https://www.github.com/allenai/s2orc)
- **Semantic Scholar API License Agreement** (updated 17 May 2023):
  - S2 data is governed by accompanying licences "such as" CC BY-NC or ODC-BY.
  - Licensees may not "repackage, sell, rent, lease, lend, distribute, or sublicense the API".
  - Attribution to "Semantic Scholar" is required.
  - Use "may be terminated by AI2 any time for any reason". — [S2 API License](https://www.semanticscholar.org/product/api/license)
- **peS2o:** HF dataset tagged `license:odc-by`. — [HF allenai/peS2o](https://huggingface.co/datasets/allenai/peS2o)
  - The Common Pile's peS2o-derived subset holds about 6.3M S2ORC papers filtered to CC BY, CC BY-SA, CC0 or public domain. — [Common Pile paper](https://arxiv.org/pdf/2506.05209) (via search summary)
- **Common Pile arXiv:** 304,048 CC BY/BY-SA/CC0 papers. The card warns some documents may carry an incorrect licence. — [HF common-pile/arxiv_papers_filtered](https://huggingface.co/datasets/common-pile/arxiv_papers_filtered/blob/refs%2Fpr%2F1/README.md)
- **unarXive 2022/2023:**
  - Split into an **open subset** from permissively licensed papers and a **full set** that includes non-exclusive-licence papers. The full set is available only via restricted Zenodo access.
  - Code is MIT. Users must ensure compliance with each paper's licence. — [unarXive 2022 paper](https://arxiv.org/pdf/2303.14957); [Zenodo record](https://zenodo.org/record/7752754)
- **unarXive 2024:** covers arXiv Jan 1991 to Dec 2024, over 2.28M documents. Repository `faerber-lab/UnarXive-2024` is MIT for code, last pushed 2026-06-17. The data licence is not stated in the sources I found. — [ACL Anthology listing](https://aclanthology.org/people/ines-besrour/unverified/); GitHub API
- **CORE:**
  - The licence covers only CORE's sui generis database rights and CORE-generated information. It gives no rights in the underlying works.
  - Older dumps are free under ODC-By. Recent datasets require a purchased licence.
  - CORE is reviewing its framework, with plans to make metadata CC0/ODC-0 and offer full text only under conditional TDM access. — [CORE Terms](https://core.ac.uk/terms); [CORE Dataset](https://core.ac.uk/services/dataset)
- **PMC Cloud:** about 8M article versions, with per-version `license_code`, `is_pmc_openaccess`, `is_manuscript` and `is_retracted`. Redistributors must redistribute only licensed data and keep it current. — [PMC Cloud README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)

### Inferences
- **S2ORC/s2orc_v2 can be used, but with care.** They are parsed from PDFs, so they are lower fidelity than JATS. Access depends on a revocable API agreement. Per-paper licence still has to be obtained, from OpenAlex/Unpaywall or the source, and checked against the ResearchBridge gate.
- **PMC Cloud plus arXiv OAI-PMH covers most of what peS2o/S2ORC offer for biomedicine and arXiv**, with better provenance. Building directly from primary sources is preferable to depending on S2.
- **Common Pile is useful** as a pre-filtered list of CC-licensed arXiv IDs to bootstrap from. Re-verify each licence against arXiv OAI before ingestion.
- **CORE** is not suitable for a commercial full-text product without a negotiated licence.

### Gaps
- I could not read the per-dataset README for `s2orc`/`s2orc_v2` because it needs an API key. I could not confirm whether these records include a per-paper licence field, or whether S2 restricts commercial use of s2orc specifically.
- The OpenAlex snapshot data licence (believed to be CC0) and the snapshot's current access terms after the 2026 pricing change were not verified in this session.
- The unarXive 2024 data licence is not verified.

## 6. Gotchas: licence ambiguity, publisher restrictions, API terms

### Takeaway
The main traps are:
- Figures and tables under licences different from the article.
- Human-readable `<license-p>` text being the only licence in some JATS files.
- PMC `TDM` author manuscripts and bioRxiv `cc_no` looking "open".
- Aggregators (OpenAlex) counting NC-ND as open.
- arXiv's ban on storing and serving non-exclusive-licence e-prints.
- PMC's "keep current" and retraction obligations.
- Revocable or terms-heavy APIs: Semantic Scholar, OpenAlex's new pricing, arXiv's 3-second rule.

### Cited Findings
- **Figures may carry their own licence.** JATS4R permissions guidance says that when a CC BY article contains a figure reproduced under another licence, "That figure must then contain a separate permissions element". Objects without one inherit the article licence. — [JATS4R permissions](https://jats4r.niso.org/permissions/)
- **`<license-p>` and copyright statements are "intended for display purposes only"**, and links in `license-p` should be ignored by automated processes. The machine-readable licence belongs in `license/@xlink:href` or `ali:license_ref`. — [JATS4R permissions v1](https://jats4r.niso.org/permissions-v1/)
- **Verified live:** a Europe PMC JATS file (PMC10009416) had `<license>` with only `<license-p>`, and no machine-readable reference. — [Europe PMC fullTextXML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10009416/fullTextXML)
- **PMC media restrictions.** PDFs, media and supplementary materials are not provided for non-CC author manuscripts. `license_code=TDM` means mining and fair use only. — [PMC Cloud](https://pmc.ncbi.nlm.nih.gov/tools/cloud/); [PMC Cloud README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)
- **PMC terms:** acknowledge NLM, no implied endorsement, redistribute only licensed data, and keep data current. The `is_retracted` flag exists. — [PMC Cloud README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)
- **Earlier reuse attempts hit inconsistent licences.** A JATS-Con 2013 paper on reusing PMC OA-subset media for Wikimedia Commons found mixed licences and inconsistent XML were barriers to automated reuse at scale. — [NCBI Bookshelf JATS-Con paper](https://ncbi.nlm.nih.gov/books/NBK159964)
- **arXiv:**
  - No storing or serving of e-prints unless the licence permits.
  - Rate limit 1 request per 3 s, aggregated across machines. Circumvention can lead to access restriction.
  - No implying arXiv endorsement. — [arXiv API ToU](https://info.arxiv.org/help/api/tou.html)
- **OpenAlex** counts CC BY-NC-ND as OA. — [OpenAlex help](https://help.openalex.org/hc/en-us/articles/41193820509079-What-is-an-OA-license)
  - It now charges per call above a free daily allowance, with full-text downloads at $0.01 each. — [OpenAlex auth docs](https://developers.openalex.org/api-reference/authentication)
- **Semantic Scholar** API access is revocable at will, the API cannot be redistributed, and attribution is required. — [S2 API License](https://www.semanticscholar.org/product/api/license)
- **Model-weight licences differ from code licences:**
  - Nougat: CC-BY-NC weights.
  - Marker/Surya: OpenRAIL-M with a $5M threshold.
  - MinerU: custom attribution and commercial thresholds; VLM weights tagged AGPL. — sources in section 4
- **Licence metadata can be wrong even in curated corpora.** The Common Pile warns that some documents may have incorrect licences. — [Common Pile arXiv card](https://huggingface.co/datasets/common-pile/arxiv_papers_filtered/blob/refs%2Fpr%2F1/README.md)

### Inferences
- **Store licence per asset, not just per paper.** ResearchBridge should store the article licence plus per-figure/table overrides parsed from JATS `<fig><permissions>`. By default, exclude or display-only any figure carrying its own permissions block, and exclude its caption from rewriting.
- **Normalise licence from structured fields in this order:**
  1. PMC `license_code`.
  2. Europe PMC `license`.
  3. JATS `xlink:href` or `ali:license_ref`.
  4. arXiv OAI `<license>`.
  5. bioRxiv `license`.
  
  Treat free-text `license-p` only as a human-review fallback. Never auto-classify a paper as CC BY from prose alone.
- **Record provenance and versioning.** Each row should hold the licence URI, the source, the retrieval date and the article version, for example `PMC123.2` or `arXiv 2401.00001v3`. This audits against licence changes and PMC's "maintain the most current version" obligation. Handle `is_retracted` by unpublishing or flagging.
- **Rewrites create derivative works under CC BY.** They need attribution and an indication of changes. CC BY-SA rewrites must be released under CC BY-SA, which ResearchBridge's rewrite output would have to honour. This is general CC licence knowledge; I did not re-verify the licence texts in this session.
- **NC handling:** for NC content, the commercial question depends on ResearchBridge's business model, which needs legal review.

### Gaps
- PMC's exact policy on third-party figures inside OA-subset CC BY articles was not found. There is no official statement on whether such figures are excluded or flagged.
- I found no quantitative study of how often CC BY articles contain separately licensed figures.
- I found no audit of "CC BY with publisher-added restrictions", such as extra terms in `license-p` text contradicting the CC URI.
