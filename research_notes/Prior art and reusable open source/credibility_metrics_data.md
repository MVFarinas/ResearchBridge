# Reusable credibility and impact data and tools for ResearchBridge (status as of 13 October 2026)

Scope: open data sources, APIs and open-source tools that could power ResearchBridge's citation, influence, journal-quality, recency and integrity signals. The table below covers licences and commercial-use terms, and the last section covers how existing products show credibility and the legal history of labelling journals (decisions.md §2.3). The readability/convolution score and the prior-knowledge burden score belong to another researcher and are mentioned only in passing.

**Quick licence matrix (detail and sources in the sections below)**

| Source | What it gives | Data licence / terms | OK to display in a commercial product? |
|---|---|---|---|
| OpenAlex | citations, counts_by_year, FWCI, percentile, journal h-index / 2yr mean citedness, is_retracted, journal allow-lists | CC0; API metered (free $1/day) | Yes (CC0). Only API usage costs money |
| Crossref REST API | is-referenced-by-count, references, retractions/updates (incl. Retraction Watch) | Metadata "freely available", reusable without licence; RW citation requested | Yes |
| Retraction Watch DB (Crossref) | retractions, EoCs, corrections, reasons | Publicly available CSV, updated daily; no explicit licence file found | Very likely yes; cite source |
| OpenCitations Index | DOI-to-DOI citations (~2.2B) | CC0 | Yes |
| NIH iCite / Open Citation Collection | citations by year, RCR, APT (PubMed only) | Public domain, no restrictions on use (per NIH) | Yes (PubMed-indexed papers only) |
| DOAJ | journal inclusion, article metadata | CC0 (current terms) | Yes |
| Semantic Scholar API | citations, influential citations, intents | Default licence is non-commercial; commercial use needs an expanded licence; logo + link required on public display | **No, not without negotiating with AI2** |
| SCImago SJR | journal rank / quartile | Free to consult; reproduction or commercialisation needs prior written permission | **No, not without permission** |
| scite | supporting/contrasting citations | Commercial (Research Solutions); API in a paid tier | Needs a commercial agreement |
| Altmetric | attention data | Free only for non-commercial research or individual/institutional badges | Needs a paid contract |
| Dimensions | citations, FCR, etc. | No-cost only for non-commercial scientometric research (SRAD) | Needs a paid contract |
| Crossref Event Data | altmetric events | **Shut down 23 Apr 2026** | n/a |
| Google Scholar | citations | No API; robots.txt disallows /scholar | No |

---

## 1. Citation data: OpenAlex, Semantic Scholar, Crossref, OpenCitations, Dimensions, Google Scholar, plus citation growth over time

### Takeaway
OpenAlex is the clear backbone. Its data is CC0, including per-year citation counts, FWCI and percentiles, and its main change since early 2026 is metered API pricing ($1/day free), not a change to the data licence. Crossref, OpenCitations and NIH iCite are also open (CC0, no-licence or public domain) and work as cross-checks. Semantic Scholar's default API licence forbids embedding in a commercial product. Dimensions and Google Scholar are not usable for a commercial reader-facing product without a contract.

### Cited Findings

**OpenAlex: licence**
- OpenAlex states its data is "a public good, released under a CC0 public-domain license with no 'personal use only' carve-out and no permission to ask". Revenue comes from services (serving, freshness, support), "mirroring the POSI principle of revenue based on services, not data." — [OpenAlex Pricing overview](https://help.openalex.org/access/pricing/)
- The blog says the full dataset "is free to download, share, remix, and build on." — [OpenAlex blog (Feb 24, 2026 post)](https://blog.openalex.org/author/jason)

**OpenAlex: 2026 pricing and API-key changes (dated)**
- 16 Jan 2026 roadmap: "Credit-based API pricing launches this month." 24 Feb 2026 post: "you'll need an API key for all requests". Keys are free, and without one the API is "not suitable for any kind of production use." — [OpenAlex blog](https://blog.openalex.org/author/jason)
- Current per-operation prices per 1,000 calls: single entity by ID/DOI **free**; list+filter **$0.10**; search **$1**; group-by $0.10 (list) or $1 (search); rerank add-on +$1; semantic search $1; cached PDF content download **$10**. — [OpenAlex Example costs](https://help.openalex.org/access/example-costs/)
- Free tier: every account gets "$1 of API usage per day for free", no payment method required, resetting at midnight UTC. Prepaid top-ups come in $1 increments and expire 3 months after the last purchase. Annual plans: **Member $5,000/yr** ($20/day budget), **Member+ $10,000/yr** ($100/day plus daily sync), **Partner from $20,000/yr** ($200+/day). — [OpenAlex Pricing overview](https://help.openalex.org/access/pricing/)
- Rate limits: no key 10 req/s; free key or prepaid 30 req/s; annual plan 50 req/s. Semantic search is limited to 1 req/s. A free key "raises your daily budget 10×" over keyless use, and the basic paging limit is 10,000 results. — [OpenAlex Authentication](https://help.openalex.org/api/authentication/)
- **Conflict:** the Feb 2026 blog says a key is needed "for all requests", but the current auth docs say "you can make basic queries with no key at all", with a lower budget and 10 req/s. — [OpenAlex blog](https://blog.openalex.org/author/jason) vs [OpenAlex Authentication](https://help.openalex.org/api/authentication/). Either way, ResearchBridge should use a key.
- Bulk snapshot: a free, anonymous S3 bucket (`s3://openalex`, `--no-sign-request`) released **quarterly** on the second Wednesday of Jan/Apr/Jul/Oct, with daily snapshots on paid plans. AWS Open Data covers the ~$70 transfer fee per download. As of Sept 2026 the API default is ~327M works (core) vs ~476M with `corpus=all`, and the snapshot includes everything. — [OpenAlex Snapshot](https://help.openalex.org/access/snapshot/)
- Oct 2026: a topic reclassification (6 Oct 2026) shifted subfield baselines, so FWCI and percentiles "shift when subfields shift". University-level mean FWCI rank correlation was 0.99, and the median university moved 4.5%. — [OpenAlex blog](https://blog.openalex.org/author/jason)

**OpenAlex: citation metrics relevant to ResearchBridge**
- Works carry `cited_by_count` and `referenced_works`, built by extracting reference lists (Crossref, PubMed, OA PDFs) and matching by DOI or metadata. Counts can be lower than the PDF's reference list. — [OpenAlex Citations](https://help.openalex.org/data/works/citations/)
- `fwci` = citations received (publication year + 3 following years) ÷ the average for works of the same year, type and subfield. 1.0 is world average. It follows the Snowball Metrics recipe, and the calculation code is public. "As of mid-2026 about 218M of 322M works (68%) carry one." — [OpenAlex Citations](https://help.openalex.org/data/works/citations/)
- `citation_normalized_percentile` gives the same information as a percentile, with `is_in_top_1_percent` and `is_in_top_10_percent`. — [OpenAlex Work attributes](https://help.openalex.org/data/works/attributes/)
- **Citation growth over time:** `counts_by_year` is a per-year rollup for roughly the last ten years (`{year, works_count, cited_by_count}`), "handy for sparklines and trend lines". The sort order is inconsistent across entity types, so sort by year yourself. — [OpenAlex Common attributes](https://help.openalex.org/data/common-attributes/)
- Source (journal) `summary_stats` includes `2yr_mean_citedness` (impact-factor-style), `h_index` and `i10_index`. These are labelled "convenience metrics; for anything rigorous, compute over the underlying works." — [OpenAlex Common attributes](https://help.openalex.org/data/common-attributes/)

**Semantic Scholar (AI2)**
- License grant: "Such use is limited to Licensee's internal use solely for the purpose of training and evaluating machine learning models and transforming data sets for legitimate, non-commercial, research and/or educational purposes." — [Semantic Scholar API License Agreement](https://api.semanticscholar.org/license)
- "Prohibited commercial use includes, but is not limited to, selling, leasing, or licensing the API for monetary or other commercial gain, or **embedding or installing the API into products for Licensee's own commercial gain** or for the commercial gain of third parties." For commercial use, contact AI2 for an "Expanded License". — [S2 API License](https://api.semanticscholar.org/license)
- Public use of the data "must point back to Semantic Scholar … with a utm_source=api UTM parameter", and public displays must "include the Semantic Scholar name and logo". Licensees may not "sell, lease, share, transfer, sublicense, commercialize" data obtained through the API. — [S2 API License](https://api.semanticscholar.org/license)
- The S2 bulk datasets (S2AG) were described in 2023 as downloadable under ODC-By 1.0, with abstracts included only "where allowed by licensing". — [Semantic Scholar Open Data Platform paper (arXiv 2301.10140)](https://arxiv.org/pdf/2301.10140). I could not confirm on a current official page whether the datasets licence differs from the API agreement above (see Gaps).

**Crossref**
- `is-referenced-by-count` in the REST API gives the number of Crossref DOIs citing a DOI (added April 2017). — [Crossref rest-api-doc issue #30](https://github.com/CrossRef/rest-api-doc/issues/30)
- Crossref cited-by counts include only citing works registered with Crossref whose publishers deposited references, so they undercount. The identities of the citing DOIs are available only to members, for their own DOIs. — [Crossref community forum](https://0-community-crossref-org.libus.csd.mu.edu/t/overlap-between-different-services-providing-citation-data/2994)
- In late 2017, ~50.84% of ~956M references in Crossref were "Open". — [Infodocket / I4OC](https://www.infodocket.com/2017/11/24/milestones-initiative-for-open-citations-i4oc-reports-open-references-at-crossref-exceed-50/)
- Crossref metadata (including retractions) is "freely available" and can be reused without a licence. — [Crossref blog, 29 Jan 2025](https://www.crossref.org/blog/retraction-watch-retractions-now-in-the-crossref-api/)

**OpenCitations**
- The OpenCitations Index had >2.2 billion citations as of the July 2025 dump (2,216,426,689 citations, released 2025-07-10, including the March 2025 Crossref data), drawn from five reference sources, under CC0, accessible via REST API, SPARQL and dumps. — [OpenCitations Data Downloads](https://download.opencitations.net); [OpenCitations Index paper (arXiv 2408.02321)](https://arxiv.org/abs/2408.02321)
- COCI (the original Crossref-derived index) is CC0 with a RAMOSE-built REST API. — [COCI paper (arXiv 1904.06052)](https://arxiv.org/pdf/1904.06052)
- The index-building software is on GitHub under the ISC licence (last pushed Sept 2026). — [opencitations/index](https://github.com/opencitations/index)

**NIH iCite (biomedicine only)**
- The NIH Open Citation Collection is described by NIH authors as a "public domain citation database" covering PubMed-indexed articles, built from CrossRef, MEDLINE, PMC, Entrez and ML-extracted references from OA full text. — [Hutchins et al., PLOS Biology 2019 (PMC6786512)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6786512)
- The iCite "Open Cites" module "disseminates link-level, public-domain citation data". Snapshots are on NIH Figshare. — [iCite Database Snapshot (NIH Figshare)](https://nih.figshare.com/articles/dataset/iCite_Database_Snapshot_2023-08/24100917); [NIH iCite support](https://support.analytics.nih.gov/hc/en-us/articles/18451694307995-iCite)
- **Growth-over-time data:** a live keyless call to `https://icite.od.nih.gov/api/pubs?pmids=31581957` (13 Oct 2026) returned `citation_count`, `citedByPmidsByYear` (each citing PMID with its year), `field_citation_rate`, `expected_citations_per_year`, `apt`, `human`/`animal` and `is_research_article`. — [iCite API (direct call)](https://icite.od.nih.gov/api/pubs?pmids=31581957)
- RCR: the denominator is the expected citations per year for NIH-funded papers with the same field citation rate and year, and the median NIH-funded paper has RCR = 1. RCR and APT are not computed for preprints unless sourced from PubMed. — [NIH Figshare iCite snapshot docs](https://nih.figshare.com/articles/dataset/iCite_Database_Snapshot_2023-01/22045307)
- A third-party analysis batched ≤400 PMIDs per request "to comply with iCite rate limits". This is not verified against NIH docs. — [IJbeasley analysis](https://rawcdn.githack.com/IJbeasley/genomics_ancest_disease_dispar/0a2d4efa93cba8863a056248a200adfa23672e46/docs/icite_rcr.html)

**Dimensions (Digital Science)**
- No-cost Dimensions (Analytics API, BigQuery) and Altmetric access is offered through the Scientometric Researcher Access to Data (SRAD) programme for **non-commercial** projects by university-affiliated scientometrics researchers aiming to publish. — [Digital Science, Introducing SRAD](https://www.digital-science.com/blog/introducing-srad-scientometric-researcher-access-data-program/)
- Python client `dimcli` is MIT-licensed (the client only, not the data). — [digital-science/dimcli](https://github.com/digital-science/dimcli)

**Google Scholar**
- There is no official Google Scholar API. Third-party scrapers (SerpApi, Apify, Oxylabs) exist. — [Scrapfly overview](https://scrapfly.io/blog/posts/google-scholar-api-and-alternatives); [CASRAI](https://www.casrai.org/dictionary/term/google-scholar-api) (secondary)
- Google Scholar's robots.txt (fetched 13 Oct 2026) has `Disallow: /search`, `Disallow: /scholar` and `Disallow: /citations?`, with only some profile and metrics views allowed. — [scholar.google.com/robots.txt](https://scholar.google.com/robots.txt)

### Inferences
- For a possibly commercial product, the safe stack is **OpenAlex (primary) + Crossref + OpenCitations (+ iCite for PubMed papers)**, all CC0, public domain or no-licence. Semantic Scholar would require an AI2 expanded licence once ResearchBridge is commercial. Even non-commercially, its terms limit use to "internal use … training and evaluating ML models and transforming data sets", which arguably does not cover a public reader app at all.
- OpenAlex costs are negligible for ResearchBridge's main pattern. Per-paper lookups by DOI are **free**, and the paper and journal records already contain `cited_by_count`, `counts_by_year`, `fwci`, `citation_normalized_percentile` and `is_retracted`. Caching from the quarterly free snapshot is the fallback if pricing changes again. OpenAlex has changed its pricing model twice in 2026, from credits to dollars.
- Citation growth can be rendered as a sparkline from OpenAlex `counts_by_year` (all fields, ~10 years) or iCite `citedByPmidsByYear` (biomed, full history).
- FWCI and percentiles are recomputed and can shift (Oct 2026 reclassification). Displayed values should carry an "as of" date and the source name.
- For arXiv preprints, citation counts will be low or zero and FWCI may be absent. Recency should temper the citation signal in the UI.

### Gaps
- I could not confirm the current Semantic Scholar *Datasets* licence (ODC-BY in 2023 papers) from an official 2026 page, or whether the API agreement's non-commercial clause applies to the bulk datasets.
- No verified current rate limit for iCite or the S2 API, and no published price for an AI2 commercial licence.
- I could not confirm whether Crossref made all deposited references open by default (believed around 2022). No 2022 source surfaced.
- I could not confirm the OpenCitations v2 API endpoint or whether it now requires a key (only an aggregator mentioned it).
- No official Dimensions commercial pricing found.

---

## 2. "Smarter" citation signals: scite, Semantic Scholar influential citations, FWCI, RCR / iCite

### Takeaway
Field-normalised impact is freely available and commercially reusable: OpenAlex FWCI and percentile (CC0) for all fields, and NIH RCR (public domain) for PubMed. Citation-context signals are either proprietary and paid (scite's supporting/contrasting counts) or locked behind Semantic Scholar's non-commercial licence ("highly influential citations", intents).

### Cited Findings
- scite pricing (official): Basic $20/mo or $144/yr; **Pro $50/mo or $480/yr, which "adds API access"**; Team up to 15 seats. — [scite pricing](https://scite.ai/pricing.md)
- Research Solutions (NASDAQ: RSSS) acquired scite on 27 Nov 2023. scite then had $3.6M annualised subscription value and ~21,000 B2C subscribers. — [NISO](https://niso.org/niso-io/2023/11/research-solutions-announces-acquisition-scite)
- Publishers such as Karger embed the scite badge (supporting/contrasting citation summary) on article pages through partnership with Research Solutions. — [STM Publishing News](https://stm-publishing.com/?p=29545)
- Semantic Scholar "Highly Influential Citations": only citations between papers with no overlapping authors are eligible. A citation is flagged if it appears several times, if it uses phrases like "build upon" or "inspired by", or if it refers to a table or figure. The approach is inspired by Valenzuela et al. (2015). — [Semantic Scholar Open Data Platform (arXiv 2301.10140)](https://arxiv.org/pdf/2301.10140)
- Valenzuela et al. found only 14.6% (69 of 465 annotated) citations were influential. The strongest features were citation frequency per section and author overlap. — [Tahamtan & Bornmann review (arXiv 1906.04588)](https://arxiv.org/pdf/1906.04588)
- OpenAlex FWCI and percentile: see section 1. CC0, with public calculation code. — [OpenAlex Citations](https://help.openalex.org/data/works/citations/)
- iCite RCR and APT (Approximate Potential to Translate) are public domain via a keyless API. — [PLOS Biology 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6786512); [iCite API](https://icite.od.nih.gov/api/pubs?pmids=31581957)

### Inferences
- "Influence in field" can be shown as an OpenAlex percentile ("in the top 10% of papers in its subfield and year by citations") without any licensing friction. That wording is relative and factual, not a judgement.
- The supporting/contrasting idea is the most reader-friendly signal but is proprietary. ResearchBridge could not reuse scite data without a commercial agreement. A home-grown citation-intent classifier over open full text (PMC OA, arXiv) is possible but is a research project in itself.

### Gaps
- No scite API terms of use or redistribution and display terms were found publicly. Badge embedding appears to be through publisher partnerships, and whether a third-party app may embed scite badges is unconfirmed.
- Whether OpenAlex will add citation-intent or context data is unknown.

---

## 3. Journal quality and integrity signals: DOAJ, Think.Check.Submit, Cabells, Beall successors, SJR, JCR, Scopus/WoS, OpenAlex source metrics, Retraction Watch, PPS, STM Integrity Hub, PubPeer, Expressions of Concern

### Takeaway
There is a rich, openly licensed set of **positive (allow-list) signals**: DOAJ membership (CC0), CWTS Core, MEDLINE, national journal lists via OpenAlex `listed_in`, and OpenAlex journal h-index and 2-year mean citedness. There is also a fully open **paper-level integrity signal**, Retraction Watch via Crossref and OpenAlex `is_retracted`. Negative journal lists (Cabells) are commercial, and their open predecessors (Beall) were withdrawn under pressure. SJR is free to view, but SCImago requires written permission for commercial reuse. Paper-mill screening tools (STM Integrity Hub, Clear Skies) are restricted to publishers.

### Cited Findings

**DOAJ**
- Current DOAJ terms: journal-level and article-level metadata are available under **CC0**, via API, CSV, OAI-PMH and dumps. The DOAJ FAQ says anyone can ingest the metadata "without any attribution to DOAJ". Site content itself is all rights reserved. — [DOAJ Terms](https://www.doaj.org/terms/); [DOAJ FAQ](https://www.doaj.org/faq)
- **Conflict / history:** in Dec 2020 DOAJ said journal metadata was CC BY-SA 4.0 while article metadata moved to CC0. Current terms say CC0 for both, and I found no dated changelog for the switch. — [DOAJ blog, 14 Dec 2020](https://blog.doaj.org/2020/12/14/important-changes-to-our-journal-csv-and-how-we-license-metadata)
- **The DOAJ Seal was retired effective 8 April 2025.** DOAJ said it was "widely misunderstood and misused", easier for better-resourced journals, and associated with prestige against DOAJ's equal-visibility aim. The logo and metadata flag were removed, and the best-practice criteria remain. — [DOAJ blog, 9 Apr 2025](https://blog.doaj.org/2025/04/09/our-metadata-changes-are-live-and-the-seal-has-been-retired); [EASE](https://ease.org.uk/2025/05/doaj-retirement-of-the-seal/)

**OpenAlex journal lists and metrics (all CC0)**
- OpenAlex "prefers allow lists (curated lists of trusted sources) over deny lists: they're more transparent, easier to maintain". Flags: `is_in_doaj` (~23,000 sources) and `is_core` (CWTS Core, ~36,000). The general field is `listed_in`. — [OpenAlex Sources](https://help.openalex.org/data/sources/)
- `listed_in` is "deliberately non-normative: OpenAlex records *that* a list includes a source, not whether the list is right". "OpenAlex does not endorse any list." Lists match by ISSN, and only current members count. — [OpenAlex Source lists](https://help.openalex.org/data/source-lists/)
- Lists added Sept–Oct 2026 include MEDLINE (~5,200; 2026-09-18 edition), Doyens de Médecine (FR) (~3,300, a French anti-predatory health list), Norwegian Register levels 1/2, Finnish JUFO 1/2/3, ERIH PLUS, JPPS (AJOL/INASP, Global South), Latindex, SciELO, Karolinska list, ABDC, Russian White List, Polish list, VABB-SHW, FNEGE, FT50, UTD24, ANVUR, KCI, CCF, FECYT seal, Publindex and the Dongbi Index. — [OpenAlex Sources](https://help.openalex.org/data/sources/); [OpenAlex Source lists](https://help.openalex.org/data/source-lists/)
- Each listed source keeps the original list's provenance (maintainer, edition), which supports attribution. — [OpenAlex Source lists](https://help.openalex.org/data/source-lists/)

**SCImago Journal Rank (SJR)**
- The SCImago legal notice says "total or partial reproduction, use, exploitation, distribution and commercialisation, requires in any case the prior written authorisation" of SCImago Research Group, S.L., "regardless of their intended purpose". — [SCImago legal notice](https://www.scimagojr.com/legal-notice.php)
- The SCImago FAQ says rankings are "open access", that academic use must cite the source, and that the indicators derive from Scopus (SCImago doesn't select journals). — [SCImago Lab FAQ](https://en.scimagolab.com/faqs-2/)

**Cabells Predatory Reports (commercial)**
- Cabells worked with Beall from 2015, denied involvement in the 2017 takedown, and launched its blacklist on 15 June 2017. It was renamed "Predatory Reports" in June 2020 and uses 70+ criteria. — [Wikipedia: Cabell Publishing](https://en.wikipedia.org/wiki/Cabell_Publishing); [Scholarly Kitchen 2017](https://scholarlykitchen.sspnet.org/2017/07/25/cabells-new-)
- The database passed 20,000 journals (20,274 as of 30 Jan 2026). — [Research Information](https://www.researchinformation.info/?p=8433)
- I found no reported lawsuit against Cabells over a listing (searched; null result).

**Think. Check. Submit.**
- This is a free checklist campaign for evaluating journals and publishers. No licence for reusing the checklist text was found. — [UKSG Insights article](https://account.insights.uksg.org/index.php/up-j-i/article/view/uksg.323)

**Retraction Watch Database (Crossref)**
- Crossref acquired the database on 12 Sept 2023 and made it "completely open and freely available". Crossref pays Retraction Watch an annual maintenance fee, initially for five years. At the time it held ~43,000 records. — [Retraction Watch, 12 Sept 2023](https://retractionwatch.com/2023/09/12/the-retraction-watch-database-becomes-completely-open-and-rw-becomes-far-more-sustainable); [GWU Himmelfarb blog](https://blogs.gwu.edu/himmelfarb/tag/retractions)
- Since 29 Jan 2025 Retraction Watch retractions appear in the Crossref REST API in `update-to`, with `source: retraction-watch` or `publisher`. Crossref "kindly request[s]" citation of the source, but this is not required. — [Crossref blog](https://www.crossref.org/blog/retraction-watch-retractions-now-in-the-crossref-api/); [Crossref docs](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/)
- The CSV on GitLab is updated every working day (latest generated 2026-10-12). `RetractionNature` covers Retraction, Correction, **Expression of concern** and Reinstatement, though EoCs and corrections are "not as comprehensive as retractions". Retraction reasons use a controlled vocabulary. The README states no explicit licence. — [crossref/retraction-watch-data (GitLab)](https://gitlab.com/crossref/retraction-watch-data)
- OpenAlex `is_retracted` is "True if the work is known to be retracted, per the Retraction Watch database". — [OpenAlex Work attributes](https://help.openalex.org/data/works/attributes/)

**Problematic Paper Screener (PPS) and tortured phrases**
- PPS (Cabanac, Labbé, Magazinov) flags published papers using fingerprint queries run against Dimensions, followed by human review. In Oct 2021, 276 tortured-phrase fingerprints flagged 1,694 papers. — [PPS paper (arXiv 2210.04895)](https://arxiv.org/pdf/2210.04895)
- PPS later scanned ~130M papers weekly, with ~19,000 papers containing ≥5 tortured phrases, and has been linked to >1,000 retractions (IOP alone retracted >1,000). — [Retraction Watch](https://retractionwatch.com/?p=136186); [CNRS News](https://news.cnrs.fr/print/1825)
- A regex-based tortured-phrase detector was proposed that publishers can run without a Dimensions subscription. — [Peer Review Congress abstract](https://peerreviewcongress.org/abstract/screening-articles-for-tortured-phrases-with-a-regular-expressions-based-detector)

**STM Integrity Hub and paper-mill detection**
- The STM Integrity Hub Paper Mill Checker MVP was "available only to participating publishers in the Hub". The Hub integrates Clear Skies' Papermill Alarm (traffic-light rating, public version optimised for cancer research; opt-in for publishers) and PubPeer data. — [STM, Papermill checker](https://stm-assoc.org/papermillchecker/); [STM + Clear Skies](https://stm-assoc.org/stm-integrity-hub-incorporates-clear-skies-papermill-alarm-screening-tool/); [Scholarly Kitchen, May 2024](https://scholarlykitchen.sspnet.org/2024/05/23/guest-post-the-research-integrity-hub-connecting-the-dots-in-a-dynamic-landscape/)

**PubPeer**
- PubPeer says most journals don't want PubPeer comments on their sites, so it offers browser extensions that show a banner when an article has comments. — [PubPeer extensions](https://www.pubpeer.com/static/extensions)
- A 2019 Zotero forum thread says PubPeer's API is "keyed"; contact PubPeer for access. — [Zotero forums](https://forums.zotero.org/discussion/comment/332582)

**Grey-area labelling by an accountable body (precedent)**
- Finland's Publication Forum (JUFO) downgraded 271 MDPI (193) and Frontiers (78) journals to level 0 from 2025 as "grey area" journals. 60 journals had been downgraded in 2024. A May 2025 panel restored some, and in June 2026 JUFO removed the downgraded list from its Dec 2024 news item. MDPI objected that the bulk move "suggests a generalized evaluation process". — [Retraction Watch, 24 Dec 2024](https://retractionwatch.com/2024/12/24/finland-publication-forum-will-downgrade-hundreds-of-frontiers-and-mdpi-journals); [JUFO news](https://julkaisufoorumi.fi/en/news/grey-area-journals-level-0); [LSMU decision](https://lsmu.lt/en/decision-on-downgrading-mdpi-and-frontiers-journals-from-2025)

### Inferences
- The most defensible journal signal for §2.3 is **attributed positive list membership**, e.g. "Listed in DOAJ · Indexed for MEDLINE · on CWTS Core (Leiden)". Each item is a checkable fact with a named maintainer, available via OpenAlex `listed_in` under CC0. The absence of a listing should **not** be rendered as a negative label, because many legitimate journals are on no list.
- Paper-level retraction, correction and EoC status is a fact published by the journal itself and aggregated openly. It is lower-risk and higher-value than journal-level judgements, and should be shown prominently.
- SJR quartiles, JCR impact factors and Cabells listings all need permission or paid contracts for commercial display. OpenAlex `2yr_mean_citedness` and `h_index` are CC0 substitutes, though they are less familiar to readers and differ numerically from JIF and SJR.

### Gaps
- Exact licence of the Retraction Watch CSV is not stated in the repo. Crossref describes it as freely available with citation requested, and I found no explicit CC0 statement.
- Clarivate JCR and Scopus/WoS display terms were not researched in detail. Both are commercial subscription products, and indexing status is typically not openly licensed.
- Cabells pricing, and whether Cabells licenses data for display in third-party consumer apps, was not found.
- Current STM Integrity Hub access terms and pricing (post-2024) were not found.
- No current confirmation of a public PubPeer API.
- Think.Check.Submit reuse licence was not found.

---

## 4. Altmetrics: Altmetric, Crossref Event Data, PlumX

### Takeaway
There is no open, commercially reusable altmetrics source left. Crossref Event Data was shut down on 23 April 2026, and Altmetric's free tiers exclude commercial products.

### Cited Findings
- Crossref announced on 24 Mar 2026 that the Event Data API "will no longer be available" from **23 April 2026**. The reasons were low usage and the cost of maintenance, with a pivot to integrity and completeness. Historical data stays available via a linked DOI, and a beta data-citation endpoint replaces part of it. — [Crossref blog](https://www.crossref.org/blog/strengthening-support-for-data-citations-and-saying-goodbye-to-event-data); [Event Data guide notice](https://www.eventdata.crossref.org/guide)
- Altmetric Details Page API free tier: non-commercial, for "researchers working on a specific academic, one-off project", attribution required, key required, rate limited. Paid contract access gives "the freedom to display the data as and where you choose". — [Altmetric API licensing](https://docs.altmetric.com/details-page-api/licensing/); [Altmetric research access](https://www.altmetric.com/research-access/)
- From 10 Nov 2025, all Altmetric Details Page API requests require an authentication key. — [Altmetric announcement](https://updates.altmetric.com/announcements/ann_vah31Uctf3Rck)
- Free Altmetric badges are limited to institutional repositories (for faculty content) and individual researchers' personal pages. "Organisations need to get in touch." — [Altmetric free badges](https://www.altmetric.com/?p=2808)

### Inferences
- An altmetric or attention signal would require a paid Altmetric (or PlumX) contract. It is also a weak credibility signal for lay readers, since attention is not validity. Skipping it in v1 seems reasonable.

### Gaps
- PlumX (believed to be Elsevier-owned) terms were not researched. No source was retrieved.

---

## 5. Open-source tools (wrappers, retraction checkers, integrity screeners)

### Takeaway
Mature permissively licensed clients exist for OpenAlex (pyalex, MIT), Semantic Scholar (MIT, though the data terms still bind), Dimensions (dimcli, MIT) and OpenCitations (ISC). Integrity-screening code is mostly research-grade: statcheck (GPL-3), scrutiny for GRIM/DEBIT (MIT), pysprite (MIT), and small MIT tortured-phrase checkers. Note GPL-3 if ResearchBridge ships closed-source code.

### Cited Findings
- **pyalex** (Python, OpenAlex): MIT, ~421 stars, pushed 2026-10-05. — [J535D165/pyalex](https://github.com/J535D165/pyalex)
- **openalex-elastic-api** (OpenAlex's own API code): MIT, pushed 2026-10-12. — [ourresearch/openalex-elastic-api](https://github.com/ourresearch/openalex-elastic-api)
- **semanticscholar** (unofficial Python client): MIT, pushed 2026-08. — [danielnsilva/semanticscholar](https://github.com/danielnsilva/semanticscholar)
- **s2_fos** (AI2 field-of-study classifier): Apache-2.0. — [allenai/s2_fos](https://github.com/allenai/s2_fos)
- **dimcli** (Dimensions client): MIT. — [digital-science/dimcli](https://github.com/digital-science/dimcli)
- **opencitations/index**: ISC. — [opencitations/index](https://github.com/opencitations/index)
- **iCiteR** (R wrapper for the iCite API): CRAN mirror, last updated 2020. — [riddlet/iCiteR](https://github.com/riddlet/iCiteR); [rdocumentation](https://www.rdocumentation.org/packages/iCiteR/versions/0.2.1)
- **RetractoBot** (Bennett Institute, Oxford): MIT. It identifies retracted PubMed papers, finds citing papers via the Scopus API, and emails authors. It is used in an RCT. — [ebmdatalab/retractobot](https://github.com/ebmdatalab/retractobot); [Bennett Institute](https://www.bennett.ox.ac.uk/trialstracker/retractobot/)
- **Zotero retraction alerts**: they flag retracted items using Retraction Watch data (DOI/PMID items, ~3/4 of RW data) without sending library contents to the server. Zotero is AGPL (GitHub reports NOASSERTION). — [Zotero blog](https://www.zotero.org/blog/retracted-item-notification/); [zotero/zotero](https://github.com/zotero/zotero)
- **statcheck** (recomputes p-values from reported test statistics): R package, **GPL-3**. — [michelenuijten/statcheck DESCRIPTION](https://github.com/michelenuijten/statcheck)
- **scrutiny** ("Error Detection in Science": GRIM, DEBIT and related tests): R, **MIT**, actively maintained (pushed 2026-10-13). — [lhdjung/scrutiny](https://github.com/lhdjung/scrutiny)
- **pysprite** (SPRITE re-implementation): MIT, last updated 2021. **grim_test** (Python GRIM): MIT. — [QuentinAndre/pysprite](https://github.com/QuentinAndre/pysprite); [phoughton/grim_test](https://github.com/phoughton/grim_test)
- **torturedcheck** (detects tortured phrases using the PPS list): MIT. — [giladfeldman/torturedcheck](https://github.com/giladfeldman/torturedcheck)

### Inferences
- For ResearchBridge, pyalex plus a thin Crossref/Retraction Watch client covers almost all of the credibility panel. Integrity screeners (statcheck, GRIM, tortured phrases) produce probabilistic accusations about specific named authors' papers. Showing their output to lay readers carries far more defamation risk than showing a retraction notice, so they are better kept internal, for example to deprioritise or flag papers for human review.
- Readability tooling for the other researcher's metrics (e.g. textstat-style libraries) was out of scope and not researched here.

### Gaps
- Seek & Blastn (nucleotide-sequence verification tool) was not found on GitHub. Its availability and licence are unconfirmed.
- No official Problematic Paper Screener code or data-export licence was found. The torturedcheck repo uses the PPS list, but the list's own licence is unverified.

---

## 6. How existing products present credibility, and disputes and lawsuits over labelling journals

### Takeaway
Reader-facing products present credibility as **attributed, relative, positive tags** ("Rigorous journal" per SciScore; "Highly cited"; "Listed in DOAJ"; "Top 10% in field"), often with caveats. They do not present it as negative verdicts about named journals. History shows that negative lists attract sustained legal and institutional pressure (Beall), while the one big legal win against a predatory publisher (OMICS) came from a regulator (the FTC) under consumer-protection law, not from a list-maker. Accountable bodies that downgrade journals (JUFO) still draw public objections and partial reversals.

### Cited Findings

**Product presentation**
- **Consensus:** the Consensus Meter 2.0 "Snapshot" reports four quality indicators per position: recency, methods (counts of meta-analyses, systematic reviews and RCTs), journals (average **SJR** scores) and citations. Indicator badges show which position "won" a category. It is a paid (Premium) feature. — [Consensus blog, Meter 2.0](https://consensus.app/home/blog/new-consensus-meter/)
- Consensus "Rigorous journal" / "Very rigorous journal" tags mean the journal is in the top 50% / top 10% of SciScore's Rigor and Transparency Index. "Highly cited" tags come with the caveat that high citation "does not necessarily mean its results are any more valid". — [UVA Library guide](https://guides.lib.virginia.edu/consensus); [Aaron Tay, 2025 deep dive](https://aarontay.substack.com/p/a-2025-deep-dive-of-consensus-promises); [Consensus + SciScore partnership](https://consensus.app/home/blog/consensus-and-sciscore-partner-to-deliver-accurate-science-based-answers-for-all/)
- Critics note journal labels are a weak proxy, since "even the most 'rigorous' journals publish weak or even retracted studies", and SciScore is biomedicine-optimised. — [Aaron Tay](https://aarontay.substack.com/p/a-2025-deep-dive-of-consensus-promises)
- **Consensus uses SJR scores in a commercial product.** This implies a SCImago licence or permission, given SCImago's legal notice, but no confirming source was found. — [Consensus blog](https://consensus.app/home/blog/new-consensus-meter/); [SCImago legal notice](https://www.scimagojr.com/legal-notice.php)
- **scite** shows supporting/contrasting/mentioning counts as a badge on publisher pages through partnerships. — [STM Publishing News](https://stm-publishing.com/?p=29545)
- **OpenAlex** frames journal lists as non-normative ("records *that* a list includes a source, not whether the list is right"; "does not endorse any list") and prefers allow lists to deny lists. — [OpenAlex Source lists](https://help.openalex.org/data/source-lists/); [OpenAlex Sources](https://help.openalex.org/data/sources/)
- **DOAJ** retired its own quality badge (the Seal) in April 2025 because it was misread as a prestige signal. — [DOAJ blog](https://blog.doaj.org/2025/04/09/our-metadata-changes-are-live-and-the-seal-has-been-retired)
- **PubPeer** reaches readers through opt-in browser extensions, because journals did not want comments on their own sites. — [PubPeer extensions](https://www.pubpeer.com/static/extensions)

**Disputes and lawsuits**
- **Beall's list:** taken offline 15 Jan 2017. Beall later wrote: "In January 2017, facing intense pressure from my employer, the University of Colorado Denver, and fearing for my job, I shut down the blog". He also described publishers harassing him, his colleagues and his university over long periods (Beall, *Biochemia Medica* 2017;27(2):273–279, doi:10.11613/BM.2017.029). — [GWU Himmelfarb guide quoting Beall](https://guides.himmelfarb.gwu.edu/PredatoryPublishing/Beall); [Debunking Denialism, June 2017](https://debunkingdenialism.com/2017/06/15/we-now-know-why-jeffrey-beall-removed-list-of-allegedly-predatory-publishers/)
- **Frontiers:** added to Beall's list in 2015 per most sources (one says 2016). Frontiers' pushback, including requests that his employer open a misconduct case, is widely cited as a main trigger for the takedown. This is a commentator view, not confirmed by Beall's own text in the sources retrieved. — [Wikipedia: Beall's List](https://en.wikipedia.org/wiki/Beall%27s_List); [Wikipedia: Frontiers in Physics](https://en.wikipedia.org/wiki/Frontiers_in_Physics)
- **MDPI:** listed by Beall in Feb 2014, removed on 28 Oct 2015 after a successful appeal. OASPA's review also found MDPI met its criteria. — [Wikipedia: Beall's List](https://en.wikipedia.org/wiki/Beall%27s_List); [CASRAI: MDPI](https://www.casrai.org/dictionary/term/mdpi) (secondary)
- **OMICS:** OMICS reportedly threatened to sue Beall for $1 billion for defamation. — [Wikipedia: Gedela Srinubabu](https://en.wikipedia.org/wiki/Gedela_Srinubabu) (secondary, needs verification). The FTC sued OMICS, iMedPub and Conference Series in 2016, and on 29 Mar 2019 Judge Gloria Navarro (D. Nev.) ordered OMICS to pay **$50,130,810** for deceptive practices. — [Retraction Watch, 2 Apr 2019](https://retractionwatch.com/2019/04/02/court-orders-publisher-omics-to-pay-u-s-govt-50-million-in-suit-alleging-unfair-and-deceptive-practices); [Chemistry World](https://chemistryworld.com/news/predatory-publisher-omics-fined-50-million-by-us-court-for-defrauding-scientists/3010348.article)
- **JUFO vs MDPI/Frontiers (2024–2026):** bulk downgrades drew public objection from MDPI and led to partial reversals after panel review (see section 3). — [Retraction Watch](https://retractionwatch.com/2024/12/24/finland-publication-forum-will-downgrade-hundreds-of-frontiers-and-mdpi-journals); [JUFO](https://julkaisufoorumi.fi/en/news/grey-area-journals-level-0)
- **Cabells:** no lawsuit over a Predatory Reports listing was found (null result). The list is behind a paywall and uses published criteria. — [Wikipedia: Cabell Publishing](https://en.wikipedia.org/wiki/Cabell_Publishing)

### Inferences
- For §2.3, the evidence favours a **hybrid of options 1 and 2**: show neutral quantitative facts (citations, citation trend, FWCI percentile, recency, retraction/EoC status) plus **attributed positive list membership** (DOAJ, MEDLINE, CWTS Core, national lists via OpenAlex `listed_in`). Never show a negative "low quality" or "predatory" verdict, and never treat absence from a list as a verdict. Every product reviewed that survives commercially works this way. The one prominent negative-list operator (Beall) was forced offline, and the commercial negative list (Cabells) is paywalled and institution-facing rather than consumer-facing.
- Wording matters. "Retracted on [date] by [journal] (source: Retraction Watch/Crossref)" is a statement of public fact. "This journal is predatory" is an opinion about a named business. Pair each signal with a "what this does and doesn't mean" tooltip, as Consensus does with its "highly cited ≠ valid" caveat.
- Third-party negative lists (Cabells, Doyens' anti-predatory list as a positive allow-list) shift but do not remove risk. Republishing a defamatory statement can itself be actionable in many jurisdictions. This is general legal knowledge, not verified for Canada or the US in this research, so legal review is advised before any negative label ships.
- Licence-wise, the hybrid can be built entirely on CC0 or public-domain data (OpenAlex, Crossref/RW, DOAJ, OpenCitations, iCite). That keeps it compatible with a future paid tier, unlike Semantic Scholar, SJR, scite, Altmetric or Dimensions.

### Gaps
- Elicit's quality and risk-of-bias presentation and Kudos's presentation were not found in searches. These are unconfirmed and not described here.
- Semantic Scholar's reader-facing presentation (e.g. "Highly Influential Citations" counts on paper pages) was not verified from a primary page in this pass.
- No case law was found on a *consumer app* being sued for displaying a third-party journal-quality label. Jurisdiction-specific defamation analysis (e.g. Canada) was out of scope and needs legal advice.
- Beall's exact words about Frontiers in the Biochemia Medica article were not retrieved directly.
