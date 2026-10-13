# Reusable open source for ResearchBridge's annotation and per-paper discussion layer

Status as of 2026-10-13. Repo metadata (licence SPDX, language, last push, stars, archived flag) was pulled live from the GitHub REST API via `gh api` on 2026-10-13. Contributor counts are approximate (GitHub contributors endpoint incl. anonymous). "Last push" is any push to any branch; where it mattered I also checked the latest commit on the default branch.

## Hypothesis (h server, client, via): licence, stack, activity, self-hosting, standalone anchoring, PDFs, groups/moderation, API

### Takeaway
Hypothesis is the strongest single thing to reuse. The server, client, Via proxy and extension are all BSD-2-Clause (permissive; the client bundles some MIT code from annotator.js). All of it is very actively maintained in October 2026. The client's anchoring code (quote/position/XPath selectors with fuzzy quote matching, plus a pdf.js integration) is the most battle-tested open-source implementation of W3C-style anchoring. But it lives inside the client repo rather than as a separate package, so reusing it standalone means extracting the code. Self-hosting h is possible but heavyweight (Python + PostgreSQL + Elasticsearch + RabbitMQ), and I found no official statement that self-hosting is supported.

### Cited Findings
- **hypothesis/h** (annotation server): BSD-2-Clause, Python, last push 2026-10-13, ~3,189 stars, ~105 contributors, not archived. Latest commits (2026-09-28) include "Fail closed on empty security-sensitive filters" and "Return a list from GroupService.groups_readable_by()". There have been no formal GitHub releases since v0.39.0 (2019-11-05); it deploys continuously. — [GitHub hypothesis/h](https://github.com/hypothesis/h)
- The h README carries a BSD-2-Clause badge and dev-setup instructions (Docker, pyenv, Node, Yarn). — [h README](https://github.com/hypothesis/h/blob/main/README.md)
- **hypothesis/client** (sidebar and in-page annotator): the GitHub API reports the licence as "NOASSERTION" because LICENSE is BSD-2-Clause ("Copyright (c) 2013-2019 Hypothes.is Project and contributors") plus a "Subcomponents" section. That section puts the bundled annotator.js code under the MIT licence (Copyright 2012 Aron Carroll, Rufus Pollock, Nick Stenning). The README says: "The Hypothesis client is released under the 2-Clause BSD License… Some third-party components are included. They are subject to their own licenses." — [client LICENSE](https://github.com/hypothesis/client/blob/main/LICENSE)
- hypothesis/client: TypeScript/Preact, last push 2026-10-04, ~737 stars, ~80 contributors, tags up to v1.1766.0 (continuous releases). Dependencies include `approx-string-match` (fuzzy string matching), `preact`, `@hypothesis/frontend-shared` and `@hypothesis/annotation-ui`. — [client package.json](https://github.com/hypothesis/client/blob/main/package.json)
- Anchoring code lives at `src/annotator/anchoring/` in the client: `html.ts`, `match-quote.ts`, `pdf.ts`, `placeholder.ts`, `rendered-text.ts`, `text-in-rect.ts`, `text-range.ts`, `trim-range.ts`, `types.ts`, `xpath.ts`. Integrations (`src/annotator/integrations/`) include `html.ts`, `html-side-by-side.ts`, `pdf.tsx`, `pdf-metadata.ts`, `image-text-layer.ts` and `vitalsource.ts`. — [client anchoring dir](https://github.com/hypothesis/client/tree/main/src/annotator/anchoring)
- **@hypothesis/annotation-ui** is a new npm package: "UI components to simplify rendering Hypothesis annotation cards in Preact + Tailwind-based applications". BSD-2-Clause, v1.1.0 published 2025-11-13. — [npm @hypothesis/annotation-ui](https://www.npmjs.com/package/@hypothesis/annotation-ui)
- **hypothesis/via** "Proxies third-party PDF files and HTML pages with the Hypothesis client embedded". BSD-2-Clause, Python, last push 2026-10-12. — [GitHub hypothesis/via](https://github.com/hypothesis/via)
- **hypothesis/browser-extension**: BSD-2-Clause, last push 2026-10-09, ~556 stars. **hypothesis/lms** (LTI app): BSD-2-Clause, last push 2026-10-12. — [browser-extension](https://github.com/hypothesis/browser-extension); [lms](https://github.com/hypothesis/lms)
- **hypothesis/pdf.js-hypothes.is** (PDF.js viewer with Hypothesis embedded): no licence detected by the GitHub API, last push 2025-01-30, ~409 stars. — [GitHub](https://github.com/hypothesis/pdf.js-hypothes.is)
- The client can be "embedded directly into web pages" (publisher embedding docs). — [client README](https://github.com/hypothesis/client) / [embedding docs](https://h.readthedocs.io/projects/client/en/latest/publishers/embedding.html)
- Third-party accounts: publishers "can ask us to register your site as a special kind of OAuth client" and receive a Client ID and secret. With these they generate time-limited "authorization grant tokens" so their own users annotate without logging in again. The docs flag this as "undergoing early-stage testing". — [h docs: authorization grant tokens](https://github.com/hypothesis/h/blob/main/docs/publishers/authorization-grant-tokens.rst)
- API: "The Hypothesis API enables you to create applications and services which read or write data from the Hypothesis service". v1.0 "is the current stable, released API version"; v2.0 "is experimental and under development". There is also a Real Time API (websocket). — [h API docs](https://h.readthedocs.io/en/latest/api/)
- Moderation, flagging: group members can flag an annotation, the group creator is notified and can hide it, and the author is not notified. — [Hypothesis help: Moderation for groups](https://web.hypothes.is/help/moderation-for-groups/)
- Moderation, pre-moderation: new annotations in a group are "not immediately visible until Moderators in the group have a chance to review". Authors see "Pending", and moderators approve or decline. Declined annotations stay hidden and can be edited and resubmitted. — [Hypothesis help: pre-moderation](https://web.hypothes.is/help/pre-moderation-in-the-hypothesis-web-app/)
- Group types: open and restricted groups, plus publisher groups. — [Open and Restricted Groups blog](https://web.hypothes.is/?p=10023); [Publisher Groups blog](https://web.hypothes.is/blog/publisher-groups/)
- Self-hosting: a third-party (unofficial) Zeabur template deploys h with PostgreSQL, Elasticsearch and RabbitMQ. — [Zeabur template](https://zeabur.com/templates/JPAKBM). Hypothesis's own site notes that annotations are usually stored in the Hypothesis service and that some users have deployed independent servers. — [web.hypothes.is](https://web.hypothes.is/?p=9803)
- Hypothesis has hosted preprint-server gatherings on annotating preprints, which is relevant scholarly-publishing context. — [Preprint Services Gather…](https://web.hypothes.is/blog/preprint-services-gather-to-explore-an-annotated-future/)

### Inferences
- The licensing of the whole Hypothesis stack is commercial-friendly: BSD-2 plus MIT subcomponents, attribution only, no copyleft. ResearchBridge could fork the client and server and run them in a closed product.
- Three integration paths, in rising effort:
  1. Embed the hosted Hypothesis client on ResearchBridge paper pages, scoped to a ResearchBridge publisher group, with SSO via authorization grant tokens. This is the lowest effort, but data and moderation stay on Hypothesis's service, and the token mechanism is "early-stage" and needs Hypothesis to register us.
  2. Self-host h plus the client. You get full control, but you inherit Elasticsearch, RabbitMQ and a large Pyramid/Python codebase.
  3. Extract only the anchoring modules (`match-quote.ts`, `text-range.ts`, `xpath.ts`, `html.ts`, `pdf.ts`) plus `approx-string-match` into our own app, and build our own storage and community layer. This is probably the best fit for a Genius-style product that needs voting and editing, which Hypothesis lacks.
- Hypothesis has threaded replies, groups, flagging and pre-moderation. It has no voting, no reputation and no collaborative or wiki editing of an annotation (Genius-style). Those would have to be built on top. This comes from the moderation docs above; I found no voting feature documented.
- Because ResearchBridge renders papers itself (CC-BY HTML/PDF), Via (a proxy for third-party pages) is mostly unnecessary. The pdf.js integration in the client is the relevant part for PDF rendering.

### Gaps
- I found no current official statement on whether Hypothesis supports or recommends self-hosting h in production. Older h docs reportedly discouraged it; this is unverified here.
- I did not confirm the exact API endpoint list for flags and moderation (the API reference page was not fetched in full).
- hypothesis/pdf.js-hypothes.is has no detected licence file. Its licence status needs manual checking (pdf.js itself is Apache-2.0).
- The exact current pre-moderation release date was not confirmed.

## W3C Web Annotation Data Model and libraries implementing it (anchoring; storage interoperability)

### Takeaway
The W3C Web Annotation Data Model (TextQuoteSelector, TextPositionSelector, RangeSelector and so on) is the right storage format for anchors. The dedicated reference library, Apache Annotator, retired from the Apache Incubator on 2025-08-11 and its repo is archived. tilgovi's small `dom-anchor-*` packages are dormant. annotator.js (OKFN) is effectively unmaintained. The live, permissively licensed options are Hypothesis's anchoring code (BSD-2) and Recogito's `@recogito/text-annotator` (BSD-3), which is very active and also ships a PDF package and a React wrapper.

### Cited Findings
- The W3C Web Annotation Data Model is a W3C Recommendation defining selectors such as TextQuoteSelector, TextPositionSelector, XPathSelector and RangeSelector. — [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- **Apache Annotator** (`apache/incubator-annotator`): Apache-2.0, TypeScript. GitHub repo archived, last commit 2024-06-23 ("Ignore .github directory in git archives"), ~241 stars. The Incubator status page records "2016-08-30 Project enters incubation" and "2025-08-11 Project retired from Apache Incubator." — [GitHub](https://github.com/apache/incubator-annotator); [Incubator status page](https://incubator.apache.org/projects/annotator.html)
- **dom-anchor-text-quote** (tilgovi): MIT, JavaScript, last push 2023-07-17, ~35 stars. **dom-anchor-text-position**: MIT, last push 2020-04-01, ~26 stars. — [dom-anchor-text-quote](https://github.com/tilgovi/dom-anchor-text-quote); [dom-anchor-text-position](https://github.com/tilgovi/dom-anchor-text-position)
- **annotator.js** (`openannotation/annotator`): dual-licensed "under the terms of either the MIT or the GNU GPL licenses" (GPLv3+). Last GitHub release v1.2.10 (2015-02-26); latest tag v2.0.0-alpha.3. The 2026-04-11 commits are site/docs only ("site: tweak home to be pure html"). ~2,762 stars, ~42 contributors. — [GitHub openannotation/annotator](https://github.com/openannotation/annotator)
- **Recogito Text Annotator** (`recogito/text-annotator-js`): BSD-3-Clause, TypeScript. Latest commit 2026-10-12 (v4.3.7, "fix/split-selector-page-boundaries"), ~104 stars, ~8 contributors. — [GitHub](https://github.com/recogito/text-annotator-js)
- Text Annotator README: "Also available: React wrapper | TEI/XML extension | Recogito PDF Annotator". "The Text Annotator data model aligns closely with the W3C Web Annotation Data Model, but with a few key differences to optimize for performance". The target selector "provides the selected `quote` and character offsets for `start` and `end`." — [text-annotator README](https://github.com/recogito/text-annotator-js/blob/main/README.md)
- npm: `@recogito/text-annotator` latest 4.3.7 (2026-10-12), BSD-3-Clause. `@recogito/pdf-annotator` latest 4.3.7 (2026-10-12), BSD-3-Clause. — [npm text-annotator](https://www.npmjs.com/package/@recogito/text-annotator); [npm pdf-annotator](https://www.npmjs.com/package/@recogito/pdf-annotator)
- **RecogitoJS** (`recogito/recogito-js`): BSD-3-Clause, archived, description "**deprecated**", last push 2025-09-30. **Recogito2** (`pelagios/recogito2`, full platform): Apache-2.0, Scala, last push 2024-01-30. — [recogito-js](https://github.com/recogito/recogito-js); [recogito2](https://github.com/pelagios/recogito2)
- **Annotorious** (image annotation, same team): BSD-3-Clause, TypeScript, release v3.4.0 (2025-05-27), last push 2026-10-06, ~869 stars. — [GitHub annotorious](https://github.com/annotorious/annotorious)
- **dokieli** (client-side editor for decentralised publishing and annotations, Solid/Linked Data): Apache-2.0, JavaScript, last push 2026-10-12, ~893 stars, ~12 contributors, no GitHub releases. — [GitHub dokieli](https://github.com/dokieli/dokieli)
- **Readium ts-toolkit** (TypeScript toolkit for ebooks/audiobooks/comics): BSD-3-Clause, last push 2026-10-13, ~157 stars. — [GitHub readium/ts-toolkit](https://github.com/readium/ts-toolkit)

### Inferences
- Use W3C selectors as the stored format: TextQuoteSelector (exact, prefix, suffix) + TextPositionSelector, plus a page index for PDFs. Both Hypothesis and Recogito produce or consume these, which keeps human and LLM annotations portable. An LLM pipeline can emit quote selectors directly: the model quotes the passage and we anchor it client-side with fuzzy matching.
- `@recogito/text-annotator` is the most "drop-in library" option for a React app: BSD-3, active, React wrapper and PDF package, decoupled from any backend. Hypothesis's anchoring is more battle-tested on messy real-world pages but is not packaged separately.
- Do not build on Apache Annotator or dom-anchor-* except as reference code. annotator.js is usable under MIT but is legacy jQuery-era code.
- Annotorious is relevant only if ResearchBridge wants annotations on figures or images.
- dokieli and Readium are not a good fit. dokieli is aimed at Solid and decentralised authoring; Readium at EPUB reading systems.

### Gaps
- I did not verify how robust `@recogito/text-annotator`'s re-anchoring is (fuzzy matching vs exact offsets) when document HTML changes.
- I did not check whether Readium has a separate annotation module or specification.
- I did not fetch the W3C implementation report to list which libraries passed conformance tests.

## PDF/HTML annotation UIs (react-pdf-highlighter, pdf.js annotation layer, OSS PSPDFKit alternatives)

### Takeaway
pdf.js (Apache-2.0, very active) is the base layer for any PDF rendering. React highlight libraries built on it exist (react-pdf-highlighter, MIT) but have stalled since late 2024. The most active permissive alternatives are Recogito's PDF Annotator (BSD-3) and EmbedPDF's Apache-2.0 SDK. EmbedPDF's server component is source-available (FCL), not open source. Because ResearchBridge's sources (PMC, PLOS, many arXiv papers) often have HTML or JATS full text, annotating HTML first and treating PDF as secondary would sharply reduce anchoring complexity.

### Cited Findings
- **mozilla/pdf.js**: Apache-2.0, JavaScript, release v6.4.299 (2026-10-03), ~54k stars, ~536 contributors. — [GitHub mozilla/pdf.js](https://github.com/mozilla/pdf.js)
- **react-pdf-highlighter** (agentcooper): MIT, TypeScript, ~1,407 stars, ~27 contributors. Latest tag v4.0.0. Last default-branch commits 2024-09-14 ("Example: remove top level code"); last push 2024-11-22. — [GitHub](https://github.com/agentcooper/react-pdf-highlighter)
- **react-pdf-highlighter-extended** (DanielArnould): MIT, TypeScript, last push 2024-11-22, ~110 stars. — [GitHub](https://github.com/DanielArnould/react-pdf-highlighter-extended)
- **EmbedPDF** (`embedpdf/embed-pdf-viewer`): ~4,548 stars, release v2.15.1 (2026-09-16), tags up to v3.0.0-next.14, last push 2026-10-12. LICENSING.md says "libraries are Apache-2.0; the deployable server product is Fair Source". The EmbedPDF SDK (`@embedpdf/*`) and CloudPDF client libraries are Apache-2.0. `cloudpdf/server` is FCL-1.0-ALv2: "Source-available, not free to run… self-hosting a current FCL-licensed release requires a valid CloudPDF license key." — [EmbedPDF LICENSING.md](https://github.com/embedpdf/embed-pdf-viewer/blob/main/LICENSING.md)
- **Recogito PDF Annotator** (`@recogito/pdf-annotator`): BSD-3-Clause, v4.3.7 (2026-10-12). — [npm](https://www.npmjs.com/package/@recogito/pdf-annotator)
- The Hypothesis client has a dedicated pdf.js integration (`integrations/pdf.tsx`, `anchoring/pdf.ts`). — [client source](https://github.com/hypothesis/client/tree/main/src/annotator/integrations)
- `instructure/pdf-annotate.js` (a formerly popular PDF annotation lib) now returns 404 on the GitHub API; it was removed or renamed. — [GitHub API check](https://github.com/instructure/pdf-annotate.js)
- ResearchHub previously maintained a `pdf2html` C++ repo, now archived (last push 2023-05-11). — [ResearchHub org](https://github.com/ResearchHub)

### Inferences
- For ResearchBridge, prefer rendering HTML/JATS-derived full text where available (PMC, PLOS, eLife, and arXiv HTML for LaTeX papers) and anchor on that HTML. Use pdf.js + Recogito PDF Annotator, or the Hypothesis PDF anchoring, only as a fallback for PDF-only papers.
- react-pdf-highlighter is fine as an MIT starting point but should be treated as "fork and own": no commits since September 2024.
- EmbedPDF's client SDK is usable (Apache-2.0). Avoid its CloudPDF server unless you are prepared to buy a licence.

### Gaps
- I did not verify which annotation/highlight plugins the EmbedPDF SDK ships, or whether they emit W3C selectors.
- I did not evaluate the pdf.js built-in annotation editor (highlight/freetext) for storing annotations outside the PDF.

## Genius-like open-source clones and comparable projects (Fermat's Library, Wikipedia-style editable annotations)

### Takeaway
No maintained open-source "Genius for papers" exists. GitHub Genius clones are student/portfolio projects (Rails + React, abandoned 2017–2022) that anchor by naive character offsets. Fermat's Library and alphaXiv are the closest product analogues but I found no public source code for either. The nearest maintained open-source analogues for community reading and annotation are general-purpose: Hypothesis, plus GPL-licensed scholarly platforms such as Manifold, PubPub and Annotation Studio.

### Cited Findings
- **drj17/Annotator**: "A full-stack web application inspired by Genius" (Rails backend, React frontend). Last push January 2022. — [ecosyste.ms listing](https://awesome.ecosyste.ms/projects/github.com%2Fdrj17%2FAnnotator)
- **samblyon/genius** ("So-Genius"): replicates "RapGenius' signature highlight-based annotation". React + Rails + Postgres. Annotations are stored "according to their start and end indices within lyrics text". Last push 2017. — [ecosyste.ms listing](https://awesome.ecosyste.ms/projects/github.com%2Fsamblyon%2Fgenius)
- **Fermat's Library** provides the "Librarian" Chrome extension for arXiv, which shows BibTeX and reference links on arXiv PDFs. A YC write-up says it also lets users comment on papers. — [arXiv blog developer spotlight](https://blog.arxiv.org/2017/09/28/arxiv-developer-spotlight-librarian-from-fermats-library); [YC blog](https://blog.ycombinator.com/fermats-library-annotating-academic-papers-every-week). Fermat's Library says the project "has since been completely free and open", which refers to access, not a code licence. — [Fermat's Library About](https://fermatslibrary.com/about)
- **alphaXiv**: a line-by-line discussion layer for arXiv papers (swap "arxiv" for "alphaxiv" in the URL), built by Stanford students and opened publicly in December 2023. It offers comment categories and private annotations, and has published community guidelines. — [Gigazine](https://gigazine.net/gsc_news/en/20240909-alphaxiv-arxiv-open-discussion); [Analytics India Mag](https://analyticsindiamag.com/ai-news-updates/stanford-ai-lab-unveils-alphaxiv-an-open-discussion-forum-for-arxiv-papers); [alphaXiv guidelines](https://alphaxiv.org/guidelines); [alphaXiv one-year blog](https://alphaxiv.org/blog/one-year)
- **Manifold** (`ManifoldScholar/manifold`, "Transforming scholarly publications into living digital works"): GPL-3.0, JavaScript, last push 2026-10-12, ~260 stars. — [GitHub](https://github.com/ManifoldScholar/manifold)
- **PubPub** (`knowledgefutures/pubpub`, "Open Community Publishing"): GPL-2.0, TypeScript, last push 2026-10-07, ~545 stars. — [GitHub](https://github.com/knowledgefutures/pubpub)
- **Annotation Studio** (`hyperstudio/Annotation-Studio`, "online annotation platform for teaching and learning in the humanities"): GPL-2.0, last push 2026-02-17, ~108 stars. — [GitHub](https://github.com/hyperstudio/Annotation-Studio)
- Genius's own early beta raised the problem of anchoring annotations when the underlying text changes. — [HN discussion](https://home5.southeastasia.cloudapp.azure.com/item?id=9244403) (mirror of HN item 9244403)

### Inferences
- The Genius-specific mechanics would have to be built by us in any scenario: one canonical, community-edited explanation per passage with vote-ranked alternatives, edit history and reputation. Hypothesis's model is many independent annotations plus replies, not one editable, voted explanation. The clone repos are useful only as UX references.
- Manifold and PubPub have in-text annotation or discussion, but they are GPL (copyleft). Code copied into a distributed product triggers GPL obligations. For a hosted web service, GPL-2/3 (unlike AGPL) does not require releasing server code. Still, mixing GPL front-end JS that is shipped to browsers is a distribution and carries risk. Treat them as design references, not code donors, unless the team accepts GPL.
- Wikipedia-style editable annotations could be modelled with a revision table per annotation (MediaWiki-like). I found no reusable open-source component for this specific pattern.

### Gaps
- Searches found no public repository or licence for alphaXiv or Fermat's Library Librarian; treat both as closed source (unconfirmed).
- I did not verify the specific annotation features of Manifold and PubPub (for example whether PubPub discussions anchor to text ranges) from their docs in this session.
- I found no open-source "Wikipedia-style editable annotation" project.

## Embeddable per-page discussion/forum components (Discourse, Coral, Remark42, Commento, Isso, Giscus/Utterances, Lemmy, others)

### Takeaway
For a commercial-friendly per-paper thread, the permissive, active options are:

- **Coral** (Apache-2.0; Vox Media; the strongest moderation tooling; Node/MongoDB/Redis)
- **Remark42** (MIT; Go; built-in voting, pinning and moderation)
- **Isso** (MIT; Python/SQLite; moderation queue)
- **Comentario** (MIT; the maintained Commento fork)
- **Artalk** (MIT; Go)

Discourse (GPL-2.0) is the richest community/reputation system. Its embed is read-only on the host page (replies happen on the forum), and running it unmodified as a separate service carries little licence risk. Lemmy is AGPL-3.0. Cusdis is archived (GPL-3.0). Original Commento is abandoned. Giscus and Utterances require GitHub accounts, which is unsuitable for a general audience.

### Cited Findings
- **Discourse**: GPL-2.0, Ruby, last push 2026-10-13, ~47,967 stars, ~1,198 contributors, tags up to v2026.10.0-latest. — [GitHub discourse/discourse](https://github.com/discourse/discourse)
- Discourse embedding works like this:
  - "you are linking a document… with a single topic", so it is one topic per page. The topic is auto-created on first page load, or linked via `topicId`.
  - Readers cannot reply from the embedded widget; they must go to the forum. This is described as intentional.
  - An `/embed/info` endpoint (API key) returns a page's topic ID and comment count.
  - For private forums, comments show only if Discourse is on a subdomain of the host.
  - Topics are keyed to the embed URL.

  — [Discourse Meta: Embed Discourse comments](https://meta.discourse.org/t/embed-discourse-comments-on-another-website-via-javascript/31963)
- **Coral** (`coralproject/talk`): the API reports "NOASSERTION", but LICENSE is Apache-2.0 ("Copyright 2025 Vox Media, Inc"). TypeScript, release v9.11.8 (2026-07-07), last push 2026-09-04, ~1,999 stars, ~75 contributors. — [Coral LICENSE](https://github.com/coralproject/talk/blob/main/LICENSE)
- Coral docs: "Our open-source commenting platform, Coral, reimagines moderation, comment display, and conversation". Install via published Docker images or source. Requirements listed as MongoDB ^8.0.3, Redis ^3.2, NodeJS ^18.16.0, PNPM ^8.0; the docs' Docker examples use MongoDB 4.2, an internal inconsistency. — [Coral docs](https://docs.coralproject.net/)
- **Remark42**: MIT, Go, release v1.18.0 (2026-10-11), ~5,624 stars, ~168 contributors. Features: social login (Google, GitHub, Apple and others, plus custom OAuth2); "Moderator can remove comments and block users"; "Voting, pinning and verification system"; sortable comments; image upload; RSS per post; admin notifications (Telegram/Slack/webhook/email); user reply notifications; import from Disqus and WordPress. — [GitHub umputun/remark42](https://github.com/umputun/remark42)
- **Isso**: MIT, Python, release 0.14.0 (2026-03-26), ~5,312 stars, ~149 contributors. SQLite backend. "Comments in moderation queue are not publicly visible before activation." — [GitHub isso-comments/isso](https://github.com/isso-comments/isso)
- **Commento** (original, gitlab.com/commento/commento): MIT. Last commit 2021-02-28, so effectively abandoned. — [GitLab commento](https://gitlab.com/commento/commento)
- **Commento++** (`souramoo/commentoplusplus`): MIT, Go, last push 2023-06-27 (dormant). — [GitHub](https://github.com/souramoo/commentoplusplus)
- **Comentario** (Commento fork): MIT, last commit 2026-10-09, ~110 GitLab stars. — [GitLab comentario](https://gitlab.com/comentario/comentario)
- **Artalk**: MIT, Go, release v2.10.0 (2026-07-24), last push 2026-10-11, ~2,347 stars. — [GitHub ArtalkJS/Artalk](https://github.com/ArtalkJS/Artalk)
- **Giscus** ("commenting system powered by GitHub Discussions"): MIT, TypeScript, last commit 2026-05-25, ~12,149 stars. — [GitHub giscus](https://github.com/giscus/giscus)
- **Utterances** ("comments widget built on GitHub issues"): MIT, last push 2024-08-15 (dormant). — [GitHub utterances](https://github.com/utterance/utterances)
- **Lemmy** ("decentralised discussion platform", federated): AGPL-3.0, Rust, release 0.19.20 (2026-07-21), ~14,626 stars, ~302 contributors. — [GitHub LemmyNet/lemmy](https://github.com/LemmyNet/lemmy)
- **Cusdis**: GPL-3.0, archived (last push 2026-07-17). — [GitHub djyde/cusdis](https://github.com/djyde/cusdis)

### Inferences
- Licence risk ranking for a possibly commercial product:
  - **Low risk:** Coral (Apache-2.0, includes a patent grant), Remark42, Isso, Comentario, Artalk, Giscus (MIT).
  - **Moderate risk:** Discourse (GPL-2.0). Running it unmodified as a separate service and embedding via JS/iframe is generally fine. Modifying and distributing it triggers GPL. GPL-2 has no network clause, so hosting even a modified copy does not by itself require releasing source.
  - **High risk if modified:** Lemmy and OpenReview-web (AGPL-3.0). Network use of a modified version requires offering source to users.
- Best fit for "per-paper thread with voting and moderation, embedded inline":
  - **Remark42:** lightweight; voting, pinning and moderation out of the box; MIT.
  - **Coral:** heavier, newsroom-grade moderation tooling.
  - **Discourse:** best for reputation (trust levels, badges) and long-form community, but replying happens off-page, which hurts the inline-reading UX.
- An alternative is to skip a separate comment engine: model the per-paper thread as annotations whose target is the whole document (W3C allows a target without selector). That gives one data model and one moderation queue for passage annotations and paper-level discussion; Hypothesis's page notes work this way.

### Gaps
- Coral's specific features were not verified from primary docs in this session: toxicity scoring via Perspective API, reactions ("Respect"), featured comments, SSO. Older public descriptions say it has these; confirm before relying on them.
- I did not verify whether Discourse's newer embedding options allow inline replying.
- No 2026 information was gathered on Remark42/Isso scaling limits.

## Science-specific open-source community/review platforms (PubPeer, PREreview, Sciety, ResearchHub, Kotahi/Libero, OpenReview, alphaXiv)

### Takeaway
Several science platforms are open source under MIT: PREreview, Sciety (eLife-born), the eLife Enhanced Preprints client, ResearchHub's Django backend and new web front end, and OpenReview's Python and JS clients. These are valuable as reference architectures and possibly for code (for example, ResearchHub's comment/voting/reputation models). OpenReview's web UI is AGPL-3.0 and its core API server does not appear to be public. PubPeer and alphaXiv have no public source that I could find. Kotahi's licence could not be verified (the Coko GitLab was unreachable).

### Cited Findings
- **PREreview** (`PREreview/prereview.org`): MIT, TypeScript, last push 2026-10-12, ~15 stars. The README describes it as "The source code for prereview.org" (Docker, Docker Compose, Make). — [GitHub](https://github.com/PREreview/prereview.org)
- **Sciety** (`sciety/sciety`, "Where research is evaluated and curated by the communities you trust"): MIT, TypeScript, last push 2026-10-12, ~17 stars. "Developed and maintained by Sciety's remote first ensemble programming team." — [GitHub](https://github.com/sciety/sciety)
- **eLife Enhanced Preprints client**: MIT, TypeScript, last push 2026-10-02. — [GitHub elifesciences/enhanced-preprints-client](https://github.com/elifesciences/enhanced-preprints-client)
- **ResearchHub**:
  - `researchhub-backend` ("Django API for researchhub.com"): MIT, Python, last push 2026-10-13.
  - `researchhub-web` (Next.js): MIT, archived 2025-06-27.
  - A newer `ResearchHub/web` repo: MIT, TypeScript, last push 2026-10-12.
  - `pdf2html`, `researchhub-word-plugin` and `ckeditor-custom-public` are archived.

  — [ResearchHub GitHub org](https://github.com/ResearchHub); [researchhub-backend](https://github.com/ResearchHub/researchhub-backend)
- **OpenReview**:
  - `openreview-web`: AGPL-3.0, JavaScript, last push 2026-10-12.
  - `openreview-py` (API client): MIT. `openreview-js`: MIT. `openreview-expertise` (reviewer matching): MIT.
  - `openreview/openreview` is documentation only.
  - No core API server repo appears in the org listing.

  — [OpenReview GitHub org](https://github.com/openreview). OpenReview's About page says the web interface is AGPL-3.0 and that some further releases are pending a professional security review. — [OpenReview About](https://openreview.net/about)
- Other open-source scholarly publishing platforms, all copyleft:
  - **Janeway** (`openlibhums/janeway`): AGPL-3.0, Python, active 2026-10-10. — [GitHub](https://github.com/openlibhums/janeway)
  - **OJS** (`pkp/ojs`): GPL-3.0, PHP, active 2026-10-12. — [GitHub](https://github.com/pkp/ojs)
- **alphaXiv**: no public repo or licence found (see Genius section). — [alphaXiv one-year blog](https://alphaxiv.org/blog/one-year)

### Inferences
- **ResearchHub backend** (MIT, Django) is the most directly "cannibalisable" science-community codebase. It is a live production system for paper discussion with voting and reputation, under a permissive licence. Its data models for threaded comments, votes and reputation could be studied or lifted.
- **PREreview and Sciety** (both MIT, TypeScript) are review and curation aggregators rather than inline annotation tools. They are useful for DOI-keyed paper pages, review ingestion (Sciety ingests evaluations from Hypothesis groups, PREreview and others) and the "docmaps"-style evaluation model.
- **OpenReview** is unsuitable as a code base: AGPL front end, and the backend is not public. Its public API can still be used to ingest reviews for ML/CS papers.
- **PubPeer, alphaXiv and Fermat's Library** are product references only.

### Gaps
- PubPeer: I did not check for any public source; it is generally understood to be closed source. Unverified in this session.
- Kotahi (Coko Foundation) licence and activity: `gitlab.coko.foundation` was unreachable and web searches returned nothing relevant. Kotahi is believed to be MIT-licensed, but this is unverified. Libero (eLife's earlier publishing suite) status was not checked.
- I did not check whether ResearchHub's backend has a separable comments/voting app or how coupled it is to their token (ResearchCoin) economics.
- The claim that Sciety ingests Hypothesis-group evaluations is from prior knowledge, not verified this session.

## Candidate inventory (repo, licence, language, recency, health, fit)

### Takeaway
Recommended core stack for ResearchBridge, all permissive:
- **Rendering:** pdf.js for PDFs; HTML/JATS rendering for the rest.
- **Anchoring and UI:** either `@recogito/text-annotator` (+ `@recogito/pdf-annotator`) for library-style integration, or code extracted from the Hypothesis client's anchoring modules.
- **Storage:** W3C Web Annotation JSON in our own Postgres. Alternatively, self-host Hypothesis h if we want its groups and moderation as-is.
- **Community features:** Remark42 or Coral for the per-paper thread, or build threads, votes and edit history ourselves, using ResearchHub's MIT backend as a reference.

Avoid copyleft code (Discourse GPL-2 if modified; Manifold GPL-3; PubPub GPL-2; Lemmy, Janeway and OpenReview-web AGPL-3) unless the team accepts the obligations.

### Cited Findings
All rows are from GitHub/GitLab/npm API queries on 2026-10-13; the URLs are the sources.

| Project | URL | Licence | Lang | Last activity | Health | Covers | Fit / risk |
|---|---|---|---|---|---|---|---|
| Hypothesis h | https://github.com/hypothesis/h | BSD-2-Clause | Python | push 2026-10-13 | 3.2k★, ~105 contrib | (b) storage/API, groups, moderation | High fit; heavy self-host (PG+ES+RabbitMQ) |
| Hypothesis client | https://github.com/hypothesis/client | BSD-2 (+MIT subcomponent) | TS/Preact | push 2026-10-04, v1.1766.0 | 737★, ~80 contrib | (a) anchoring HTML+PDF, sidebar UI, threads | High fit; anchoring not packaged standalone |
| @hypothesis/annotation-ui | https://www.npmjs.com/package/@hypothesis/annotation-ui | BSD-2-Clause | TS/Preact+Tailwind | 1.1.0, 2025-11-13 | new | UI cards | Medium; Preact not React |
| Hypothesis Via | https://github.com/hypothesis/via | BSD-2-Clause | Python | push 2026-10-12 | 30★ | proxy | Low (we host content ourselves) |
| pdf.js-hypothes.is | https://github.com/hypothesis/pdf.js-hypothes.is | none detected | JS | push 2025-01-30 | 409★ | PDF viewer + Hypothesis | Check licence |
| Apache Annotator | https://github.com/apache/incubator-annotator | Apache-2.0 | TS | **archived**; retired 2025-08-11 | 241★ | (a) W3C selectors | Reference only |
| dom-anchor-text-quote | https://github.com/tilgovi/dom-anchor-text-quote | MIT | JS | 2023-07 | 35★ | (a) | Dormant |
| dom-anchor-text-position | https://github.com/tilgovi/dom-anchor-text-position | MIT | JS | 2020-04 | 26★ | (a) | Dormant |
| Recogito text-annotator | https://github.com/recogito/text-annotator-js | BSD-3-Clause | TS | v4.3.7, 2026-10-12 | 104★, ~8 contrib | (a) HTML anchoring + UI, React wrapper, PDF pkg | High fit; small team |
| Recogito PDF annotator | https://www.npmjs.com/package/@recogito/pdf-annotator | BSD-3-Clause | TS | 4.3.7, 2026-10-12 | — | (a) PDF | High fit |
| RecogitoJS | https://github.com/recogito/recogito-js | BSD-3-Clause | JS | **archived/deprecated** | 404★ | (a) | Avoid |
| Recogito2 | https://github.com/pelagios/recogito2 | Apache-2.0 | Scala | 2024-01 | 165★ | platform | Low |
| Annotorious | https://github.com/annotorious/annotorious | BSD-3-Clause | TS | v3.4.0 2025-05; push 2026-10-06 | 869★ | figure/image annotation | Optional |
| annotator.js (OKFN) | https://github.com/openannotation/annotator | MIT or GPL-3 (choice) | JS | last release 2015; docs-only commits 2026-04 | 2.8k★ | (a) | Legacy; avoid |
| dokieli | https://github.com/dokieli/dokieli | Apache-2.0 | JS | push 2026-10-12 | 893★, ~12 contrib | Solid-based annotation/authoring | Low fit |
| Readium ts-toolkit | https://github.com/readium/ts-toolkit | BSD-3-Clause | TS | push 2026-10-13 | 157★ | EPUB reading | Low fit |
| pdf.js | https://github.com/mozilla/pdf.js | Apache-2.0 | JS | v6.4.299, 2026-10-03 | 54k★, ~536 contrib | PDF rendering | Essential base |
| react-pdf-highlighter | https://github.com/agentcooper/react-pdf-highlighter | MIT | TS | last commit 2024-09-14 | 1.4k★ | (a) PDF highlight UI | Fork-and-own |
| react-pdf-highlighter-extended | https://github.com/DanielArnould/react-pdf-highlighter-extended | MIT | TS | 2024-11 | 110★ | (a) | Dormant |
| EmbedPDF SDK | https://github.com/embedpdf/embed-pdf-viewer | Apache-2.0 (SDK); FCL-1.0 (server) | TS | v2.15.1 2026-09-16 | 4.5k★ | PDF viewer | OK for SDK; avoid server |
| Discourse | https://github.com/discourse/discourse | GPL-2.0 | Ruby | 2026-10-13 | 48k★, ~1.2k contrib | (c) forum, trust levels, embed | Strong features; GPL; off-page replies |
| Coral (Talk) | https://github.com/coralproject/talk | Apache-2.0 | TS | v9.11.8 2026-07-07 | 2.0k★, ~75 contrib | (c) comments + moderation | High fit; Mongo/Redis |
| Remark42 | https://github.com/umputun/remark42 | MIT | Go | v1.18.0 2026-10-11 | 5.6k★, ~168 contrib | (c) comments, voting, moderation | High fit, light |
| Isso | https://github.com/isso-comments/isso | MIT | Python | 0.14.0 2026-03-26 | 5.3k★ | (c) comments, mod queue | Medium (simple) |
| Comentario | https://gitlab.com/comentario/comentario | MIT | Go | 2026-10-09 | 110★ (GitLab) | (c) | Medium |
| Commento | https://gitlab.com/commento/commento | MIT | Go | last commit 2021-02 | — | (c) | **Abandoned** |
| Commento++ | https://github.com/souramoo/commentoplusplus | MIT | Go | 2023-06 | 433★ | (c) | Dormant |
| Artalk | https://github.com/ArtalkJS/Artalk | MIT | Go | v2.10.0 2026-07-24 | 2.3k★ | (c) | Medium |
| Giscus | https://github.com/giscus/giscus | MIT | TS | 2026-05-25 | 12k★ | (c) via GitHub Discussions | Low (GitHub login) |
| Utterances | https://github.com/utterance/utterances | MIT | TS | 2024-08 | 9.7k★ | (c) via GitHub Issues | Dormant; low |
| Cusdis | https://github.com/djyde/cusdis | GPL-3.0 | TS | **archived** | 2.8k★ | (c) | Avoid |
| Lemmy | https://github.com/LemmyNet/lemmy | AGPL-3.0 | Rust | 0.19.20 2026-07-21 | 14.6k★ | (c) federated forum | AGPL risk |
| PREreview | https://github.com/PREreview/prereview.org | MIT | TS | 2026-10-12 | 15★ | preprint reviews | Reference |
| Sciety | https://github.com/sciety/sciety | MIT | TS | 2026-10-12 | 17★ | evaluation aggregation | Reference |
| eLife EPP client | https://github.com/elifesciences/enhanced-preprints-client | MIT | TS | 2026-10-02 | 2★ | preprint+review display | Reference (article rendering) |
| ResearchHub backend | https://github.com/ResearchHub/researchhub-backend | MIT | Python/Django | 2026-10-13 | 49★ | (b)(c) paper discussion, votes, reputation | Good reference/code donor |
| ResearchHub web | https://github.com/ResearchHub/web | MIT | TS | 2026-10-12 | — | front end | Reference (old researchhub-web archived 2025-06-27) |
| OpenReview web | https://github.com/openreview/openreview-web | AGPL-3.0 | JS | 2026-10-12 | 67★ | review UI | AGPL; backend not public |
| openreview-py | https://github.com/openreview/openreview-py | MIT | Python | 2026-10-12 | 270★ | API client | Ingest reviews |
| Manifold | https://github.com/ManifoldScholar/manifold | GPL-3.0 | JS | 2026-10-12 | 260★ | scholarly reading + annotation | GPL; reference |
| PubPub | https://github.com/knowledgefutures/pubpub | GPL-2.0 | TS | 2026-10-07 | 545★ | community publishing + discussions | GPL; reference |
| Annotation Studio | https://github.com/hyperstudio/Annotation-Studio | GPL-2.0 | HTML/Ruby | 2026-02-17 | 108★ | teaching annotation | GPL; reference |
| Janeway | https://github.com/openlibhums/janeway | AGPL-3.0 | Python | 2026-10-10 | 239★ | journal/preprint platform | AGPL; out of scope |
| OJS | https://github.com/pkp/ojs | GPL-3.0 | PHP | 2026-10-12 | 1.0k★ | journal management | Out of scope |
| drj17/Annotator (Genius clone) | https://github.com/drj17/Annotator | unknown | Rails/React | 2022-01 | — | Genius UX | UX reference only |
| samblyon/genius (So-Genius) | https://github.com/samblyon/genius | unknown | Rails/React | 2017 | — | Genius UX | UX reference only |

### Inferences
- Lowest-effort MVP path:
  1. Render HTML full text.
  2. Integrate `@recogito/text-annotator` (React).
  3. Store W3C annotations (TextQuote + TextPosition selectors) in Postgres.
  4. Add our own `votes`, `annotation_revisions` and `reports` tables.
  5. Treat LLM explanations as annotations with `creator` = model and `motivation` = "explaining" or "describing" (W3C motivations).
  6. Embed Remark42 (MIT) or build a simple threaded-comment model for per-paper discussion.

  This gives Genius-style community editing plus LLM annotations on one data model without copyleft exposure.
- Highest-leverage path if the team prefers "adopt rather than build": self-host Hypothesis (h + client, BSD-2) and extend it with voting and canonical-explanation editing. You get production-grade anchoring, groups, flagging and pre-moderation immediately, but must maintain a fork of a large Python/Elasticsearch system.
- Attribution obligations: BSD-2/BSD-3/MIT/Apache-2.0 require preserving copyright and licence notices. Apache-2.0 also requires preserving NOTICE files and stating changes.

### Gaps
- Licences for the Genius clone repos (drj17/Annotator, samblyon/genius) were not checked.
- Star counts and contributor counts are rough health signals only. Issue-response times and bus factor were not assessed.
- Kotahi, Libero and PubPeer could not be evaluated (see previous section).
