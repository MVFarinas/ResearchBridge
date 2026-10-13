# Open-source paper reading interfaces and LLM paper-explanation tools (reuse inventory for ResearchBridge)

Method note: repository metadata (licence, stars, last push or commit, latest release, contributor count) was pulled from the GitHub REST API with `gh api` on 2026-10-13. "pushed" is the date of the last push to any branch. Where it matters, the date of the last commit on the default branch is given as well. Hugging Face licence data comes from the HF models API on the same date. Star counts are a rough popularity signal and say nothing about code quality. "lic=null" means GitHub found no licence file. Under default copyright that means **no reuse rights**, whatever the paper or README says.

---

## Q1. Allen AI Semantic Reader Open Research Platform: which components are open source, under what licences, how well maintained, and how close to production?

### Takeaway
Only two pieces are officially presented as reusable libraries: **PaperMage** (Apache-2.0, parsing) and **PaperCraft** (the `allenai/pdf-component-library` repo, published to npm as `@allenai/pdf-components` with an Apache-2.0 declaration). Both have effectively stopped development: the last commits were in Nov 2024 and Nov 2023. **ScholarPhi** (inline term and symbol definitions) is Apache-2.0 but was last committed in March 2023, and its pipeline needs LaTeX source. **Paper Plain** and **Scim** have code with *no licence*, and Paper Plain's UI was never released. I found no public code for **CiteSee, Relatedly or Threddy**. Everything here is research-prototype grade, best used for design patterns and selective code harvesting, not as a maintained dependency.

### Cited Findings
- The official platform page lists exactly two "Open Source Libraries": PaperMage ("Process and Analyze Scholarly PDF Documents", github.com/allenai/papermage, EMNLP 2023 demo) and PaperCraft ("Create Visually Augmented Interactive Readers", source = github.com/allenai/pdf-component-library). Everything else (Papeos, Synergi & Threddy, Paper Plain, LLM Paper Q&A, CiteSee, CiteRead, Scim, ScholarPhi) is listed under "Research prototypes". The page states no licence for any project. — [Semantic Reader Open Research Platform](https://openreader.semanticscholar.org/)
- On that page, CiteSee and Scim are tagged "In-Production" (that is, built into the Semantic Scholar reader product, not released as code). Relatedly, Qlarify and SciA11y appear only as publication entries with no code links. — [Semantic Reader Open Research Platform](https://openreader.semanticscholar.org/)
- The Semantic Reader Project paper (CACM / arXiv 2303.14334) describes the three pillars (research, product, open-science resources). — [arXiv 2303.14334](https://www.arxiv.org/pdf/2303.14334); [CACM](https://cacm.acm.org/research/the-semantic-reader-project)
- **PaperMage**: allenai/papermage. Apache-2.0, Python, about 815 stars, 8 contributors. Latest release v0.18.0 (2024-03-17), last commit 2024-11-08. The README warns: "This project is a research prototype for EMNLP 2023. Due to other project priorities, we are unlikely to be addressing issues / maintaining this on a regular cadence", and points to the Dolma project for future PDF parsing work. — [allenai/papermage](https://github.com/allenai/papermage)
- **PaperCraft / pdf-component-library**: allenai/pdf-component-library. TypeScript, about 93 stars, no LICENSE file detected by GitHub. The library's `ui/library/package.json` declares `"license": "Apache-2.0"`, and the npm package `@allenai/pdf-components` lists Apache-2.0. Latest npm version 1.0.2, published 2024-02-15; the last default-branch commit is dated 2023-11-15. — [allenai/pdf-component-library](https://github.com/allenai/pdf-component-library); npm registry (`npm view @allenai/pdf-components`)
- The pdf-component-library README describes a React layer on top of `react-pdf`. Its features are citation popovers, outlines, thumbnails, zoom, page control, **text highlighting**, **Hypothesis.io integration for note taking**, scroll-to logic and performance optimisation. Architecture: a page image as the background layer, then a transparent text layer for selection and highlighting, then an **overlay layer "where most of the interactive features are located, such as page highlights and citation popovers"**. — [pdf-component-library README](https://github.com/allenai/pdf-component-library)
- **ScholarPhi**: allenai/scholarphi ("An interactive PDF reader"). Apache-2.0, about 427 stars, 21 contributors, no releases, last commit 2023-03-29. It has three sub-projects: `ui/`, an `api/` that serves entities and their bounding boxes, and `data-processing/`. The quick start runs the UI "pointing to the production api". — [allenai/scholarphi](https://github.com/allenai/scholarphi)
- The ScholarPhi data-processing README says: "if you want to run all stages of the data processing pipeline, installation is going to be pretty involved... these scripts need to compile LaTeX, analyze images, invoke Node.js libraries, and upload data to a database" (PostgreSQL). — [scholarphi/data-processing](https://github.com/allenai/scholarphi/tree/master/data-processing)
- The platform page describes ScholarPhi as "Augmenting Papers with Just-in-Time Definitions of Terms and Symbols", with a demo at scholarphi.org, and labels it the "Founding Project". — [Semantic Reader Open Research Platform](https://openreader.semanticscholar.org/)
- **Paper Plain**: allenai/paper-plain. No licence, 8 stars, last push 2022-02-28. Its README describes four NLP-powered features: "definitions of unfamiliar terms, in-situ plain language section summaries, a collection of key questions that guide readers to answering passages, and plain language summaries of the answering passages". It says "`ui/` ... TBD". The repo contains only `backend/` notebooks: "Public - GPT-3 Simplification.ipynb", "Public - Term Definitions.ipynb", "Public - Extractive_QA_BioASQ.ipynb", "Public - Linking Questions and Answers.ipynb", "Public - Document Annotations.ipynb", and `sauce_defs.py`. The demo links point to an allenai.org app subdomain. — [allenai/paper-plain](https://github.com/allenai/paper-plain)
- The platform page dates Paper Plain as "TOCHI'22 -> CHI'24". — [Semantic Reader Open Research Platform](https://openreader.semanticscholar.org/)
- **Scim**: the code lives at rayfok/scim, not under allenai. No licence, about 40 stars, last push 2024-01-30. `reader/` holds the UI, which "is built upon infrastructure for... ScholarPhi". `model/sse_skimming` holds the salient-sentence extraction and classification pipeline, with Snorkel weak supervision under `weak_label` and labelling functions "designed over research papers in NLP". — [rayfok/scim](https://github.com/rayfok/scim)
- **CiteSee / Relatedly / Threddy**: no repositories under allenai on GitHub (API returned 404 for allenai/citesee, allenai/relatedly, allenai/threddy). A GitHub search for "threddy" returns only unrelated projects. The Threddy paper (Kang, Chang, Kim, Kittur 2022) gives no repository link. — [Threddy arXiv 2208.03455](https://arxiv.org/pdf/2208.03455); GitHub API search, 2026-10-13
- AI2's actively maintained, Apache-2.0 open-source work has moved toward literature QA and parsing: **allenai/ai2-scholarqa-lib** (Apache-2.0, about 288 stars, pushed 2026-06-25), **allenai/olmocr** (Apache-2.0, about 19.7k stars, pushed 2026-03-25, "Toolkit for linearizing PDFs for LLM datasets/training") and **allenai/asta-paper-finder** (Apache-2.0, pushed 2026-03-17, described as a "frozen-in-time version"). — [ai2-scholarqa-lib](https://github.com/allenai/ai2-scholarqa-lib); [olmocr](https://github.com/allenai/olmocr); [asta-paper-finder](https://github.com/allenai/asta-paper-finder)
- **allenai/s2orc-doc2json** ("Parsers for scientific papers (PDF2JSON, TEX2JSON, JATS2JSON)"): Apache-2.0, about 477 stars, last push 2024-04-11. — [s2orc-doc2json](https://github.com/allenai/s2orc-doc2json)

### Inferences
- **The best fit for ResearchBridge feature (2), inline explanations anchored to spans, is the *pattern* from ScholarPhi, Paper Plain and PaperCraft rather than their code.** That pattern is entity records with bounding boxes or character offsets, served by an API and drawn in an overlay layer as popovers. PaperCraft's overlay-layer design is directly reusable (Apache-2.0 per npm). It is tied to PDF rendering, though. ResearchBridge's corpus is arXiv, PMC, PLOS and DOAJ, much of which is available as JATS XML or LaTeX/HTML, so an HTML-first reader with span anchors (character offsets into normalised text) is probably simpler than PDF bounding-box overlays.
- ScholarPhi's need for LaTeX compilation limits it to arXiv papers that have source. It does not cover PMC, PLOS or DOAJ JATS content. The Postgres plus image-processing pipeline from 2020–2023 would need heavy modernisation, and the LLM era makes its definition-extraction models largely obsolete. Reuse would be mostly UI and React code under Apache-2.0.
- Paper Plain's notebooks and Scim's code carry no licence, so they cannot legally be copied into ResearchBridge without permission from AI2 or the authors. Treat them as design references. The papers (TOCHI/CHI, IUI 2023) contain the UX evaluations, which are valuable evidence for ResearchBridge's lay-reader design (section "gists", key-question index).
- PaperMage is usable (Apache-2.0) for parsing PDFs into layered entities (tokens, sentences, sections, bounding boxes), but it is unmaintained. olmOCR, Docling (MIT, about 68.8k stars, active) or GROBID (Apache-2.0, active) are lower-risk parsing choices. JATS-native parsing makes PDF parsing unnecessary for PMC and PLOS.

### Gaps
- The npm package and package.json declare Apache-2.0 for pdf-component-library, but the repo has no LICENSE file. A legal review may want explicit confirmation from AI2.
- I could not check whether the Paper Plain and ScholarPhi demos (scholarphi.org, the allenai.org apps subdomain) are still live in Oct 2026.
- I found no evidence that CiteSee, Relatedly, Threddy, CiteRead, Papeos or Qlarify code was ever released. The links behind "Code Tutorial" for Paper Plain and "LLM Paper Q&A" on the platform page were not resolvable from the page text.

---

## Q2. LLM paper Q&A, summarisation and research repos: which are reusable, and which produce passage-anchored explanations rather than chat?

### Takeaway
The strongest permissively licensed, actively maintained engines are **PaperQA2** (Apache-2.0, grounded answers with in-text citations to chunks), **Kotaemon** (Apache-2.0, citations highlighted in an in-browser PDF viewer), **open-notebook** (MIT, NotebookLM clone with "transformations") and **ai2-scholarqa-lib** (Apache-2.0). None of these does ResearchBridge's core job: annotations attached to spans, generated proactively over a single paper. They are all question-driven chat or report generators. The closest single-paper reader is **Open Paper** (khoj-ai/openpaper), but it is **AGPL-3.0**. **ChatPaper's licence is CC BY-NC-ND 4.0, so its code cannot be reused.**

### Cited Findings
- **PaperQA2** (Future-House/paper-qa): Apache-2.0, about 9.4k stars, 40+ contributors, latest release v2026.08.12, pushed 2026-09-25. Described as "High accuracy RAG for answering questions from scientific documents with citations". It offers "grounded responses containing in-text citations", embeddings plus LLM-based "re-ranking and contextual summarization (RCS)", agentic RAG, multimodal contextual summarisation, and PDF readers that "parse images and tables, report page numbers". The pipeline creates a "scored summary of each chunk in the context of the current query" and then uses an "LLM to re-score and select most relevant summaries". — [Future-House/paper-qa](https://github.com/Future-House/paper-qa)
- **OpenScholar** (AkariAsai/OpenScholar): code Apache-2.0, about 1.7k stars, 4 contributors, no releases, last push 2025-08-13. — [AkariAsai/OpenScholar](https://github.com/AkariAsai/OpenScholar)
- **The OpenScholar-8B model weights carry the Llama 3.1 licence.** The HF API for `OpenSciLM/Llama-3.1_OpenScholar-8B` reports `license: llama3.1` and base model `meta-llama/Llama-3.1-8B` (last modified 2025-07-19). A search-engine summary of the model card claimed "Apache 2.0", which contradicts the HF metadata. Treat the weights as Llama-licensed: commercial use is allowed, with attribution and acceptable-use obligations and the 700M MAU clause. — [HF OpenSciLM/Llama-3.1_OpenScholar-8B](https://huggingface.co/OpenSciLM/Llama-3.1_OpenScholar-8B); conflicting summary via [OpenScholar model card](https://huggingface.co/OpenScholar/Llama-3.1_OpenScholar-8B/blame/main/README.md)
- **ai2-scholarqa-lib**: "Repo housing the open sourced code for the ai2 scholar qa app and also the corresponding library". Apache-2.0, pushed 2026-06-25. — [allenai/ai2-scholarqa-lib](https://github.com/allenai/ai2-scholarqa-lib)
- **STORM** (stanford-oval/storm): MIT, about 31.6k stars, 23 contributors, release v1.1.0 (2025-01-23), last push 2025-09-30. It is "a LLM system that writes Wikipedia-like articles from scratch based on Internet search", and Co-STORM adds human-AI collaboration (`pip install knowledge-storm`). — [stanford-oval/storm](https://github.com/stanford-oval/storm)
- **gpt-researcher** (assafelovic/gpt-researcher): Apache-2.0, about 30k stars, pushed 2026-10-10. "An autonomous agent that conducts deep research on any data using any LLM providers". — [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)
- **ChatPaper** (kaixindelele/ChatPaper): about 19.9k stars, last push 2026-03-02. GitHub reports the licence as NOASSERTION. LICENSE.md is **Creative Commons BY-NC-ND 4.0** (non-commercial, no derivatives). It does full-text summarisation, translation, polishing and review/response of arXiv papers, and builds on gpt_academic. — [kaixindelele/ChatPaper](https://github.com/kaixindelele/ChatPaper) (LICENSE.md)
- **arxiv-sanity-lite** (karpathy): MIT, about 1.7k stars, last push 2023-06-19. Tags arXiv papers and recommends similar ones with SVMs; it has no LLM explanation features. — [karpathy/arxiv-sanity-lite](https://github.com/karpathy/arxiv-sanity-lite)
- **Kotaemon** (Cinnamon/kotaemon): Apache-2.0, about 25.8k stars, 39 contributors, release v0.12.0 (2026-05-31), pushed 2026-07-14. "Advanced citations with document preview... View your citations (incl. relevant score) directly in the in-browser PDF viewer with highlights." — [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon)
- **open-notebook** (lfnovo/open-notebook): MIT, about 40.1k stars, 87 contributors, release v1.15.0 (2026-10-04), pushed 2026-10-13. Stack: Python, Next.js/React, SurrealDB, LangChain. Features include "Content Transformations: Powerful customizable actions to summarize and extract insights", citations, and multi-speaker podcast generation. — [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook)
- **podcastfy** (souzatharsis/podcastfy): Apache-2.0, about 6.6k stars, pushed 2026-05-04. "Open Source Python alternative to NotebookLM's podcast feature". — [souzatharsis/podcastfy](https://github.com/souzatharsis/podcastfy)
- **Open Paper** (khoj-ai/openpaper): **AGPL-3.0**, about 500 stars, 6 contributors, pushed 2026-10-05. Features: PDF and assistant side by side, an "AI-generated brief and starter questions" on upload, and "contextual citations — click one and you're taken to the exact passage". Users can "Select any text to highlight it, attach a comment, or send it to the AI assistant for a deeper explanation". It also offers project-level "Data tables" with custom extraction schemas "each cell grounded in its source", Zotero import and audio overviews. — [khoj-ai/openpaper](https://github.com/khoj-ai/openpaper)
- **alphaXiv**: the alphaXiv GitHub org exposes only `paper-implementations` and a `feedback` issue tracker, not the reader itself. Community clones: **AsyncFuncAI/alphaxiv-open** (MIT, about 152 stars, last push 2025-05-24) and **DylanUnicorn/little-alphaxiv** (MIT, about 20 stars, pushed 2026-08-21, "Self-hosted alphaxiv-style paper-reading app (FastAPI CORS proxy + Vite/React/TS SPA)", side-by-side PDF and paper-aware assistant, BYO key). — GitHub API search, 2026-10-13; [little-alphaxiv](https://github.com/DylanUnicorn/little-alphaxiv); [alphaxiv-open](https://github.com/AsyncFuncAI/alphaxiv-open)
- **OpenScholarXIV** (ScholarXIV/OpenScholarXIV): GPL-3.0, Dart (Flutter), about 1.2k stars, pushed 2026-08-29. An AI-powered app to search, read and bookmark arXiv papers. — [ScholarXIV/OpenScholarXIV](https://github.com/ScholarXIV/OpenScholarXIV)
- **paperai** (neuml/paperai): Apache-2.0, about 1.8k stars, pushed 2026-07-14, "AI for medical and scientific papers". Companion **paperetl**: Apache-2.0, pushed 2025-12-07, "ETL processes for medical and scientific papers". — [neuml/paperai](https://github.com/neuml/paperai); [neuml/paperetl](https://github.com/neuml/paperetl)
- **PDFMathTranslate** (now PDFMathTranslate/PDFMathTranslate): **AGPL-3.0**, about 37.5k stars, pushed 2026-10-13. "[EMNLP 2025 Demo] PDF scientific paper translation with preserved formats". Its engine **BabelDOC** (funstory-ai/BabelDOC) is also **AGPL-3.0**, about 9.7k stars, pushed 2026-08-05. — [PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate); [BabelDOC](https://github.com/funstory-ai/BabelDOC)
- **Reader and annotation UI building blocks** (all checked 2026-10-13):
  - **mozilla/pdf.js**: Apache-2.0, about 54k stars, active. — [pdf.js](https://github.com/mozilla/pdf.js)
  - **wojtekmaj/react-pdf**: MIT, about 11.2k stars, active. — [react-pdf](https://github.com/wojtekmaj/react-pdf)
  - **agentcooper/react-pdf-highlighter**: MIT, about 1.4k stars, last push 2024-11-22. — [react-pdf-highlighter](https://github.com/agentcooper/react-pdf-highlighter)
  - **DanielArnould/react-pdf-highlighter-extended**: MIT, about 110 stars, last push 2024-11-22. — [react-pdf-highlighter-extended](https://github.com/DanielArnould/react-pdf-highlighter-extended)
  - **hypothesis/client**: GitHub reports NOASSERTION, the LICENSE text begins with a BSD-style "Redistribution and use in source and binary forms" clause, active (2026-10-04). — [hypothesis/client](https://github.com/hypothesis/client)
  - **zotero/reader**: "PDF/EPUB/HTML reader for Zotero", copyright Corporation for Digital Scholarship, licence in COPYING (NOASSERTION per GitHub), active. — [zotero/reader](https://github.com/zotero/reader)
- **HTML renderings of arXiv**: **dginev/ar5iv** (MIT, about 875 stars, pushed 2026-10-13) and **brucemiller/LaTeXML** (NOASSERTION per GitHub, active 2026-09-20). — [ar5iv](https://github.com/dginev/ar5iv); [LaTeXML](https://github.com/brucemiller/LaTeXML)

### Inferences
- Classification by output mode:
  - **Passage-anchored, i.e. jumps or highlights to the source span**: Kotaemon, Open Paper and PaperQA2 (anchors are chunk and page citations).
  - **Chat or report only**: STORM, gpt-researcher, ChatPaper, alphaXiv clones, OpenScholar.
  - **Notebook-style transformations**: open-notebook.
  - **Proactive span annotations generated over the whole document** (ResearchBridge feature 2): only the AI2 research prototypes (ScholarPhi, Paper Plain, Scim), and no maintained OSS project does this.
- PaperQA2's "contextual summarization" of chunks is close to what ResearchBridge needs for structured summaries (feature 3), for example running fixed questions like "What are the limitations?" or "What COIs are declared?" over each paper and getting chunk-cited evidence. It is Apache-2.0 and actively released, so it is the strongest pipeline candidate. Its design targets multi-paper corpora, so single-paper use would mean configuring a one-document index.
- Kotaemon's citation-highlight PDF viewer (Apache-2.0, Gradio-based) is a reusable reference for "evidence highlight in source", but it is a Gradio app, not a component library.
- AGPL tools (Open Paper, PDFMathTranslate/BabelDOC, oddpub) impose network-use source disclosure. Copying their code into a hosted ResearchBridge would oblige ResearchBridge to publish its full source under AGPL. Use them as design references or run them as isolated services only after legal review.
- PDFMathTranslate and BabelDOC deserve a close look because their task, layout-preserving full-text rewriting of papers, is structurally the same as ResearchBridge feature (1) with "plain English" in place of the target language. The licence is the blocker.
- For the arXiv portion of the corpus, LaTeXML/ar5iv HTML provides a semantic, span-addressable rendering that sidesteps PDF overlay complexity.

### Gaps
- I did not verify whether alphaXiv has open-sourced any reader component beyond paper-implementations. No such repo was found.
- I did not check Kotaemon's or PaperQA2's issue-response health beyond release cadence.
- SciSpace-style OSS clones beyond Open Paper and the alphaXiv clones: no prominent, well-maintained project was found. Most GitHub "paper explainer" repos are small hobby projects (for example ScienceDeJargonizer, 1 star, no licence).

---

## Q3. Open-source models and pipelines for plain-language rewriting and simplification of science, and for jargon explanation

### Takeaway
Small fine-tuned simplification models exist on Hugging Face under Apache-2.0, notably **pszemraj/long-t5-tglobal-base-sci-simplify**, trained on PLOS lay summaries. They are research-grade and abstract-level, and they fall well short of a modern instruction-tuned LLM with prompting. **SciTLDR** (Apache-2.0) is code and data for one-sentence TLDRs, last updated 2023. Jargon identification research (Guo et al., NAACL 2024) has no confirmed public code. Realistically, ResearchBridge will use general LLMs for rewriting, and these datasets (PLOS/eLife lay summaries, CELLS, PLABA) serve as evaluation benchmarks.

### Cited Findings
- **pszemraj/long-t5-tglobal-base-sci-simplify**: licence apache-2.0, base google/long-t5-tglobal-base, dataset `pszemraj/scientific_lay_summarisation-plos-norm`, about 132.5k downloads, last modified 2025-12-29. The eLife variant `...-sci-simplify-elife` is also apache-2.0. — [HF model](https://huggingface.co/pszemraj/long-t5-tglobal-base-sci-simplify)
- **haining/sas_baseline / haining/scientific_abstract_simplification**: described as a scientific abstract simplification model, prompted with "summarize, simplify, and contextualize: ". The HF API did not return licence metadata (it required auth). — [HF haining/sas_baseline](https://huggingface.co/haining/sas_baseline)
- **sambydlo/scientific_abstract_simplification-scientific-lay-summarise**: apache-2.0, T5 fine-tuned on `tomasg25/scientific_lay_summarisation`, last modified 2023-03-29, 20 downloads (negligible adoption). — [HF model](https://huggingface.co/sambydlo/scientific_abstract_simplification-scientific-lay-summarise)
- CELLS (paired abstracts and lay language summaries) is used for abstract-level lay language generation with retrieval augmentation. — [Retrieval augmentation for lay language generation, arXiv 2211.03818](https://arxiv.org/pdf/2211.03818)
- PLABA (Plain Language Adaptation of Biomedical Abstracts, a TREC 2024 track). A University of Amsterdam paper reports its models "are conservative and cautious in gratuitous edits or information insertions". — [Biomedical text simplification models trained on aligned abstracts and lay summaries](https://www.dare.uva.nl/id/70f0d5bc-87be-4430-89f8-8db7d08d96ee); [TREC PLABA NTU paper](https://trec.nist.gov/pubs/trec33/papers/ntu_nlp.plaba.pdf)
- **SciTLDR** (allenai/scitldr): Apache-2.0, about 760 stars, last push 2023-05-22. — [allenai/scitldr](https://github.com/allenai/scitldr)
- **Paper Plain's backend** contains a "GPT-3 Simplification" notebook and a "Term Definitions" notebook. The repo has no licence. — [allenai/paper-plain](https://github.com/allenai/paper-plain)
- **Personalized Jargon Identification** (Guo, Chang, Antoniak, Bransom, Cohen, Wang, August; NAACL 2024): about 10k term-familiarity annotations from 11 CS researchers over 100 abstracts. Prompting that includes the reader's own publications gave the highest accuracy, and zero-shot prompting was a strong baseline. The authors note the small size may limit generalisability. A follow-up, "Explain Less, Understand More" (arXiv 2505.16227), studies data-efficient personalisation of reader-dependent jargon. — [ACL Anthology 2024.naacl-long.255](https://aclanthology.org/2024.naacl-long.255); [arXiv 2311.09481](https://arxiv.org/pdf/2311.09481); [arXiv 2505.16227](https://arxiv.org/pdf/2505.16227)
- **Automatic jargon identifier for scientists engaging with the public** (a word-frequency-based de-jargonizer, PMC article). — [PMC5549884](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5549884/)
- **ScienceDeJargonizer** (ericlee878): no licence, 1 star, last push 2024-06-01. Small hobby or student project. — [GitHub](https://github.com/ericlee878/ScienceDeJargonizer)
- **MAS-Scientific-Text-Simplification** (sandracondee): MIT, 1 star, pushed 2026-09-02. A multi-agent LangGraph system "for simplifying scientific texts while preserving factual accuracy". Toy-scale. — GitHub API search, 2026-10-13

### Inferences
- Fine-tuned T5 and LongT5 simplifiers are permissively licensed but abstract-length and low quality next to current LLMs. Their main value to ResearchBridge is as **baselines** and their **datasets** (PLOS/eLife lay summaries, CELLS, PLABA) as evaluation sets for faithfulness and readability.
- Jargon-familiarity work suggests ResearchBridge's term-explanation trigger could be personalised by reader level, and that zero-shot LLM prompting is a reasonable starting point. This is supported by Guo et al.'s finding that zero-shot was a strong baseline.
- The faithfulness risk in full-paper rewriting (hallucinated "added context") is not solved by any OSS pipeline found. PLABA's finding that conservative models avoid "gratuitous edits or information insertions" highlights the tension with ResearchBridge's "brief added context" goal.

### Gaps
- I did not confirm licences for haining/* models (the HF API required auth), for the CELLS dataset, or for the PLOS/eLife lay-summarisation datasets. Licences of their source text (CC BY for PLOS and eLife) likely carry over, but this was not verified.
- I found no public code or dataset repo for Guo et al.'s jargon work.
- I found no maintained OSS full-document (not just abstract) science simplification pipeline.

---

## Q4. Structured extraction of limitations, COI, funding and statistics: what tools exist?

### Takeaway
For PMC/JATS biomedicine, **rtransparent** (R, GPL-3) is the most directly relevant tool. It extracts COI, funding, protocol registration, and data and code availability from PMC XML, and it was validated across all of PMC OA. It depends on **ODDPub** (R, **AGPL-3.0**), which makes reuse copyleft-heavy. **statcheck** (R, GPL-3, maintained) only recomputes p-values for APA-style reported tests. **RobotReviewer** (GPL-3, risk-of-bias and PICO extraction) has been dormant since 2022. Limitation extraction exists only as research code (BAGELS, LimGen) with no licences. The practical route is to re-implement these heuristics (regex section and statement detectors) in ResearchBridge's own stack, alongside LLM extraction. Use these tools as reference implementations and validation baselines, not as linked code.

### Cited Findings
- **rtransparent** (serghiou/rtransparent): GPL-3 ("GPL-3 + file LICENSE"), R, version 0.2.5, about 15 stars, last push 2024-12-24. It "automatically identifies and extracts indicators of transparency (data availability, code availability, statements of conflicts of interest, statements of funding, statements of protocol registration) from TXT and PMC XML versions of published research articles in biomedicine". It imports `oddpub`, xml2, stringr and tokenizers. It "was validated and subsequently used to extract indicators of transparency from the entire open access literature from PubMed Central" (bioRxiv 10.1101/2020.10.30.361618). A fork exists at nimh-dsst/rtransparent (GPL-3, pushed 2025-11-21), and there is an ETL repo, nimh-dsst/osm-rtrans-etl. — [serghiou/rtransparent](https://github.com/serghiou/rtransparent); [nimh-dsst/rtransparent](https://github.com/nimh-dsst/rtransparent)
- **ODDPub** (quest-bih/oddpub): AGPL-3.0, R, about 45 stars, pushed 2026-08-31. "Algorithm for Open Data Detection in Publications". — [quest-bih/oddpub](https://github.com/quest-bih/oddpub)
- **Barzooka** (quest-bih/barzooka): MIT, Python, 6 stars, last push 2024-08-14. The repo has no description. — [quest-bih/barzooka](https://github.com/quest-bih/barzooka)
- **statcheck** (MicheleNuijten/statcheck): DESCRIPTION licence GPL-3, R, dev version 1.6.1.9000, about 194 stars, pushed 2026-07-03, on CRAN. It "searches for null-hypothesis significance test (NHST) in APA style (e.g., t(28) = 2.2, p < .05). It recalculates the p-value using the reported test statistic and degrees of freedom... [and] will flag the result as an error" if they don't match. — [MicheleNuijten/statcheck](https://github.com/MicheleNuijten/statcheck)
- **RobotReviewer** (ijmarshall/robotreviewer): GPL-3.0, Python, about 179 stars, **last push 2022-07-18**. It provides PICO extraction and automatic Cochrane Risk of Bias assessment from trial PDFs, and runs as docker-compose services including GROBID. The README asks deployers to "Display the text, 'Risk of Bias automation by RobotReviewer (how to cite)' on the same screen". **RRnlp** (bwallace/RRnlp): "NLP for evidence-based medicine", **MIT**, about 18 stars, last push 2023-01-16. **Trialstreamer** (ijmarshall/trialstreamer): no licence, last push 2022-06-24. — [robotreviewer](https://github.com/ijmarshall/robotreviewer); [RRnlp](https://github.com/bwallace/RRnlp); [trialstreamer](https://github.com/ijmarshall/trialstreamer)
- **BAGELS** (EMNLP 2025 Findings): limitation extraction and generation. It extracts limitation sections with science-parse, falls back to regex keyword matching when no section exists, uses LLM filtering, and treats a limitation as a multi-sentence span. It also proposes RAG-based generation. The code repo IbrahimAlAzhar/BAGELS_Limitation_Gen has **no licence**, 2 stars, last push 2025-09-22. — [BAGELS arXiv 2505.18207](https://arxiv.org/pdf/2505.18207); [ACL Anthology 2025.findings-emnlp.1050](https://aclanthology.org/2025.findings-emnlp.1050/)
- **LimGen** generates limitations with LLMs, using ACL 2022–2023 author-written limitations sections as references. Repo arbmf/LimGen: no licence, 2 stars, last push 2024-06-06. **LimTopic** reports that Science Parse "missed many limitations sections because they were sub-sections within other sections". — [LimGen arXiv 2403.15529](https://arxiv.org/pdf/2403.15529); [LimTopic arXiv 2503.10658](https://arxiv.org/pdf/2503.10658)
- **pubmed_parser** (titipata/pubmed_parser): MIT, about 738 stars, pushed 2025-07-31. "A Python Parser for PubMed Open-Access XML Subset and MEDLINE XML Dataset". **s2orc-doc2json** includes JATS2JSON (Apache-2.0). — [pubmed_parser](https://github.com/titipata/pubmed_parser); [s2orc-doc2json](https://github.com/allenai/s2orc-doc2json)
- Open Paper's "Data tables" offer custom extraction schemas over papers with each cell grounded in source (AGPL-3.0). — [khoj-ai/openpaper](https://github.com/khoj-ai/openpaper)

### Inferences
- **Licence interplay**: rtransparent (GPL-3) imports oddpub (AGPL-3.0). Running it as a server-side component would plausibly bring AGPL network obligations. The safest reuse is to run it **offline as a validation and benchmark tool**, or to clean-room re-implement its regex patterns for COI, funding and registration in Python or TypeScript. In JATS, many of these statements are already tagged: `<fn fn-type="COI-statement">`, `<funding-group>`, and the `<sec sec-type>` attribute. This is standard JATS knowledge, not verified in this session.
- statcheck covers only APA-format NHST reporting, which is common in psychology and rare in biomedical or CS papers. It is useful as a narrow consistency check feeding the "statistical significance" summary field, not as a general statistics extractor. Effect sizes, CIs and sample sizes will need LLM extraction with span citations.
- RobotReviewer's models (risk of bias, PICO) are relevant to trial papers but stale. MIT-licensed RRnlp is the more reusable piece, but it is also unmaintained since 2023.
- Limitation extraction has no production-ready OSS. BAGELS's hybrid approach (section detection, then regex fallback, then LLM filter) is a sensible template to re-implement.

### Gaps
- I did not confirm Barzooka's exact function from the repo itself (the GitHub description is blank). From QUEST/BIH's prior publications it is understood to detect bar graphs of continuous data in PDFs, but that is unverified here.
- SciScore: I found no open-source release, and it appears to be a commercial or proprietary service. Not verified in this session.
- Penelope.ai, StatReviewer and similar manuscript checkers were not investigated.
- I did not obtain recall and precision figures for rtransparent's COI and funding detection (they are in the bioRxiv and PLOS Biology paper, which was not fetched).

---

## Q5. Consolidated inventory: repo, licence, language, activity, health, ResearchBridge fit, integration effort and risk

### Takeaway
Ranked shortlist for reuse:
1. PaperQA2 (Apache-2.0) for grounded structured-summary extraction.
2. pdf-component-library / PaperCraft (Apache-2.0 per npm, stale) plus react-pdf, react-pdf-highlighter or pdf.js (MIT/Apache) for anchored overlays, or ar5iv/LaTeXML HTML for arXiv.
3. ScholarPhi (Apache-2.0, stale) as the UX and code reference for inline definitions.
4. open-notebook (MIT) or Kotaemon (Apache-2.0) for notebook and citation-viewer patterns.
5. rtransparent and statcheck (GPL) as offline validators.

Avoid copying code from ChatPaper (CC BY-NC-ND), the unlicensed AI2 prototypes (Paper Plain, Scim) and the AGPL projects (Open Paper, PDFMathTranslate/BabelDOC, ODDPub) unless ResearchBridge itself goes AGPL.

### Cited Findings
All rows come from the GitHub API on 2026-10-13 unless noted. Sources: the repo URLs in the first column.

| Repo | Licence | Lang | Last activity | Health | RB feature | Fit / integration notes |
|---|---|---|---|---|---|---|
| [allenai/papermage](https://github.com/allenai/papermage) | Apache-2.0 | Python | commit 2024-11-08; rel v0.18.0 2024-03 | 815★, 8 contrib; README: research prototype, not maintained | Parsing / span model | Layered doc model with boxes. Unmaintained, so prefer JATS or GROBID/Docling |
| [allenai/pdf-component-library](https://github.com/allenai/pdf-component-library) (PaperCraft) | Apache-2.0 (npm/package.json; no LICENSE file) | TS/React | npm 1.0.2 2024-02-15 | 93★ | (2) reader overlays | Overlay layer for highlights and popovers on react-pdf. PDF-only, stale |
| [allenai/scholarphi](https://github.com/allenai/scholarphi) | Apache-2.0 | Py + TS | commit 2023-03-29 | 427★, 21 contrib | (2) inline term definitions | Best UX reference. Pipeline needs LaTeX + Postgres, heavy. Harvest UI only |
| [allenai/paper-plain](https://github.com/allenai/paper-plain) | **none** | Notebooks | 2022-02-28 | 8★; UI never released | (1)(2)(3) lay aids | Design reference only. No reuse rights |
| [rayfok/scim](https://github.com/rayfok/scim) | **none** | Py | 2024-01-30 | 40★ | Skim highlights | Design reference only |
| CiteSee / Relatedly / Threddy | n/a | n/a | n/a | No public repos found | — | Not reusable |
| [allenai/scitldr](https://github.com/allenai/scitldr) | Apache-2.0 | Py | 2023-05-22 | 760★ | (3) TLDR | Dataset and baseline only |
| [allenai/ai2-scholarqa-lib](https://github.com/allenai/ai2-scholarqa-lib) | Apache-2.0 | Py | 2026-06-25 | 288★ | Multi-paper QA | Literature synthesis, not single-paper explanation |
| [Future-House/paper-qa](https://github.com/Future-House/paper-qa) | Apache-2.0 | Py | rel 2026-08-12 | 9.4k★, 40+ contrib | (3) grounded structured summaries | **Top pipeline candidate**. Chunk-level citations |
| [AkariAsai/OpenScholar](https://github.com/AkariAsai/OpenScholar) | Code Apache-2.0; **weights Llama 3.1 licence** | Py | 2025-08-13 | 1.7k★, 4 contrib | Lit QA | Research code, no releases |
| [stanford-oval/storm](https://github.com/stanford-oval/storm) | MIT | Py | 2025-09-30 | 31.6k★ | — | Wikipedia-style report generation. Low fit |
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | Apache-2.0 | Py | 2026-10-10 | 30k★ | — | Web research agent. Low fit |
| [kaixindelele/ChatPaper](https://github.com/kaixindelele/ChatPaper) | **CC BY-NC-ND 4.0** | Py | 2026-03-02 | 19.9k★ | (3) summaries | **Not reusable** (NC + ND) |
| [karpathy/arxiv-sanity-lite](https://github.com/karpathy/arxiv-sanity-lite) | MIT | Py | 2023-06-19 | 1.7k★ | Discovery | Out of scope |
| [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon) | Apache-2.0 | Py (Gradio) | rel 2026-05-31 | 25.8k★ | Citation highlight viewer | Pattern reference |
| [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook) | MIT | Py + Next.js | rel 2026-10-04 | 40.1k★, 87 contrib | (3) transformations; audio | Healthy. Permissive. Chat and notebook model, not span annotation |
| [souzatharsis/podcastfy](https://github.com/souzatharsis/podcastfy) | Apache-2.0 | Py | 2026-05-04 | 6.6k★ | Optional audio | Add-on |
| [khoj-ai/openpaper](https://github.com/khoj-ai/openpaper) | **AGPL-3.0** | Py + TS | 2026-10-05 | 500★, 6 contrib | (2)(3) reader, explain-selection, grounded tables | Closest product analogue. AGPL blocks code copying |
| [DylanUnicorn/little-alphaxiv](https://github.com/DylanUnicorn/little-alphaxiv) | MIT | TS + FastAPI | 2026-08-21 | 20★ | Reader + chat | Small, permissive scaffold |
| [AsyncFuncAI/alphaxiv-open](https://github.com/AsyncFuncAI/alphaxiv-open) | MIT | Py | 2025-05-24 | 152★ | Reader + chat | Stale |
| [PDFMathTranslate/PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) / [BabelDOC](https://github.com/funstory-ai/BabelDOC) | **AGPL-3.0** | Py | 2026-10 / 2026-08 | 37.5k★ / 9.7k★ | (1) layout-preserving rewrite | Strong technical analogue. AGPL |
| [neuml/paperai](https://github.com/neuml/paperai) / [paperetl](https://github.com/neuml/paperetl) | Apache-2.0 | Py | 2026-07 / 2025-12 | 1.8k★ / 700★ | Ingest and QA | Possible ETL reuse |
| [mozilla/pdf.js](https://github.com/mozilla/pdf.js), [wojtekmaj/react-pdf](https://github.com/wojtekmaj/react-pdf), [react-pdf-highlighter](https://github.com/agentcooper/react-pdf-highlighter) | Apache-2.0 / MIT / MIT | JS/TS | active / active / 2024-11 | 54k★ / 11k★ / 1.4k★ | (2) | Low-risk building blocks |
| [hypothesis/client](https://github.com/hypothesis/client) | BSD-style (NOASSERTION on GitHub) | JS | 2026-10-04 | 737★ | (2) text anchoring | Robust annotation anchoring. Licence text needs review |
| [dginev/ar5iv](https://github.com/dginev/ar5iv) / [LaTeXML](https://github.com/brucemiller/LaTeXML) | MIT / NOASSERTION | CSS / Perl | active | 875★ / 1.3k★ | (1)(2) arXiv HTML | HTML-first rendering for arXiv |
| [serghiou/rtransparent](https://github.com/serghiou/rtransparent) | GPL-3 (imports AGPL oddpub) | R | 2024-12-24 | 15★ | (3) COI, funding, registration, data and code | Use offline or re-implement |
| [quest-bih/oddpub](https://github.com/quest-bih/oddpub) | AGPL-3.0 | R | 2026-08-31 | 45★ | (3) data availability | Copyleft |
| [MicheleNuijten/statcheck](https://github.com/MicheleNuijten/statcheck) | GPL-3 | R | 2026-07-03 | 194★, CRAN | (3) p-value consistency | APA-style only |
| [ijmarshall/robotreviewer](https://github.com/ijmarshall/robotreviewer) / [bwallace/RRnlp](https://github.com/bwallace/RRnlp) | GPL-3 / MIT | Py | 2022-07 / 2023-01 | 179★ / 18★ | (3) RoB, PICO for RCTs | Dormant |
| [quest-bih/barzooka](https://github.com/quest-bih/barzooka) | MIT | Py | 2024-08-14 | 6★ | Figure-quality flag | Niche |
| [BAGELS_Limitation_Gen](https://github.com/IbrahimAlAzhar/BAGELS_Limitation_Gen) / [LimGen](https://github.com/arbmf/LimGen) | **none** | Py / NB | 2025-09 / 2024-06 | 2★ each | (3) limitations | Method reference only |
| [pszemraj/long-t5-tglobal-base-sci-simplify](https://huggingface.co/pszemraj/long-t5-tglobal-base-sci-simplify) | Apache-2.0 (weights) | HF | 2025-12-29 | ~132k downloads | (1) baseline | Baseline only |
| [titipata/pubmed_parser](https://github.com/titipata/pubmed_parser) | MIT | Py | 2025-07-31 | 738★ | JATS ingest | Low-risk |
| [grobidOrg/grobid](https://github.com/grobidOrg/grobid), [docling-project/docling](https://github.com/docling-project/docling), [allenai/olmocr](https://github.com/allenai/olmocr), [datalab-to/marker](https://github.com/datalab-to/marker) | Apache-2.0 / MIT / Apache-2.0 / Apache-2.0 (code) | Java / Py | all active 2026 | 5.2k★ / 68.8k★ / 19.7k★ / 40.4k★ | PDF parsing for DOAJ/PDF-only papers | Likely covered by the parsing research track |

### Inferences
- No single OSS project covers ResearchBridge's combination: a full-paper plain-English rewrite, original-text span-anchored explanations, and a structured critical-appraisal summary. The novel work is the integration and the span-anchored LLM annotation layer.
- **Licence hygiene matters more than code quality here.** Several of the most on-target projects are unlicensed (Paper Plain, Scim, BAGELS, LimGen), non-commercial (ChatPaper) or AGPL (Open Paper, PDFMathTranslate, ODDPub). Permissive and also maintained: PaperQA2, open-notebook, Kotaemon, pdf.js/react-pdf, Docling/GROBID/olmOCR, pubmed_parser.
- Model-weight caution: any Llama-derived science model (OpenScholar-8B) carries the Llama community licence. Small T5 simplifiers are Apache-2.0 but low-capability.

### Gaps
- Bug-backlog and issue-response metrics were not collected. Health is approximated by stars, contributors and last activity.
- The licence texts for marker's model weights, MinerU (GitHub NOASSERTION) and LaTeXML were not read. MinerU is omitted from the shortlist for that reason.
- I did not check whether AI2's newer Asta / Semantic Reader production features (for example LLM-powered paper Q&A in Semantic Reader) have any OSS component beyond those listed.
