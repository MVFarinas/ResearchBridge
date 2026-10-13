# Commercial and Free Products for Helping Non-Experts Read Scientific Papers (Competitive Landscape for ResearchBridge)

Scope note: research conducted 2026-10-13. Prices and user counts below are mostly company-reported or from third-party aggregators that disagree with each other; these are flagged where they conflict. ResearchBridge feature numbering used throughout: F1 = full-paper plain-English rewrite; F2 = original paper with inline explanations (community or LLM); F3 = structured summary (findings, implications, significance, limitations, COI, practical relevance); F4 = credibility/impact metrics (citations, journal quality, recency, readability, prior-knowledge burden); F5 = per-paper discussion thread.

## Q1. Which products do LLM-based paper explanation / simplification / "explain this passage" today?

### Takeaway
"Highlight a passage and get an LLM explanation" is now a commodity feature, offered free or cheaply by Explainpaper, SciSpace, alphaXiv, Google PAIR's Lumi and many chat-with-PDF tools. Almost all of them market to researchers and students rather than the lay public. None found does a faithful, full-paper plain-English rewrite as a primary product. Lumi is open source.

### Cited Findings

**Explainpaper** (highlight-to-explain reader)
- Positions itself as "Read Research Papers 10x Faster". You highlight a confusing passage and get an explanation at adjustable complexity, in 50+ languages, that takes the surrounding paper into account. It also has chat-with-paper with section citations, plus outlines and key-point extraction — [Explainpaper homepage](https://www.explainpaper.com/)
- Pricing: Free ($0) has unlimited highlight explanations on basic models. Pro ($16/month) adds advanced models, whole-paper summaries, saved highlights, paper Q&A and "Math Explain" — [Explainpaper homepage](https://www.explainpaper.com/); same $16 figure in [SciSpace vs ChatPDF comparison / aggregator search results](https://www.aitoolsmentor.com/tool/scispace)
- Traction claim: "Join 400,000+ researchers" (unverified marketing). The only date on the site is "© 2025", and there is no changelog, so we cannot confirm it was actively developed in 2026 — [Explainpaper homepage](https://www.explainpaper.com/)
- Audience: its testimonials come from AI/ML researchers and people new to complex fields, so it is aimed at researchers rather than the lay public — [Explainpaper homepage](https://www.explainpaper.com/)

**SciSpace (formerly Typeset) — "Copilot" / AI chat, Chrome extension, Agent**
- Its central feature: highlight a passage, equation, table or figure in a PDF, get a plain-language explanation, and ask follow-ups grounded in the same document — [Labcritics](https://labcritics.com/tools/scispace/)
- A Chrome extension adds highlight-and-"explain" on web pages. Math and table snipping works only in PDFs — [SciSpace Copilot extension page](https://scispace.com/resources/scispace-copilot-chrome-extension/)
- "Copilot" is an older brand name for what is now the AI chat feature — [Effortless Academic 2026 review](https://effortlessacademic.com/scispace-an-all-in-one-ai-tool-for-literature-reviews/)
- A 2026 roundup describes it as a "reading tutor" that explains sections, defines terms, simplifies methodology and clarifies equations in real time — [Paperguide roundup](https://paperguide.ai/blog/ai-research-paper-summarizers/) (vendor blog; competitor of SciSpace)
- Pricing is inconsistent across sources. One says credit-based Agent plans (Free 100 credits, Premium 1,200, Advanced 10,000, Max 40,000) with Premium about $20/mo, Advanced $90/mo, Max $200/mo. Others say Premium $12/mo and Teams $20/user/mo — [aitoolsmentor](https://www.aitoolsmentor.com/tool/scispace); [aisotools](https://aisotools.com/pricing/scispace); official page: [SciSpace pricing](https://scispace.com/pricing)
- Traction (company-reported, inconsistent): "6 million users" as of Nov 2025 per its careers listing, and "9.6 Million+ researchers" on its enterprise page — [Wellfound/SciSpace careers](https://wellfound.com/company/typeset); [SciSpace Enterprise](https://scispace.com/enterprise)

**alphaXiv** (arXiv overlay: comments plus an AI assistant)
- It has an AI assistant that analyzes highlighted passages, private notes and similar-paper discovery. Community likes and comments remain. One reviewer said many comments in the earlier version were bot-posted — [Medium review of alphaXiv](https://medium.com/@joycebirkins/alphaxiv-an-evidence-based-ai-platform-for-precise-analysis-online-arxiv-paper-search-viewing-e9d66eff6b87)
- Raised a $7M seed (co-led by Menlo Ventures and Haystack, Nov 2025) to become "the GitHub of AI research". Its stated audience is engineers turning academic discoveries into AI features. It claims "millions of users" — [SiliconANGLE](https://siliconangle.com/2025/11/19/alphaxiv-raises-7m-funding-become-github-ai-research/)
- A Medium post claims a $70M raise, but it is unverified and contradicted by PitchBook's $7M — [Medium claim](https://medium.com/@writertripathi/alphxiv-just-raised-70m-and-it-validates-why-i-built-paper-route-c2c8c7f2daa7); [PitchBook](https://pitchbook.com/profiles/company/770062-33)
- The homepage (fetched Oct 2026) now leads with "grounding its answers in the underlying work". Its navigation shows "Grounded literature review", "Autoresearch", "MCP Server", "Browser Extension" and "Publish". Paper listings show one-sentence finding summaries and view counts. Pricing is not shown — [alphaXiv homepage](https://www.alphaxiv.org/)
- PitchBook describes it as an open discussion platform with line-by-line commenting and side-by-side viewing — [PitchBook](https://pitchbook.com/profiles/company/770062-33)

**Lumi (Google PAIR / DeepMind) — open source**
- An open-source tool that helps people read arXiv papers. It offers AI-augmented annotations with summaries at multiple levels of detail, "smart highlights" you can query, and figure explanations — [GitHub PAIR-code/lumi](https://github.com/pair-code/lumi)
- Puts short AI summaries in the side margin next to the original text and links references to the exact cited sentence. There is a live demo at lumi.withgoogle.com — [Towards Data Science](https://towardsdatascience.com/reading-research-papers-in-the-age-of-llms/); [Hacker News thread](https://news.ycombinator.com/item?id=45737196)
- Users have requested paragraph-by-paragraph full-text translation (GitHub issue #107), which suggests it does not offer a full-text rewrite — [Lumi issue #107](https://github.com/PAIR-code/lumi/issues/107)

**Semantic Scholar (Ai2): TLDRs, Semantic Reader, Paper Plain, ScholarPhi**
- TLDRs: about 20-word AI summaries of a paper's main objective and results. Beta launched Nov 2020, later covering about 60M papers in CS, biology and medicine. Shown in search results and on paper pages, and available via API — [Semantic Scholar TLDR page](https://www.semanticscholar.org/product/tldr); [CASRAI guide](https://www.casrai.org/guides/semantic-scholar)
- Semantic Reader: augments PDF reading with inline citation context, definition lookup and related work. It is still labeled beta — [Educators Technology review, Sep 2026](https://www.educatorstechnology.com/2026/09/semantic-scholar-review.html)
- Paper Plain (research prototype, ACM TOCHI 2023, presented at CHI 2024): built for non-experts reading medical papers. It offers in-situ term definitions, AI plain-language "gists" of passages, and key questions to guide lay readers. **This is the closest prior art to ResearchBridge F2.** The project site lists it as a prototype with a demo, not a product. CiteSee and Scim are "In-Production" — [Semantic Reader project paper (arXiv 2303.14334)](https://www.arxiv.org/pdf/2303.14334); [Semantic Reader Open Research Platform](https://openreader.semanticscholar.org/)
- ScholarPhi: "drill-down" definitions of math symbols and terms shown over the text. Also a prototype — [Semantic Reader Open Research Platform](https://openreader.semanticscholar.org/)
- Open-source components: PaperMage (scholarly PDF processing library, EMNLP 2023) and PaperCraft (React UI components for augmented reading interfaces) — [Semantic Reader Open Research Platform](https://semantic-reader-open-platform.vercel.app/)

**Elicit** (evidence synthesis; researcher-focused)
- Raised a $22M Series A on Feb 26, 2025 at a $100M valuation (Spark Capital, Footwork) and launched "Elicit Reports". At that time it reported 400k+ monthly researchers — [Elicit blog](https://elicit.com/blog/series-a); [Elicit on X](https://x.com/elicitorg/status/1894772293752266846)
- Its careers page (undated) claims 2M+ researchers. It is a Public Benefit Corporation — [Elicit careers](https://elicit.com/careers); [Elicit $9M PBC post](https://elicit.com/blog/elicit-raises-9-million-and-becomes-a-public-benefit-corporation)
- Pricing conflicts across aggregators. One lists Basic free, Plus $12, Pro $49, Team $79/user/mo. Another lists Pro $49, Scale $169 and Enterprise. A third lists academic tiers at $19/$69/$149 per month — [Paperguide](https://paperguide.ai/blog/elicit-vs-consensus/); [aiproductivity.ai](https://aiproductivity.ai/pricing/elicit/); [costbench](https://costbench.com/software/ai-research-tools/elicit/)

**Consensus** (AI academic search engine that answers questions from papers)
- Raised an $11.5M Series A (Union Square Ventures) in Aug 2024, with 400k+ MAU and about $1.5–2M annualized revenue at the time — [Bloomberg](https://www.bloomberg.com/news/articles/2024-08-14/consensus-nabs-11-million-to-build-ai-search-tool-for-academics); [MobiHealthNews](https://www.mobihealthnews.com/news/consensus-raises-115m-ai-research-engine-scientific-papers)
- Later announced $30M in new funding and "2.5M researchers start their work with Consensus every month" (the X post is undated in search results) — [Consensus on X](https://x.com/ConsensusNLP/status/2053863836613005543); [Tracxn](https://tracxn.com/d/companies/consensus/__WfH-QwhS9-s-sqDaImlN8S11KPpemxLaqZoQreCJfiU)
- Pricing conflicts. One source lists Pro $10/mo and Deep $45/mo. A Sep 2026 source lists Pro $20/mo ($144/yr) and Deep $65/mo ($540/yr) — [aitoolradar](https://www.aitoolradar.net/compare/elicit-vs-consensus); [decidenavigator](https://decidenavigator.com/compare/consensus-vs-elicit)

**Scholarcy, SciSummary, Paperguide** (summarizers)
- Scholarcy produces flashcard-style summaries of key claims, methodology, findings, references and tables. SciSummary (since 2023) summarizes articles "without having to read the full text" — [Paperguide roundup](https://paperguide.ai/blog/ai-research-paper-summarizers/); [SciSummary](https://scisummary.com/)
- The 2026 roundups pitch these tools at students and researchers, and none is described as built for general readers — [unite.ai roundup Oct 2026](https://www.unite.ai/best-ai-research-paper-summarizers/); [Paperguide roundup](https://paperguide.ai/blog/ai-research-paper-summarizers/)

**Generic "chat with documents" tools: Humata, ChatPDF, NotebookLM**
- Humata (per a March 2026 review): free plan up to 60 pages, Student $1.99/mo, Expert $9.99/mo, Team $49/user/mo, with OCR on Team. Toolradar gives wildly different numbers ($199/$999), so this is unresolved — [ComputerTech review](https://computertech.co/humata-ai-review); [Toolradar](https://toolradar.com/tools/humata/pricing)
- ChatPDF: free basic use. Paid tier said to be around $5–10/mo (unsourced) — [aipicks.jp](https://aipicks.jp/tool/chatpdf/pricing)
- NotebookLM Audio Overviews turn papers into AI "podcasts". Google's help page says they "may contain inaccuracies" — [Futurity](https://www.futurity.org/ai-generated-podcasts-3323312/); [TechRadar review](https://www.techradar.com/pro/notebooklm-review)

**Iris.ai** (enterprise R&D)
- Oslo-based "AI science assistant" for R&D departments. Closed an almost-€8M Series A (June 2024) and was still active in 2025 (new CRO in May 2025, 10-year post in Dec 2025). It is enterprise-focused, not lay — [Iris.ai](https://iris.ai/category/journey); [PitchBook](https://pitchbook.com/profiles/company/162774-19)

**Human-written lay summaries (journals and services; non-LLM baseline)**
- eLife digests: in research articles since 2012. Over 2,400 published at the time of the article, averaging 347 words. They explain background and significance for outsiders. Authors answer plain-language questions to help eLife's writers — [eLife "Plain-language summaries: Something for everyone"](https://elifesciences.org/articles/25411); [eLife inside guide to digests](https://elifesciences.org/articles/25410)
- eLife keeps a list of 50+ journals and organizations producing plain-language summaries, including PNAS Significance Statements (~120 words), Cochrane plain-language summaries (400–700 words), Autism lay abstracts and PLOS Medicine author summaries (6–9 bullet sentences). The table is from 2017 — [eLife list](https://elifesciences.org/inside-elife/5ebd9a3f/plain-language-summaries-journals-and-other-organizations-that-produce-plain-language-summaries)
- Kudos: authors write a plain-language "What is it about / Why is it important" story, with publishers suggesting 4–5 sentences. The Royal Society of Chemistry (RSC) says it has served 460,000+ researchers (promotional figure) — [RSC Kudos page](https://www.rsc.org/publishing/publish-with-us/maximise-your-impact-and-visibility/increase-your-impact-with-kudos)
- Academic research exists on automated lay summarization (for example the BioLaySumm 2024 shared task) — [BioLaySumm 2024 overview](https://arxiv.org/pdf/2408.08566)

### Inferences
- LLM inline explanation (F2b) is not differentiating by itself. Explainpaper gives it away free, SciSpace includes it in its free tier, and Lumi is open-source Google code doing margin annotations on arXiv. ResearchBridge's differentiation would have to come from audience (lay readers), faithfulness guarantees, or curation/verification, not from having the feature.
- The well-funded players (Elicit, Consensus, SciSpace, alphaXiv) are moving toward "research agents" and literature review for professionals: Elicit Reports, Consensus Deep, SciSpace Agent, alphaXiv Autoresearch and MCP. That pulls them away from the lay-reader use case, leaving it relatively open.
- Paper Plain is the strongest direct prior art for "lay readers plus original paper plus inline help", but it remains a research prototype. Its CHI/TOCHI paper is worth reading for user-study evidence on what lay readers actually used.
- Human-written lay summaries (eLife digests, Cochrane PLS, PNAS significance statements) give a quality benchmark and possibly training/eval data. They exist for only a small fraction of papers, which is the coverage gap an automated tool would fill.

### Gaps
- Perplexity academic/focus mode, Paper Digest, Moonlight (AI paper reviewer extension), Scite Assistant and "ResearchGPT"-style tools were not verified in this session. I found no 2026 source on their current features or status.
- I could not confirm whether Paper Plain's demo is still live in 2026.
- I could not confirm Explainpaper's 2026 activity (the site shows only "© 2025").
- ChatPDF's official pricing and NotebookLM's paper-specific features were not checked against primary sources.
- PLOS "author summaries" are documented here only for PLOS Medicine (2017 data). Current PLOS-wide practice was not verified.

## Q2. Which products do community/human annotation or per-paper discussion?

### Takeaway
Human annotation and discussion of papers exists in several mature but niche forms: Hypothesis (general web annotation, now mainly used in education), PubPeer (post-publication critique, dominated by misconduct reports), Fermat's Library (curated annotated "journal club"), PREreview and Sciety (open preprint review and aggregation), and alphaXiv comments. All are expert- or classroom-oriented. None is a Genius-style lay explanation layer at scale. The one attempt to bring Genius-style annotation to the open web was scaled back after a harassment controversy and low usage.

### Cited Findings

**Hypothesis** (open web/PDF annotation; nonprofit; open-source client)
- Reports 1M+ users and 300+ institutional customers, mostly higher education (secondhand figure) — [Fieldwork security review](https://fieldwork.news/tools/hypothes-is/)
- Has published milestones of 7M and later 20M annotations (dates not captured) — [Hypothesis 7M blog](https://web.hypothes.is/blog/hypothesis-7-million-annotations-and-counting/); [Hypothesis 20M blog](https://web.hypothes.is/blog/our-view-from-20-million-annotations/); [Nature 2019 milestone](https://www.nature.com/articles/d41586-019-01427-9)
- 2025 releases were education-focused: image annotation in PDFs, @mentions and grading tools — [UChicago Academic Tech, Dec 2025](https://academictech.uchicago.edu/2025/12/10/explore-new-hypothesis-features-for-image-annotation-grading-and-more/)
- Adoption is low even in its core market. At CU Boulder it was used in 0.3% of Canvas courses and by 0.9% of Canvas users (Fall 2021 to Spring 2025 average), behind Perusall — [CU Boulder OIT assessment](https://oit.colorado.edu/services/consulting-professional-services/academic-technology-initiatives-team/needs-assessments/social-annotation-tools)

**PubPeer** (post-publication commenting; experts)
- 2012–2021: 189,426 comments by 42,661 commentators on 101,272 publications — [arXiv 2310.16059](https://arxiv.org/pdf/2310.16059)
- More than two-thirds of comments report some type of misconduct, mainly image manipulation (2019–2020 sample of 39,985 posts on 24,779 publications) — [IDEAS/JASIST 2022](https://ideas.repec.org/a/bla/jinfst/v73y2022i5p655-670.html)
- A 2026 researcher survey found PubPeer's effect on correcting the record is indirect (through retractions), with anonymity the main concern — [Sciety/OSF preprint "PubPeer is okay, but…"](https://sciety.org/articles/activity/10.31222/osf.io/nh3eg_v1)
- PubPeer has opened to preprint reviews — [UCSF Guides](https://guides.ucsf.edu/writingpublishing/peerreview)

**Fermat's Library** (free, curated annotated papers)
- Launched 2015, free and open. Scientists, academics and citizen scientists annotate equations, figures and ideas in the margins. A weekly "Journal Club" features community-annotated papers in mathematics, physics, economics, CS and biology. "Margins" lets users save, annotate and share papers — [Fermat's Library](https://fermatslibrary.com/); [Journal Club](https://fermatslibrary.com/journal_club); [Margins](https://fermatslibrary.com/margins); [Nautilus interview](https://nautil.us/in-fermats-library-no-margin-is-too-narrow-236846)
- Has partnered with the journal Quantum — [Quantum collaboration](https://quantum-journal.org/collaboration-with-fermats-library/)

**PREreview and Sciety** (open preprint review)
- PREreview: open preprint review in which reviews get DOIs. Described in Sept 2026 as an "innovation lab" for open peer review — [eLife Labs on PREreview](https://elifesciences.org/labs/57d6b284/prereview-a-new-resource-for-the-collaborative-review-of-preprints); [Zenodo 2026 presentation](https://zenodo.org/records/22756778)
- Sciety aggregates preprint evaluations and activity feeds (example 2026 activity page) — [Sciety](https://sciety.org/articles/activity/10.31222/osf.io/nh3eg_v1)

**ResearchHub** (crypto-incentivized science community, now a funding platform)
- As of Aug 21, 2026, its homepage is "funding-focused". It reports over $2.2M of grants funded, with fully funded proposals auto-accepted as registered reports in the ResearchHub Journal. Its backend GitHub was active Aug 2026. Last known raise: $5M seed (June 2023) — [ResearchHub on X](https://x.com/ResearchHub/status/2090891266653302875); [ResearchHub Journal](https://www.researchhub.com/journal); [GitHub](https://github.com/ResearchHub); [startupintros](https://startupintros.com/orgs/researchhub)

**alphaXiv comments**
- Offers line-by-line commenting on arXiv papers. A reviewer said many earlier comments were bot-posted, giving limited value — [PitchBook](https://pitchbook.com/profiles/company/770062-33); [Medium review](https://medium.com/@joycebirkins/alphaxiv-an-evidence-based-ai-platform-for-precise-analysis-online-arxiv-paper-search-viewing-e9d66eff6b87)
- The Oct 2026 homepage foregrounds AI-grounded answers and literature review rather than discussion — [alphaXiv](https://www.alphaxiv.org/)

**Genius (Rap Genius) expansion beyond music: the closest "failed lay annotation" precedent**
- Rap Genius renamed itself Genius to annotate news, literature and so on. It hired an education lead in 2013 and launched the genius.it prefix and Web Annotator for annotating any web page (2015) — [Connected Learning Alliance](https://clalliance.org/blog/annotation-rap-genius-and-education/); [TechCrunch 2015](https://techcrunch.com/2015/04/08/annotate-this/); [Fast Company](https://www.fastcompany.com/3044833/annotating-service-genius-wants-to-mark-up-the-entire-internet)
- 2016 harassment controversy: blogger Ella Dawson asked Genius to disable the annotator on her site. Site owners could not opt out, and there was no way to report abusive annotations. Genius later added a report-abuse tool — [Daily Dot](https://dailydot.com/?p=108098); [Digiday](https://digiday.com/media/genius-matures-hires-first-cro-adds-report-abuse-tool-amid-controversy/)
- Genius later laid off about a quarter of its staff (mostly engineering) and said it would shift emphasis away from the annotation platform toward video (Verge report relayed) — [pxlnv linklog citing The Verge](https://pxlnv.com/linklog/genius-will-de-emphasize-web-annotations-in-favour-of-video/)
- One account attributed to a Genius founder (unverified authorship, undated) says: "We shut down our web annotator because nobody was using it and some wack-ass politicians were criticizing it" — [HackerNoon](https://hackernoon.com/the-ceo-of-my-company-genius-must-be-black-8q1030xa)

**Personal annotation (Zotero, Mendeley)**: not researched in this session (see Gaps).

### Inferences
- The evidence points to one failure pattern for open community annotation outside music lyrics: low sustained contribution, plus abuse/moderation burden (Genius), or capture by a narrow use (PubPeer becoming a misconduct-reporting venue). This bears directly on decisions.md §2.1(a). Cold start and moderation are documented problems, not hypothetical ones.
- Every surviving human-annotation venue has a committed niche contributor base: instructors and students (Hypothesis), research-integrity sleuths (PubPeer), curators (Fermat's Library), early-career reviewers (PREreview). A lay-explainer community would need a comparable motivated group. Candidates include grad students, science communicators and journalists. That is an inference to test.
- Fermat's Library's model (a small number of high-quality, curated annotated papers per week) is a realistic template for hybrid seeding: curated human annotations on a few featured papers, with LLM annotations elsewhere.
- alphaXiv's bot-comment problem and its pivot toward AI features suggest that per-paper discussion threads alone do not create engagement.

### Gaps
- No 2025–2026 PubPeer activity statistics were found. The latest are 2012–2021.
- Genius Web Annotator: no official shutdown date or announcement found. The "shut down" claim rests on an unverified HackerNoon post. The prompt's "Genius science/education vertical" could not be confirmed as a distinct product. Only the education push and the general web annotator are documented.
- Zotero and Mendeley annotations, arXiv-adjacent discussion sites (for example Hacker News or Reddit threads, and Hugging Face Papers comments) and any Wikipedia-like lay-science annotation efforts were not researched.
- No traction data found for Fermat's Library, PREreview or Sciety.

## Q3. Per-product profile: audience, ResearchBridge feature coverage, business model, 2026 status, traction, shutdowns

### Takeaway
Every active commercial product targets researchers and students on freemium subscriptions of roughly $10–$50/month at the entry paid tier. Lay-oriented work exists only as research prototypes (Paper Plain), open-source demos (Lumi) or hand-written journal digests. Notable shutdowns and retreats are Papers with Code (July 2025) and Genius's web annotation. ResearchHub has pivoted to funding.

### Cited Findings
- Papers with Code (Meta) was sunset July 24, 2025 without prior notice. The domain now redirects to Hugging Face Trending Papers. The data is preserved in a GitHub repo, last updated Sep 8, 2025 — [HyperAI](https://hyper.ai/en/news/42900); [Coursera article](https://www.coursera.org/articles/papers-with-code); [GitHub issue #116](https://github.com/paperswithcode/paperswithcode-data/issues/116)
- Iris.ai: active, enterprise R&D, Series A about €8M (2024) — [PitchBook](https://pitchbook.com/profiles/company/162774-19)
- ResearchHub: active, but its homepage pivoted to science funding (Aug 2026) — [ResearchHub on X](https://x.com/ResearchHub/status/2090891266653302875)
- Pricing, traction and status for Explainpaper, SciSpace, alphaXiv, Elicit, Consensus, Humata, ChatPDF, Hypothesis, PubPeer and Fermat's Library: see the Q1 and Q2 citations above.

### Inferences
Feature map. "Y" means a documented core feature, "~" means partial or adjacent, "–" means not found. Cells are based on the Q1/Q2 citations and reflect what was found, not an exhaustive audit.

| Product | Audience | F1 full rewrite | F2 inline explain (LLM) | F2 inline (human) | F3 structured summary | F3 limitations/COI focus | F4 metrics | F5 discussion | Model / price | Status Oct 2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| Explainpaper | Researchers/learners | – | Y | – | ~ (outline, key points; Pro full summary) | – | – | – | Free + Pro $16/mo | Site live; "© 2025", activity unconfirmed |
| SciSpace | Researchers/students | – | Y (text, equations, tables, figures) | – | Y (summaries) | – | – | – | Freemium credits; ~$12–20/mo entry (conflicting) | Active; claims 6–9.6M users |
| alphaXiv | AI/ML engineers and researchers | – | Y | ~ comments | ~ (one-line summaries) | – | ~ (view counts) | Y (line-by-line) | Not shown; VC-backed ($7M seed) | Active; claims "millions" |
| Lumi (Google PAIR) | arXiv readers | – (full translation requested, not built) | Y (margin summaries, figure explanations) | – | Y (multi-level summaries) | – | – | – | Free, open source | Demo live per HN; repo activity date unknown |
| Semantic Scholar (TLDR, Reader) | Researchers | – | ~ (definitions, citation context) | – | ~ (1-sentence TLDR) | – | Y (citations) | – | Free (nonprofit Ai2) | Active; Reader still beta |
| Paper Plain (Ai2 research) | **Lay readers, medical papers** | – | Y (definitions, passage gists, guiding questions) | – | ~ | – | – | – | Research prototype | Prototype only (CHI 2024) |
| Elicit | Researchers / systematic reviews | – | – | – | Y (extraction tables, Reports) | ~ (user-defined extraction columns; inference) | – | – | Freemium; $12–49+/mo (conflicting) | Active; $22M Series A 2025 |
| Consensus | Researchers / general queries | – | – | – | Y (question-answer synthesis) | – | ~ | – | Freemium; Pro $10–20/mo (conflicting) | Active; $30M raise, 2.5M monthly claimed |
| Scholarcy / SciSummary | Students/researchers | – | – | – | Y (flashcard summaries) | – | – | – | Freemium | Listed in 2026 roundups |
| NotebookLM / Humata / ChatPDF | General docs | – | ~ (chat Q&A) | – | Y (audio/text summaries) | – | – | – | Free / freemium | Active |
| Kudos | Authors promoting work | – | – | – | ~ (author-written lay "what/why") | – | ~ (altmetrics-style tracking) | – | Publisher-paid | Active (460k+ researchers claimed) |
| eLife digests / Cochrane PLS / PNAS significance | Public | ~ (lay digest, not a rewrite) | – | – | Y (human-written) | – | – | – | Journal cost | Active; small share of the literature |
| Hypothesis | Educators/students | – | – | Y | – | – | – | Y (threaded annotations) | Nonprofit; institutional licences | Active; education-focused |
| PubPeer | Research-integrity community | – | – | ~ (comments, not explanations) | – | ~ (critiques often flag problems) | – | Y | Free, nonprofit | Active |
| Fermat's Library | Curious scientists, citizen scientists | – | – | Y (curated margin annotations) | – | – | – | Y | Free | Active (launched 2015) |
| PREreview / Sciety | Preprint reviewers | – | – | ~ (reviews) | ~ | – | – | Y | Nonprofit | Active |
| ResearchHub | Researchers, crypto-funded | – | – | ~ | – | – | – | Y | Token/grant-funded | Active; pivoted to funding |
| Genius Web Annotator | General web | – | – | Y | – | – | – | Y | Ad-funded | De-emphasized/shut down (date unverified) |
| Papers with Code | ML researchers | – | – | – | – | – | Y (benchmarks) | – | Meta-funded | **Shut down July 2025** |

- Regular pattern: products bundle F2 (LLM) with F3 (generic summaries). Nobody bundles F1, F3-with-limitations/COI, F4-readability/burden scores and F5 for a lay audience.
- Business-model signal: researcher willingness to pay supports $10–50/mo tiers. There is no documented paying lay-public market. Combined with decisions.md §1.1 (NC licences constrain commercialization), the lay-audience slot may be better suited to a nonprofit or grant model, like Ai2, Hypothesis and PREreview.

### Gaps
- No verified traction numbers for Lumi, Fermat's Library, PREreview, Sciety, Scholarcy or SciSummary.
- Official pricing pages were not fetched for SciSpace, Elicit or Consensus. The aggregator figures conflict.
- Whether Elicit's custom extraction columns are commonly used to extract limitations or conflict-of-interest information is an inference, not a documented feature.

## Q4. Which ResearchBridge features appear genuinely unserved?

### Takeaway
The clearest gaps are: (1) a faithful full-paper plain-English rewrite with brief added context, side-by-side with the original; (2) summaries that systematically surface limitations, conflicts of interest and statistical significance for lay readers; (3) per-paper readability and prior-knowledge-burden scores; and (4) any of this aimed at the public, journalists and claim-checkers rather than researchers. The individual pieces (LLM highlight-explain, generic summaries, citation counts, comment threads) are all well served.

### Cited Findings
- None of the 2026 summarizer roundups describe a tool built for general readers. They target students and researchers — [Paperguide roundup](https://paperguide.ai/blog/ai-research-paper-summarizers/); [unite.ai Oct 2026](https://www.unite.ai/best-ai-research-paper-summarizers/)
- Lumi users have requested full-text paragraph-by-paragraph translation, which suggests even the most "reading-augmentation" focused open tool lacks full rewrite — [Lumi issue #107](https://github.com/PAIR-code/lumi/issues/107)
- Paper Plain (lay readers, medical papers) remained a research prototype — [Semantic Reader platform](https://openreader.semanticscholar.org/); [arXiv 2303.14334](https://www.arxiv.org/pdf/2303.14334)
- Human lay summaries are short (PNAS ~120 words, eLife ~347 words, Cochrane 400–700 words) and summarize rather than rewrite — [eLife](https://elifesciences.org/articles/25411); [eLife list](https://elifesciences.org/inside-elife/5ebd9a3f/plain-language-summaries-journals-and-other-organizations-that-produce-plain-language-summaries)
- Lay summarization is an active academic research area (BioLaySumm), not yet a consumer product category — [BioLaySumm 2024](https://arxiv.org/pdf/2408.08566)
- PubPeer critiques mostly flag misconduct, such as image manipulation, rather than explaining limitations to lay readers — [IDEAS/JASIST](https://ideas.repec.org/a/bla/jinfst/v73y2022i5p655-670.html)

### Inferences
- **F1 (full faithful rewrite plus context, side-by-side)**: no product found does this. The likely reasons are cost, faithfulness risk, and copyright, all of which ResearchBridge's licence-gated corpus partly addresses. That copyright gate may be part of why incumbents, who work on user-uploaded PDFs, have not built a hosted full rewrite.
- **F3 limitations/COI/significance focus**: generic summarizers extract "findings" and "methods". No product found markets an explicit limitations, COI or "how strong is this evidence" section for lay readers. This fits the claim-checker and journalist audience.
- **F4 readability score and prior-knowledge burden score**: no product found offers per-paper readability or background-burden scores. Citation counts are commodity (Semantic Scholar, Consensus). Journal-quality labels carry the risk flagged in decisions.md §2.3.
- **F5 discussion**: well served for experts (PubPeer, alphaXiv, Hypothesis, Fermat's Library). Discussion aimed at lay readers ("what does this mean for me?") is unserved, but history (Genius, alphaXiv bot comments) suggests it is hard to make work.
- **F2 hybrid (curated human plus LLM)**: Fermat's Library (curated human) and Lumi/Explainpaper (LLM) each do half. No product found combines LLM annotations with human verification or upvoting for lay readers.

### Gaps
- Not exhaustive. Smaller or newer lay-focused startups (2025–2026 launches) may exist that general searches did not surface. A Product Hunt sweep was not done.
- Whether ScienceOpen, Researcher (app), Perplexity or Scite offer limitation-focused summaries was not checked.

## Q5. Public evidence about LLM explanation faithfulness complaints and hallucinations

### Takeaway
There is solid peer-reviewed evidence that LLMs systematically overgeneralize scientific findings when summarizing (about 5x more often than human summaries), and that AI paper "podcasts" and research assistants introduce unsupported claims. There is no authoritative benchmark comparing the faithfulness of the specific paper-explanation products, which leaves room for ResearchBridge's planned groundedness benchmark (decisions.md §2.2).

### Cited Findings
- Peters & Chin-Yee (Royal Society Open Science, April 2025) tested 10 LLMs on 4,900 summaries of scientific research. Several models (including DeepSeek, ChatGPT-4o and LLaMA 3.3 70B) overgeneralized in 26–73% of cases, even when prompted for accuracy. LLM summaries were about 5x more likely than human-written summaries to contain broad generalizations (OR = 4.85) — [PMC full text](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12042776/); [PhilArchive](https://philarchive.org/rec/PETGBI-4)
- Newer models often did worse than older ones on generalization accuracy. A typical error was turning past-tense, study-bound claims into present-tense universal ones. Claude had the highest generalization accuracy among those tested. Suggested mitigations include lower temperature and benchmarking for generalization accuracy — [Utrecht University news](https://www.uu.nl/en/news/most-leading-chatbots-routinely-exaggerate-science-findings); [PhilArchive](https://philarchive.org/rec/PETGBI-4)
- NotebookLM Audio Overviews of three planetary-science papers (AGU journal study, Flynn & Peters) made unjustified extrapolations. One implied liquid water and possible life on Mars, which the paper never claimed. Subtler errors were "harder for nonexperts to catch" — [Futurity](https://www.futurity.org/ai-generated-podcasts-3323312/)
- A TechRadar reviewer found NotebookLM skipped key information, made factual errors and referenced information not in the document — [TechRadar](https://www.techradar.com/pro/notebooklm-review)
- HKUST Library's evaluation of Scite Assistant, Elicit, Consensus and Scopus AI found arguments generally well supported. However, the tools drew inaccurate conclusions from introductory or general statements in abstracts rather than specific findings. Only Scite retrieved full text; the others mainly used abstracts — [HKUST Library](https://library.hkust.edu.hk/sc/trust-ai-lit-rev/); [Katina Magazine](https://katinamagazine.org/content/article/reviews/2025/deep-dive-into-three-ai-academic-search-tools)
- A JCHM study of ScholarAI and SciSpace found outputs "not free from misinformation" in both interpretation and citations. SciSpace's literature-search quality was judged unacceptable in all four sessions, and hallucinations increased across sessions — [JCHM](https://jchm.in/archive/volume/13/issue/2/article/27050/pdf)
- PaperAsk (2025) is a benchmark for LLM reliability in paper search and reading — [arXiv 2510.22242](https://arxiv.org/pdf/2510.22242)
- Disregarded as unreliable: vendor-blog "hallucination rates" (Atlas: Elicit 0.07, Consensus 0.09, Scite 0.11, SciSpace 0.16) with no methodology, and a Botonomy blog citing an unverifiable "Stanford HAI study" — [Atlas](https://www.atlasworkspace.ai/blog/best-ai-research-assistants); [Botonomy](https://www.botonomy.ai/blog/automation/ai-powered-research-assistant/)

### Inferences
- The documented failure (overgeneralization, past to present tense, study-bound to universal) is exactly the "nuance turned into clickbait" risk inspiration.md wants to avoid. It is also the error lay readers are least able to detect (Flynn & Peters). This argues for faithfulness checks that target generalization scope and hedging, not just factual hallucination.
- Abstract-only grounding (HKUST finding) is a known weakness of incumbents. ResearchBridge's full-text, openly licensed corpus allows full-text grounding, which is a defensible quality claim if measured.
- No vendor publishes a third-party-verified faithfulness score for paper explanations. A published, reproducible faithfulness benchmark could itself be a differentiator and a trust signal.

### Gaps
- No product-specific faithfulness complaints were found for Explainpaper, alphaXiv or Lumi inline explanations (for example on Hacker News or Reddit). This was not searched in depth.
- Elicit's self-published accuracy metrics (mentioned by CASRAI) were not retrieved — [CASRAI guide](https://casrai.org/guides/ai-powered-research-assistant-tools)
- The exact citation for the Flynn & Peters AGU paper (journal name, year) was not retrieved. Only the Futurity coverage was seen.
