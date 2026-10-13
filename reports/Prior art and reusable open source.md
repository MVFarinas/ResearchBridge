# Borrow the plumbing, build the faithful core

No existing product or open-source project combines everything ResearchBridge proposes: a faithful full-paper plain-English rewrite beside the untouched original, a lay-oriented summary that surfaces limitations, conflicts of interest and statistical strength, per-paper readability and prior-knowledge scores, and discussion aimed at non-experts. Each individual piece, however, is a commodity. Highlight-to-explain is free in Explainpaper, included in SciSpace's free tier and open-sourced by Google in Lumi. Citation metrics are CC0 in OpenAlex. Anchoring, PDF rendering, grounded question answering, scholarly parsing and comment engines all exist under permissive licences and were actively maintained as of October 2026. The closest prior art, AI2's Paper Plain, targeted lay readers of medical papers but remained a prototype whose code has no licence. ResearchBridge can therefore assemble most of its infrastructure from BSD, MIT and Apache projects: JATS and LaTeXML ingestion, Recogito or Hypothesis anchoring, PaperQA2 for cited extraction, OpenAlex and Crossref for credibility data, and Remark42 or Coral for threads. What differentiates the product has to be built: whole-document LLM annotation anchored to passages, a faithfulness-checked rewrite, a lay appraisal summary backed by evidence spans, and the two invented metrics. Licence status matters more than code quality, because the projects closest to ResearchBridge's purpose are AGPL, unlicensed or non-commercial. The evidence also narrows every open decision, and it corrects one premise of §1.1: most of PubMed Central permits derivatives, but only about a tenth of arXiv does.

## Inline explanation is a commodity, but no one serves lay readers the full bundle

LLM explanation of a confusing passage is now a free, mass-market feature. Explainpaper offers unlimited highlight explanations free and a $16/month Pro tier ([Explainpaper](https://www.explainpaper.com/)). SciSpace explains highlighted text, equations, tables and figures, and claims 6 to 9.6 million users ([Labcritics](https://labcritics.com/tools/scispace/); [SciSpace Enterprise](https://scispace.com/enterprise)). Google PAIR's **Lumi** places AI summaries in the margins of arXiv papers and is open source, though this research did not verify its licence ([PAIR-code/lumi](https://github.com/pair-code/lumi)). Lumi's users have asked for a paragraph-by-paragraph translation of the full text, so even the most reading-focused open tool lacks a full rewrite ([Lumi issue #107](https://github.com/PAIR-code/lumi/issues/107)).

The well-funded players are moving away from the lay reader. Elicit Reports, Consensus Deep, SciSpace Agent, and alphaXiv's "Autoresearch" and MCP server all serve professionals doing literature review ([Elicit](https://elicit.com/blog/series-a); [alphaXiv](https://www.alphaxiv.org/); [SiliconANGLE](https://siliconangle.com/2025/11/19/alphaxiv-raises-7m-funding-become-github-ai-research/)). The 2026 roundups of summarizers name no tool built for general readers ([unite.ai](https://www.unite.ai/best-ai-research-paper-summarizers/); [Paperguide](https://paperguide.ai/blog/ai-research-paper-summarizers/)).

**Paper Plain is the closest prior art, and its user study is the most useful evidence the project has.** It gave non-experts reading medical papers three aids: definitions of terms, plain-language "gists" of sections, and guiding questions linked to the passages that answer them. Readers found papers easier to read **with no loss of comprehension**. They used passage summaries more than definition tooltips, and they cross-checked summaries against the source because the summaries could be vague. The design lesson was to supplement the original text rather than replace it ([August et al., arXiv 2203.00130](https://arxiv.org/pdf/2203.00130)). That directly supports ResearchBridge keeping the original alongside the rewrite. As a source of code, though, it is a dead end. The repository has no licence, the UI was never released, and the last push was in February 2022 ([allenai/paper-plain](https://github.com/allenai/paper-plain)).

Human-written lay summaries set the quality bar but cover only a sliver of the literature. eLife digests average 347 words, PNAS significance statements about 120, and Cochrane plain-language summaries 400–700 ([eLife](https://elifesciences.org/articles/25411); [eLife list](https://elifesciences.org/inside-elife/5ebd9a3f/plain-language-summaries-journals-and-other-organizations-that-produce-plain-language-summaries)).

Human annotation venues are mature but niche, and each survives on a committed group of contributors. Hypothesis has published milestones of 7 million and then 20 million annotations, mostly from education, yet appeared in only 0.3% of CU Boulder's Canvas courses ([Hypothesis](https://web.hypothes.is/blog/our-view-from-20-million-annotations/); [CU Boulder OIT](https://oit.colorado.edu/services/consulting-professional-services/academic-technology-initiatives-team/needs-assessments/social-annotation-tools)). More than two-thirds of PubPeer's comments report misconduct ([JASIST 2022](https://ideas.repec.org/a/bla/jinfst/v73y2022i5p655-670.html)). Fermat's Library curates a weekly annotated journal club ([Fermat's Library](https://fermatslibrary.com/journal_club)). Genius tried to annotate the open web. It ran into a 2016 harassment controversy, partly because site owners could not opt out, and later moved its emphasis from annotation to video ([Daily Dot](https://dailydot.com/?p=108098); [pxlnv citing The Verge](https://pxlnv.com/linklog/genius-will-de-emphasize-web-annotations-in-favour-of-video/)).

In the table, "Y" marks a documented core feature, "~" a partial one, and "–" means none was found. The feature columns refer to ResearchBridge's planned features: F1, the full plain-English rewrite; F2, inline explanations, whether LLM- or human-written; F3, the structured summary, here its coverage of limitations and conflicts of interest (COI); F4, credibility and impact metrics; and F5, the per-paper discussion thread.

| Product | Audience | F1 full rewrite | F2 LLM inline | F2 human inline | F3 limitations/COI | F4 metrics | F5 discussion | Status, Oct 2026 |
|---|---|---|---|---|---|---|---|---|
| Explainpaper | Researchers | – | Y | – | – | – | – | Live; activity unconfirmed |
| SciSpace | Researchers, students | – | Y | – | – | – | – | Active |
| alphaXiv | AI/ML engineers | – | Y | ~ | – | ~ | Y | Active, $7M seed |
| Lumi (Google PAIR) | arXiv readers | – | Y | – | – | – | – | Open source, demo live |
| Paper Plain (AI2) | **Lay readers** | – | Y | – | – | – | – | Prototype only |
| Semantic Scholar | Researchers | – | ~ | – | – | Y | – | Reader still beta |
| Elicit / Consensus | Researchers | – | – | – | ~ | ~ | – | Active, VC-backed |
| Hypothesis / Fermat's Library | Educators / scientists | – | – | Y | – | – | Y | Active, niche |
| PubPeer | Integrity sleuths | – | – | ~ | ~ | – | Y | Active |

The table draws on the product sources cited above, the [Semantic Reader platform](https://openreader.semanticscholar.org/) and [PitchBook's alphaXiv profile](https://pitchbook.com/profiles/company/770062-33).

Four things are left unclaimed: the faithful side-by-side rewrite (F1), a summary that systematically covers limitations, conflicts of interest and statistical strength (F3), readability and burden scores (F4), and the lay audience itself.

That gap is both an opportunity and a warning. Every commercial product targets researchers at $10–50 a month, and the research found no documented paying lay market. That points toward a nonprofit or grant model like those of Ai2, Hypothesis and PREreview, which also fits §1.1's caution about non-commercial (NC) licences.

## The licence gate keeps 5.4 million PMC papers but only a tenth of arXiv

§1.1 says "arXiv, PubMed Central, PLOS and DOAJ are millions of papers, most under CC-BY." That holds for PMC and PLOS but not for arXiv or DOAJ.

| Source | Rewrite-eligible (CC BY, CC BY-SA, CC0) | Display-only, non-commercial or excluded | Source |
|---|---|---|---|
| Europe PMC full text | 5,336,633 CC BY + 60,833 CC0 + 3,512 CC BY-SA ≈ **5.4M** | 1.1M CC BY-NC-ND (display-only); 1.3M CC BY-NC or BY-NC-SA | [Europe PMC REST](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=LICENSE:%22cc%20by%22%20AND%20OPEN_ACCESS:y%20AND%20IN_EPMC:y%20AND%20HAS_FT:y&format=json&pageSize=1) |
| arXiv (1.38M works tracked by OpenAlex) | about **216,000** | ~1.12M with no licence value, consistent with arXiv's default non-exclusive licence | [OpenAlex group_by](https://api.openalex.org/works?filter=primary_location.source.id:S4306400194&group_by=primary_location.license) |
| bioRxiv (sample of 2,007 recent preprints) | about **30%** | 33% display-only; 24.5% "no reuse" | [bioRxiv API](https://api.biorxiv.org/details/biorxiv/2025-09-01/2025-09-10/0) |
| DOAJ | not determinable | article records sampled had `license: null` and link to publisher HTML | [DOAJ API](https://doaj.org/api/search/articles/bibjson.title:cancer?pageSize=1) |

NC-ND is the largest non-commercial category in PMC, and it is display-only. The §1.1 licence table therefore needs an explicit NC-ND row. For arXiv, the Common Pile's pre-filtered set counts **304,048** permissively licensed papers, against arXiv's own count of "over 2 million" ([Common Pile card](https://huggingface.co/datasets/common-pile/arxiv_papers_filtered/blob/refs%2Fpr%2F1/README.md); [arXiv](https://info.arxiv.org/about/accessible_HTML.html)). arXiv's terms forbid storing and serving e-prints whose licence does not permit it ([arXiv API ToU](https://info.arxiv.org/help/api/tou.html)). Papers under the default licence are therefore excluded even from display, leaving roughly 10–15% of arXiv usable. DOAJ is a discovery layer, not a source of per-article licences.

The gate is checkable, as §1.1 claims, but only if each licence is read from the right field, and several sources changed recently. In the week of 24 August 2026, PMC removed its FTP article datasets, its OA Web Service API and the `oa_comm`/`oa_noncomm` file lists. Any tutorial or library built on those is now broken. The authoritative route is the per-article `s3://pmc-oa-opendata` bucket, whose JSON carries a `license_code` ([PMC Cloud Service](https://pmc.ncbi.nlm.nih.gov/tools/cloud/); [PMC Cloud README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)). A code of `TDM` is not a reuse licence. It marks author manuscripts that may only be text-mined under fair use. At arXiv, the Atom API returns no licence at all, but the OAI-PMH `arXiv` format does ([arXiv OAI-PMH](https://oaipmh.arxiv.org/oai?verb=GetRecord&identifier=oai:arXiv.org:2310.06825&metadataPrefix=arXiv); [arXiv Atom](https://export.arxiv.org/api/query?id_list=2310.06825)). Among aggregators, OpenAlex counts CC BY-NC-ND as "open", so aggregators can serve only as secondary signals ([OpenAlex help](https://help.openalex.org/hc/en-us/articles/41193820509079-What-is-an-OA-license)).

Two further traps mean §1.1 has to track licences below the paper level. First, JATS4R guidance says a figure reproduced under another licence carries its own `<permissions>` element, which overrides the article licence ([JATS4R](https://jats4r.niso.org/permissions/)). Second, some JATS files contain only human-readable `<license-p>` text, as one Europe PMC file did when checked live ([Europe PMC fullTextXML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10009416/fullTextXML)).

The schema should therefore record five things for each article version: the licence URI, the field it came from, the retrieval date, the version identifier, and any per-figure or per-table overrides. Licence fields should be read in order of precedence: PMC `license_code` first, then Europe PMC `license`, then JATS `ali:license_ref`, then arXiv OAI-PMH, then the bioRxiv API. Licences that exist only as prose should go to human review.

The PMC bucket terms add four operating duties: acknowledge NLM, redistribute only licensed data, keep it current, and act on `is_retracted`. One general point about Creative Commons licences was not re-verified here: a rewrite of a CC BY-SA paper must itself be released under BY-SA. So the licence field determines the licence of the output, not only whether a rewrite is permitted.

The format choice follows from the licence choice. PMC and PLOS JATS XML and arXiv's native LaTeXML HTML give clean sections and paragraphs without PDF parsing. arXiv has backfilled HTML even for papers from 2017 ([arXiv HTML 1706.03762](https://arxiv.org/html/1706.03762)).

The permissive, maintained ingestion stack is as follows. Treat the PDF tools as a fallback for bioRxiv and for DOAJ journals without XML.

| Role | Tool | Licence |
|---|---|---|
| JATS XML (PMC, PLOS) | pubmed_parser | MIT |
| PLOS bulk download | allofplos | MIT |
| arXiv LaTeX to HTML | LaTeXML | Public domain |
| arXiv HTML | ar5iv | MIT |
| PDF fallback | GROBID | Apache-2.0 |
| PDF fallback | Docling | MIT code, Apache-2.0 models |
| PDF fallback | olmOCR | Apache-2.0 code and weights |

Sources: [pubmed_parser](https://github.com/titipata/pubmed_parser); [allofplos](https://github.com/PLOS/allofplos); [LaTeXML](https://github.com/brucemiller/LaTeXML); [GROBID](https://github.com/grobidOrg/grobid); [Docling](https://github.com/docling-project/docling); [olmOCR](https://github.com/allenai/olmocr).

Corpora such as S2ORC and Common Pile help bootstrap lists of paper IDs. S2ORC is ODC-By but sits behind a Semantic Scholar API agreement that can be revoked. Neither corpus's dataset licence clears per-paper copyright, so every paper must still be re-verified at its primary source ([S2 API License](https://www.semanticscholar.org/product/api/license); [Common Pile paper](https://arxiv.org/pdf/2506.05209)).

## Feature by feature, the infrastructure is permissive and maintained but the core is not

The same pattern holds for every feature. The infrastructure layer has a healthy permissive option. The layer that makes the feature *ResearchBridge's* has either nothing to reuse, or only research code that is unlicensed or copyleft.

| Feature | Reuse as code (permissive, maintained) | Reference only (blocked by licence or staleness) | Must build |
|---|---|---|---|
| **F1 rewrite** | JATS/LaTeXML HTML as the alignment substrate; T5 simplifiers (Apache-2.0) as baselines only | PDFMathTranslate / BabelDOC (AGPL); Paper Plain notebooks (no licence); ChatPaper (CC BY-NC-ND) | Paragraph-aligned whole-paper rewrite with bounded added context, plus a faithfulness gate |
| **F2 inline (LLM)** | `@recogito/text-annotator` + `pdf-annotator` (BSD-3); Hypothesis client anchoring (BSD-2); pdf.js (Apache-2.0); PersonalizedJargon, definition-complexity (Apache-2.0) | ScholarPhi, PaperCraft (Apache-2.0, stale since 2023); Open Paper (AGPL); Lumi | A whole-document annotation pipeline that emits W3C quote selectors |
| **F2 inline (community)** | Hypothesis h server (BSD-2) for groups, flagging and pre-moderation; ResearchHub backend (MIT) for votes and reputation | Genius clones (portfolio code); Manifold, PubPub (GPL) | One canonical, editable explanation per passage, with vote ranking, revision history and reputation |
| **F3 summary** | PaperQA2 (Apache-2.0) for cited per-question extraction; JATS COI and funding tags; scrutiny (MIT) for GRIM checks | rtransparent (GPL-3, imports AGPL ODDPub); statcheck (GPL-3); RobotReviewer (GPL-3, dormant); BAGELS, LimGen (no licence) | Lay-facing limitations, COI, statistics and "strength of evidence" fields, each linked to its source span |
| **F4 credibility** | OpenAlex (CC0) via pyalex (MIT); Crossref + Retraction Watch; OpenCitations (CC0); iCite (public domain); DOAJ (CC0) | Semantic Scholar, SJR, scite, Altmetric, Dimensions (terms block commercial display) | Readability and prior-knowledge-burden scores; trend and caveat UI |
| **F5 discussion** | Remark42 (MIT), Coral (Apache-2.0), Isso (MIT) | Discourse (GPL-2, replies only off-page); Lemmy (AGPL); Giscus (GitHub login) | Moderation norms for a lay audience; optionally one data model for annotations and threads |

### F1 rewrite: the hardest feature has the least to reuse

No maintained open-source pipeline simplifies full scientific documents. Fine-tuned simplifiers such as `pszemraj/long-t5-tglobal-base-sci-simplify` (Apache-2.0, trained on PLOS lay summaries) handle abstract-length text at research quality. They are baselines, not engines ([HF model](https://huggingface.co/pszemraj/long-t5-tglobal-base-sci-simplify)).

The best structural analogue is **PDFMathTranslate** and its engine **BabelDOC**. They rewrite full papers while preserving layout, which is F1 with "plain English" in place of a target language. Both are **AGPL-3.0**, so copying their code into a hosted service would oblige ResearchBridge to publish its own source ([PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate); [BabelDOC](https://github.com/funstory-ai/BabelDOC)). ChatPaper's full-text summarisation code is CC BY-NC-ND and cannot be reused at all ([ChatPaper](https://github.com/kaixindelele/ChatPaper)).

The practical design rewrites paragraph by paragraph over JATS or LaTeXML HTML and keeps an alignment back to each source paragraph. That alignment drives the side-by-side view and also serves as the unit of faithfulness checking.

The real engineering is the faithfulness gate, because the documented failure modes are exactly what inspiration.md wants to avoid. LLMs overgeneralised scientific findings in up to 73% of summaries, about 4.85 times as often as expert human summaries ([Peters & Chin-Yee, PMC12042776](https://pmc.ncbi.nlm.nih.gov/articles/PMC12042776/)). Lay summaries of randomised controlled trials written by GPT-4 and Llama-2 added non-factual content in 31–38% of cases ([FactPICO](https://arxiv.org/html/2402.11456)). LLMs also carry spin forward from the original paper into their plain-language summaries ([Yun et al.](https://arxiv.org/abs/2502.07963)).

Peters & Chin-Yee also found that an explicit "be accurate" instruction increased overgeneralisation (OR 1.90). Temperature 0 cut the odds by about 76%, and Claude models were the only ones not significantly worse than the original abstracts. Model choice and decoding settings are levers to measure. Prompt wording alone is not a safeguard.

The "add 1–2 sentences of context" principle runs into a direct tension here. The models that avoided errors in the TREC PLABA track did so by being "conservative and cautious in gratuitous edits or information insertions" ([TREC PLABA NTU](https://trec.nist.gov/pubs/trec33/papers/ntu_nlp.plaba.pdf)). A check that rejects every added sentence will also reject legitimate context. The gate therefore has to classify additions, not forbid them.

### F2 inline explanations: anchoring is solved, proactive annotation is not

Anchoring and rendering are the best-served part of the stack under either annotation model. Annotations should be stored in the **W3C Web Annotation Data Model**: a TextQuoteSelector plus a TextPositionSelector, with a page index for PDFs ([W3C](https://www.w3.org/TR/annotation-model/)). An LLM then quotes the passage it is explaining, and the client anchors that quote with fuzzy matching.

Two libraries can do the anchoring. The most drop-in option is **`@recogito/text-annotator`** (BSD-3, v4.3.7 released 12 October 2026, with a React wrapper and a PDF package; [text-annotator-js](https://github.com/recogito/text-annotator-js); [npm pdf-annotator](https://www.npmjs.com/package/@recogito/pdf-annotator)). The Hypothesis client's anchoring modules (BSD-2) are more battle-tested on messy pages, but they are not packaged separately and would have to be extracted ([hypothesis/client anchoring](https://github.com/hypothesis/client/tree/main/src/annotator/anchoring)).

Avoid Apache Annotator, which left the Apache Incubator as a retired project on 11 August 2025 ([Incubator](https://incubator.apache.org/projects/annotator.html)). Rendering HTML first, from JATS or LaTeXML, avoids most of the complexity of overlaying annotations on PDFs. pdf.js (Apache-2.0, v6.4.299) remains the fallback for PDF-only papers ([pdf.js](https://github.com/mozilla/pdf.js)).

Reuse stops at the content layer. Kotaemon, PaperQA2 and Open Paper link answers back to source spans, but they are question-driven chat tools. **None generates annotations proactively across a whole paper**, which is what F2 needs. Only AI2's prototypes did that, and none of them is a usable dependency today. **ScholarPhi** is Apache-2.0, but its last commit was in March 2023 and its pipeline needs LaTeX compilation and PostgreSQL ([ScholarPhi](https://github.com/allenai/scholarphi)). **PaperCraft** has an overlay-layer design worth copying. It declares Apache-2.0 in npm, but the repository has no LICENSE file and its last commit was in November 2023 ([pdf-component-library](https://github.com/allenai/pdf-component-library)). **Open Paper**, the closest live product, explains selected text and builds grounded tables, but it is AGPL ([khoj-ai/openpaper](https://github.com/khoj-ai/openpaper)).

For deciding *what* to explain, two Apache-2.0 research repositories are available: Guo et al.'s PersonalizedJargon and August et al.'s definition-complexity. Guo et al. showed that how familiar a term is varies widely even within a subfield, and that zero-shot prompting is a strong baseline ([arXiv 2311.09481](https://arxiv.org/pdf/2311.09481)). One counterintuitive result belongs in the design: a GPT-4 pilot found definitions generated from the abstract alone slightly more accurate than definitions generated with retrieval over the full text ([Nishal et al., arXiv 2410.12069](https://arxiv.org/pdf/2410.12069)).

For the community variant, Hypothesis's server (`h`, BSD-2, pushed daily) already provides groups, flagging and pre-moderation ([Hypothesis pre-moderation](https://web.hypothes.is/help/pre-moderation-in-the-hypothesis-web-app/)). Self-hosting it means running PostgreSQL, Elasticsearch and RabbitMQ, and the research found no official statement that self-hosting is supported ([hypothesis/h](https://github.com/hypothesis/h)). More importantly, Hypothesis's model is many independent annotations with replies. It has no voting, no reputation and no community-edited canonical explanation.

**No maintained open-source "Genius for papers" exists.** The GitHub clones are abandoned portfolio projects that anchor annotations by raw character offsets ([samblyon/genius](https://awesome.ecosyste.ms/projects/github.com%2Fsamblyon%2Fgenius)). ResearchHub's MIT-licensed Django backend is a live production system for discussing papers, with votes and reputation, which makes it the best code donor for those mechanics. How tightly it is coupled to ResearchHub's token economy has not been checked ([researchhub-backend](https://github.com/ResearchHub/researchhub-backend)).

### F3 summary engine: cited extraction is reusable, appraisal heuristics are copyleft

**PaperQA2** (Apache-2.0, release v2026.08.12, 40+ contributors) is the strongest pipeline candidate. Its "re-ranking and contextual summarization" step scores each chunk against a question and returns answers with in-text citations ([paper-qa](https://github.com/Future-House/paper-qa)). Running a fixed set of questions over a single-paper index would yield a structured summary with evidence for each field. The questions would cover limitations, declared conflicts of interest, funding, sample and effect sizes, and whether a finding is causal or correlational.

The specialised appraisal tools are best used as validators. **rtransparent** extracts conflict-of-interest, funding and registration statements from PMC XML, and was validated across all of PMC open access. It is GPL-3 and imports **ODDPub**, which is AGPL-3.0, so it should run offline as a benchmark or be reimplemented clean-room ([rtransparent](https://github.com/serghiou/rtransparent); [oddpub](https://github.com/quest-bih/oddpub)). JATS already tags many such statements (`fn-type="COI-statement"`, `<funding-group>`), though how consistently was not verified.

**statcheck** (GPL-3) recomputes p-values, but only for APA-style reporting ([statcheck](https://github.com/MicheleNuijten/statcheck)). **scrutiny** (MIT) offers GRIM and DEBIT consistency checks ([scrutiny](https://github.com/lhdjung/scrutiny)). **RobotReviewer**'s risk-of-bias models are also GPL-3 and have been dormant since 2022 ([robotreviewer](https://github.com/ijmarshall/robotreviewer)). For limitations, only unlicensed research code exists, from BAGELS and LimGen. BAGELS's hybrid approach (detect the section, fall back to regex, then filter with an LLM) is a sensible template to reimplement ([BAGELS](https://arxiv.org/pdf/2505.18207)).

The LimTopic authors found that Science Parse missed many limitations sections nested inside other sections ([LimTopic](https://arxiv.org/pdf/2503.10658)). That is another argument for working from JATS structure rather than parsed PDFs. The spin finding argues for an explicit field asking whether the abstract claims more than the results show, since models detect spin when asked directly ([Yun et al.](https://arxiv.org/abs/2502.07963)).

### F4 credibility: a fully CC0 panel is buildable today

**OpenAlex** is the backbone. Its data is CC0, and looking up a single paper by DOI is free. Each work record carries the citation count (`cited_by_count`), citations per year (`counts_by_year`, enough for a sparkline), field-weighted citation impact (`fwci`), a citation percentile and a retraction flag (`is_retracted`). Each journal record lists the curated lists that include it (`listed_in`) ([OpenAlex Pricing](https://help.openalex.org/access/pricing/); [OpenAlex Citations](https://help.openalex.org/data/works/citations/); [OpenAlex Source lists](https://help.openalex.org/data/source-lists/)).

Other open sources complement it. **Crossref** exposes Retraction Watch notices in its REST API ([Crossref](https://www.crossref.org/blog/retraction-watch-retractions-now-in-the-crossref-api/)). **OpenCitations** (CC0) holds about 2.2 billion citations ([OpenCitations](https://download.opencitations.net)). **NIH iCite** (public domain) gives citations by year and the Relative Citation Ratio (RCR) for biomedical papers ([iCite API](https://icite.od.nih.gov/api/pubs?pmids=31581957)). **pyalex** is an MIT-licensed Python client for OpenAlex ([pyalex](https://github.com/J535D165/pyalex)).

OpenAlex changed its pricing model twice in 2026, and FWCI values moved with its topic reclassification on 6 October 2026. ResearchBridge should cache data from the free quarterly snapshot and show an "as of" date on every metric ([OpenAlex Snapshot](https://help.openalex.org/access/snapshot/); [OpenAlex blog](https://blog.openalex.org/author/jason)).

The familiar brand-name sources are blocked for a product that may become commercial. **Semantic Scholar**'s API licence prohibits "embedding or installing the API into products for Licensee's own commercial gain" ([S2 API License](https://api.semanticscholar.org/license)). **SCImago** requires prior written permission for any reproduction of its journal rankings ([SCImago](https://www.scimagojr.com/legal-notice.php)). **scite, Altmetric and Dimensions** all need paid contracts. **Crossref Event Data**, the last open altmetrics feed, shut down on 23 April 2026 ([Crossref](https://www.crossref.org/blog/strengthening-support-for-data-citations-and-saying-goodbye-to-event-data)).

The readability and burden scores have no product precedent. They are discussed under §2.4 below.

### F5 discussion: adopt a comment engine, or fold threads into annotations

Three comment engines are commercially safe and maintained. **Remark42** (MIT, v1.18.0) has built-in voting, pinning and moderation ([Remark42](https://github.com/umputun/remark42)). **Coral** (Apache-2.0) offers newsroom-grade moderation ([Coral LICENSE](https://github.com/coralproject/talk/blob/main/LICENSE)). **Isso** (MIT, SQLite) has a moderation queue ([Isso](https://github.com/isso-comments/isso)).

Discourse has the richest reputation system, but it is GPL-2 and readers cannot reply from the embedded widget ([Discourse Meta](https://meta.discourse.org/t/embed-discourse-comments-on-another-website-via-javascript/31963)). Giscus requires a GitHub account, which is wrong for a general audience.

A cleaner design models per-paper discussion as W3C annotations that target the whole document. Passage annotations, LLM explanations and paper-level threads would then share one data model and one moderation queue.

The cautionary evidence concerns engagement, not tooling. alphaXiv's discussion layer filled with bot comments, and the product pivoted toward AI features ([Medium review](https://medium.com/@joycebirkins/alphaxiv-an-evidence-based-ai-platform-for-precise-analysis-online-arxiv-paper-search-viewing-e9d66eff6b87)). Threads alone do not create a community.

## Copyleft code, non-commercial weights and unlicensed prototypes are the real traps

Licence risk splits four ways: code, model weights, datasets, and API or data terms. A project's GitHub licence often says nothing about the weights or data it depends on. The tiering below assumes ResearchBridge stays closed-source and keeps the paid-tier option that §1.1 contemplates.

| Risk tier | Code | Model weights | Data and APIs |
|---|---|---|---|
| **Safe: permissive, attribution only** | pdf.js, Recogito, Hypothesis h and client, PaperQA2, Kotaemon, open-notebook, GROBID, Docling, LaTeXML, ar5iv, pubmed_parser, Remark42, Coral, Isso, pyalex, ResearchHub backend, AlignScore, SummaC, QAFactEval, FActScore, scrutiny | Docling Heron and Granite-Docling (Apache-2.0), olmOCR-2 (Apache-2.0), MiniCheck RoBERTa/DeBERTa/Flan-T5 (MIT), Vectara HHEM (Apache-2.0), T5 sci-simplify (Apache-2.0) | OpenAlex, OpenCitations, DOAJ metadata (CC0); iCite (public domain); Crossref metadata; PLABA (CC0); FactPICO annotations (CC BY 4.0) |
| **Safe but stale: fork and own** | PaperMage, PaperCraft, ScholarPhi, react-pdf-highlighter, RRnlp, SciTLDR | — | — |
| **Obligations attached** | — | OpenScholar-8B (Llama 3.1 licence); Marker/Surya (OpenRAIL-M, free only under $5M funding or revenue); MinerU (attribution required for online services, plus commercial thresholds) | Retraction Watch (citation requested, no explicit licence); PMC bucket (acknowledge NLM, keep data current) |
| **Copyleft: run unmodified or offline** | GPL: rtransparent, statcheck, RobotReviewer, Discourse, Manifold, PubPub | — | — |
| **AGPL: network use triggers source disclosure** | Open Paper, PDFMathTranslate, BabelDOC, ODDPub, Lemmy, OpenReview-web, CERMINE | MinerU2.5 VLM (tagged AGPL-3.0) | — |
| **Non-commercial or no-derivatives** | ChatPaper (CC BY-NC-ND) | Bespoke-MiniCheck-7B (CC BY-NC), Nougat (CC BY-NC) | LLM-AggreFact (CC BY-ND); Semantic Scholar API; SCImago SJR; Altmetric and Dimensions free tiers |
| **No licence: no reuse rights** | Paper Plain, Scim, BAGELS, LimGen, LENS, Devaraj factuality code, pdf.js-hypothes.is | — | MedReadMe data; Cochrane and SciNews text (third-party copyright despite CC-BY tags) |

Key sources for the weights and data rows: [Marker README](https://github.com/datalab-to/marker); [MinerU LICENSE](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md); [Bespoke-MiniCheck-7B](https://huggingface.co/bespokelabs/Bespoke-MiniCheck-7B); [LLM-AggreFact](https://huggingface.co/datasets/lytang/LLM-AggreFact); [OpenScholar-8B](https://huggingface.co/OpenSciLM/Llama-3.1_OpenScholar-8B); [Cochrane permissions](https://cochranelibrary.com/en/help/permissions); [MedReadMe](https://github.com/chaojiang06/medreadme).

**The projects most like ResearchBridge are disproportionately the risky ones.** Open Paper is the closest live analogue to F2 and F3. PDFMathTranslate is the closest analogue to F1. Paper Plain is the closest analogue to the whole concept. None of them can donate code.

**A permissive code licence often hides a restriction on weights or data.** Nougat's code is MIT, but its weights are non-commercial. MiniCheck's code is Apache-2.0, but its best 7B checkpoint is CC BY-NC. Marker's code is Apache-2.0, but its weights stop being free above $5M in funding or revenue. CELLS's repository is MIT, but its underlying journal text has mixed copyright ([CELLS repo](https://github.com/LinguisticAnomalies/pls_retrieval)).

Two safe-looking projects still deserve a recorded licence review before shipping. GitHub labels the Hypothesis client "NOASSERTION" because it bundles MIT subcomponents under BSD-2 ([client LICENSE](https://github.com/hypothesis/client/blob/main/LICENSE)). PaperCraft declares Apache-2.0 in npm but has no LICENSE file.

The same discipline applies to the paper corpus. The weakest point in an otherwise careful posture would be a figure inside a CC BY paper that carries its own, more restrictive permissions.

## The evidence settles parts of every open decision

### §2.1 annotation model: the evidence favours LLM-first, with a neutral data model

On perceived quality, LLM explanations already match or beat human ones. In a blinded Cochrane trial, ChatGPT-4o plain-language summaries were judged "submittable" 64% of the time, against 36% for human ones ([PMC12302524](https://pmc.ncbi.nlm.nih.gov/articles/PMC12302524/)). In a field deployment on X, LLM-written Community Notes received significantly higher helpfulness ratings than human notes on the same posts, across 108,169 ratings ([arXiv 2604.02592](https://arxiv.org/abs/2604.02592)).

On comprehension and faithfulness, humans still win in the best-controlled studies. Human-written plain-language summaries produced significantly better multiple-choice comprehension than GPT-4 versions, even though the GPT-4 versions scored better on readability formulas ([Guo et al., arXiv 2505.10409](https://arxiv.org/html/2505.10409v1)). Expert summaries did not overgeneralise relative to the original papers, while LLM summaries did, at 4.85 times the rate ([PMC12042776](https://pmc.ncbi.nlm.nih.gov/articles/PMC12042776/)).

No study compares Genius-style community explanations of scientific passages with LLM explanations. The record of community annotation (Genius's retreat, Hypothesis's low adoption, PubPeer's capture by misconduct reporting) shows that cold start and moderation are documented costs, not hypothetical ones.

The evidence supports shipping **option (b), LLM annotation, as the product**. Store every annotation in the W3C model with `creator` set to the model, so that human annotations can be added later without a migration. This is not the "may coexist" hybrid that §2.1 warns against. A neutral schema costs nothing, and the second cost structure only begins once public write access opens.

If human contribution is wanted, the Fermat's Library pattern fits best: a small, curated set of featured papers verified by recruited experts. LLM highlight-explain is a free commodity, so the defensible advantage is a *measured, published faithfulness score*, which no vendor offers ([HKUST Library](https://library.hkust.edu.hk/sc/trust-ai-lit-rev/)). That makes §2.2 the moat, not community annotation.

### §2.2 faithfulness benchmark: nearly every ingredient is open and permissive

The benchmark can be assembled almost entirely from permissive parts. **eLife and PLOS articles with expert lay summaries** (Hugging Face card: CC-BY-4.0) supply long-form full text that closely matches ResearchBridge's input ([HF scientific_lay_summarisation](https://huggingface.co/datasets/tomasg25/scientific_lay_summarisation)). **PLABA** (CC0) adds sentence-aligned gold adaptations and TREC's manual factuality protocol ([OSF](https://api.osf.io/v2/nodes/rnpmf/); [TREC PLABA lessons](https://arxiv.org/abs/2507.14096)). **FactPICO**'s expert-annotated summaries (CC BY 4.0) are a ready-made set for calibrating an LLM judge.

The evidence on automatic metrics is sobering. Natural-language-inference (NLI) and question-answering (QA) checkers reach only Kendall τ ≈ 0.15–0.29 against expert judgements of individual summaries. A GPT-4 rubric judge reached 0.475 ([FactPICO](https://arxiv.org/html/2402.11456)). AlignScore and SummaC reward output that copies the source: in BioLaySumm 2025, the system with the best factuality score wrote at a Flesch-Kincaid grade level of 16.45 ([BioLaySumm 2025](https://aclanthology.org/2025.bionlp-1.31)). These metrics can also be optimised directly, so they can be gamed ([ACL Anthology](https://aclanthology.org/people/sicheng-shen)).

A practical stack has three layers: a cheap NLI pass using AlignScore or one of MiniCheck's MIT-licensed checkpoints; a QA-based check with QAFactEval (BSD-3), the only automatic metric that predicted reader comprehension in Guo et al.; and a rubric judge that scores each claim separately, validated against human raters.

The rubric should code each failure type separately: Peters's three generalisation shifts (quantified to generic, past to present tense, descriptive to action-guiding), loss of certainty or hedging, drift from correlation to causation, spin, substituted numbers or populations, dropped limitations, and **added information labelled factual or non-factual**. That last code is what lets legitimate context pass.

Crisp binary codes reached inter-rater agreement of κ 0.79–0.95. Fine-grained judgements about insertions reached only α ≈ 0.43 ([Devaraj et al.](https://aclanthology.org/2022.acl-long.506)). The rubric should therefore be decomposed into binary or ordinal checks.

The benchmark should include a human-written explanation arm and lay comprehension questions on the same passages. That is the only design that settles §2.1 with data, as decisions.md asks. Lay raters are good at measuring comprehension but not faithfulness: Guo et al. discarded 66% of their crowd annotations. Do not use Bespoke-MiniCheck-7B outputs commercially, and do not redistribute anything derived from LLM-AggreFact.

### §2.3 credibility scoring: show attributed positives and facts, never verdicts

Every surviving product presents credibility as attributed, relative, positive tags. Consensus labels journals "Rigorous" using SciScore, and caveats its "highly cited" tag with "does not necessarily mean its results are any more valid" ([Aaron Tay](https://aarontay.substack.com/p/a-2025-deep-dive-of-consensus-promises)). OpenAlex calls its journal lists "deliberately non-normative" ([OpenAlex Source lists](https://help.openalex.org/data/source-lists/)). DOAJ retired its own Seal in April 2025 because readers misread it as a mark of prestige ([DOAJ blog](https://blog.doaj.org/2025/04/09/our-metadata-changes-are-live-and-the-seal-has-been-retired)).

The precedent for negative lists is grim. Beall took down his list in 2017 under "intense pressure" from his employer after sustained harassment by publishers ([GWU guide quoting Beall](https://guides.himmelfarb.gwu.edu/PredatoryPublishing/Beall)). Finland's JUFO, an accountable public body, partly reversed its bulk downgrade of MDPI and Frontiers journals after objections ([Retraction Watch](https://retractionwatch.com/2024/12/24/finland-publication-forum-will-downgrade-hundreds-of-frontiers-and-mdpi-journals)).

The answer to §2.3 combines its first two options, built entirely on CC0 or public-domain data. Show neutral facts: citations, citation trend, the FWCI percentile phrased as "top 10% in its field and year", recency, and retraction or expression-of-concern status attributed to the journal and Retraction Watch. Add attributed positive list membership, such as "Listed in DOAJ · Indexed for MEDLINE · CWTS Core". Absence from a list must never be shown as a negative.

Integrity screeners such as statcheck, GRIM and tortured-phrase detectors produce probabilistic accusations about named authors. They should stay internal, used only to triage papers. A defamation review for the relevant jurisdiction, particularly Canada, was out of scope here and remains a prerequisite for any negative label.

### §2.4 readability and burden metrics: define them against comprehension, not formulas

No product offers per-paper readability or prior-knowledge scores, so these remain genuinely original. The evidence is clear about what not to build. Flesch-Kincaid-style formulas correlate poorly with how difficult lay readers actually find a text ([Zheng & Yu, JMIR 2017](https://jmir.org/2017/3/e59/PDF)). In Guo et al., summaries with better formula scores produced worse comprehension ([arXiv 2505.10409](https://arxiv.org/html/2505.10409v1)).

Jargon is the more promising signal. Adding a single feature, the count of jargon spans, noticeably improved how well readability formulas matched human judgements ([MedReadMe, arXiv 2405.02144](https://arxiv.org/abs/2405.02144)). A De-Jargonizer study of 5,000 PLOS papers found that jargon made up 14% of words in abstracts but 10% in the matching lay summaries ([PMC5549884](https://pmc.ncbi.nlm.nih.gov/articles/PMC5549884)).

A defensible first version of the burden score combines three parts. The first is **jargon density** computed from word frequencies in an open news corpus, which would be a reimplementation because De-Jargonizer has no code licence. The second is **a MedReadMe-style span detector**; MedReadMe's data is unlicensed, so ask the authors before using it. The third is **a reader-profile adjustment** from PersonalizedJargon (Apache-2.0).

Validate the score against lay comprehension questions on the §2.2 passages, so one human study serves both decisions. One finding should shape the definition: "somewhat familiar" readers comprehended best, and self-described experts scored lowest. Prior knowledge does not map one-to-one onto understanding.

## Conclusion

ResearchBridge's risk is not missing infrastructure. Its risk is that the infrastructure is so readily available that the team builds the easy two-thirds first and treats the faithful core as polish.

The benchmark should come first. LLM highlight-explain is a commodity, and no one in the category publishes a faithfulness score, so the §2.2 benchmark is a product asset, not just a de-risking step. It is cheap to build from CC0 and CC-BY parts, it settles §2.1 empirically, and a published result is the one differentiator a well-funded incumbent cannot copy overnight.

The licence gate makes ResearchBridge a biomedical product at launch. The §1.1 gate is right, but it keeps about 5.4 million PMC papers while shrinking arXiv to about a tenth. ResearchBridge will therefore launch as a biomedical and life-science reader whether or not that was intended. That should also set the first benchmark domain, since the open evaluation data is mostly biomedical too.

Every reusable layer has a permissive option, but the licence traps cluster in exactly the projects that most resemble ResearchBridge. No code should be copied until it has been checked against a recorded licence inventory. Two pieces of genuinely new engineering remain, neither of which any open project has done in maintained form: whole-document, passage-anchored LLM annotation, and a paragraph-aligned rewrite whose added context is classified rather than forbidden.
