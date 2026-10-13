# Lay summarisation and faithfulness of plain-language rewrites: research landscape and reusable assets (as of Oct 2026)

Scope: datasets, shared tasks, faithfulness metrics, failure modes, human-evaluation protocols, LLM vs human evidence, and readability/jargon measures. These are the inputs for the ResearchBridge §2.2 faithfulness benchmark, which also bears on §2.1 (annotation model). Licences were checked against the GitHub API (`license.spdx_id`) and the Hugging Face API (`cardData.license`) on 2026-10-13 unless noted otherwise. "None detected" means the repo has no recognised LICENSE file, so default copyright applies: there is no reuse grant.

---

## 1. Lay summarisation datasets and shared tasks: size, domain, licence

### Takeaway
Most of the major corpora are biomedical. The datasets with the cleanest licences for a commercial-leaning product are eLife/PLOS (HF card CC-BY-4.0, built from CC-BY journals) and PLABA (CC0 on OSF). Cochrane-derived and news-derived sets (Cochrane simplification, SciNews) are tagged CC-BY on GitHub or HF, but the underlying text belongs to Wiley/Cochrane and to Science X respectively, so treat them as research-only. Nothing large exists outside biomedicine except SciNews (9 disciplines) and SciTLDR (CS, TLDRs only).

### Cited Findings
**eLife and PLOS (Goldsack et al., EMNLP 2022)**
- These are full biomedical research articles paired with expert-written lay summaries. Splits: PLOS 24,773 / 1,376 / 1,376 and eLife 4,346 / 241 / 241 (train/val/test). The HF dataset card licence is **cc-by-4.0**. The card says nothing about the licences of the source articles — [HF tomasg25/scientific_lay_summarisation](https://huggingface.co/datasets/tomasg25/scientific_lay_summarisation)
- PLOS lay summaries are author-written and come from 5 PLOS journals (Biology, Comp Bio, Genetics, Pathogens, NTD). eLife lay summaries ("digests") are written by expert editors with the authors, and are longer, more abstractive and more readable than PLOS ones — [BioLaySumm 2025 overview](https://aclanthology.org/2025.bionlp-1.31)
- The original repo hosts the data on Google Drive (PLOS ~1.3 GB, eLife ~330 MB). No licence file was detected on the repo — [GitHub TGoldsack1/Corpora_for_Lay_Summarisation](https://github.com/TGoldsack1/Corpora_for_Lay_Summarisation); [paper](https://aclanthology.org/2022.emnlp-main.724)
- The paper's human evaluation was small: 2 domain experts judged 10 test articles per dataset, with BART outputs shown alongside the abstract and the reference lay summary — [arXiv 2210.09932](https://arxiv.org/pdf/2210.09932)

**BioLaySumm shared tasks (BioNLP 2023, 2024, 2025)**
- **2024**: 53 teams and more than 200 submissions; 14 teams wrote system papers. Evaluation was **automatic only**, with no human evaluation. Criteria: Relevance (ROUGE-1/2/L, BERTScore), Readability (FKGL, Dale-Chall, Coleman-Liau, LENS), Factuality (AlignScore, SummaC). AlignScore and SummaC replaced a fine-tuned BARTScore, which had favoured BART systems. The organisers note that AlignScore and SummaC **favour extractive outputs**, so factuality trades off against relevance and readability, especially on the abstractive eLife data — [BioLaySumm 2024 overview, arXiv 2408.08566](https://arxiv.org/html/2408.08566v1)
- **2025** (3rd edition, ACL 2025): Task 1.1 is plain lay summarisation on PLOS and eLife (eLife test = 142; the PLOS test set varies by subtask). Task 1.2 requires external knowledge (RAG, definitions). Task 2 is new: layman's radiology reports. Factuality is still AlignScore and SummaC. BLEU, METEOR and semantic similarity were added for relevance. 13 teams wrote system papers. Baselines were Qwen2.5-7B and LLaMA3-8B fine-tunes — [BioLaySumm 2025 overview](https://aclanthology.org/2025.bionlp-1.31)
- 2025 findings: "No single system dominated." For example, the SUWMT system was 1st on relevance (ROUGE 0.370) with FKGL 11.74, while MetinOZU had SummaC 0.920 but **FKGL 16.45**, meaning high factuality only by staying close to the source. RAG teams in Subtask 1.2 gained 7–9% factuality over non-RAG baselines but "sometimes disrupted narrative coherence." The organisers list the "persistent conflicts between readability and factuality" as challenge #1 — [BioLaySumm 2025 overview](https://aclanthology.org/2025.bionlp-1.31)
- The BioLaySumm 2025 HF datasets (`BioLaySumm/BioLaySumm2025-eLife`, `-PLOS`) have **no licence field set** on the HF card — [HF API](https://huggingface.co/datasets/BioLaySumm/BioLaySumm2025-eLife)
- A 2025 participant used AlignScore, SummaC, ROUGE-L, BERTScore, LENS, FKGL, DCRS and CLI as an RL reward, raising AlignScore from 0.722 to 0.862 on validation. This shows the metrics are **directly optimisable, and therefore gameable** — [ACL Anthology, Sicheng Shen](https://aclanthology.org/people/sicheng-shen)

**CELLS (Guo et al.)**
- A parallel corpus of abstracts and lay summaries from biomedical journals with lay-summary sections. The abstract reports 63k pairs from 12 journals. The arXiv version reports 75,205 pairs after filtering (eLife, Ann Rheum Dis and Reproductive Health were excluded as outliers), so **the counts conflict across versions** — [arXiv 2211.03818](https://arxiv.org/pdf/2211.03818); [DeepAI listing](https://deepai.org/publication/cells-a-parallel-corpus-for-biomedical-lay-language-generation)
- The repo `LinguisticAnomalies/pls_retrieval` is licensed **MIT** — [GitHub](https://github.com/LinguisticAnomalies/pls_retrieval)

**PLABA (NLM; Attal, Ondov & Demner-Fushman, Sci Data 2023)**
- 750 PubMed abstracts (75 consumer questions × 10 abstracts) with 921 manually written, sentence-aligned gold adaptations — [arXiv 2210.12242](https://arxiv.org/pdf/2210.12242)
- The data is on OSF (osf.io/rnpmf) under **CC0 1.0 Universal**, according to the OSF API licence field. The code repo `attal-kush/PLABA` has no licence detected — [OSF API](https://api.osf.io/v2/nodes/rnpmf/); [GitHub README](https://github.com/attal-kush/PLABA)
- It became the TREC PLABA track (2023, 2024). Manual judgments by biomedical experts covered factual accuracy, completeness, simplicity and brevity. Top LLM systems **matched human references on factual accuracy and completeness, but not on simplicity or brevity**. Reference-based automatic metrics "generally did not correlate well" with manual judgments. In Task 2C, contractors rated outputs on a 3-point symmetric Likert scale, rescaled to 0–100 — [Lessons from TREC PLABA, arXiv 2507.14096](https://arxiv.org/abs/2507.14096); [TREC PLABA data](https://trec.nist.gov/data/plaba.html)
- A follow-up called PLABA-EVAL has 78 abstracts with expert adaptations (609 sentences) and three independent raters per document — [search summary of 2026.readi-1.4](https://aclanthology.org/2026.readi-1.4/) (only the snippet was seen; verify before relying on it)

**Cochrane simplification (Devaraj et al., NAACL 2021)**
- About 4,500 pairs of Cochrane abstracts and plain-language summaries for paragraph-level medical simplification — [HF GEM/cochrane-simplification](https://huggingface.co/datasets/GEM/cochrane-simplification)
- The GitHub repo is tagged **CC-BY-4.0**, and the GEM HF card says cc-by-4.0. The data is produced by scraping the Cochrane website — [GitHub AshOlogn/Paragraph-level-Simplification-of-Medical-Texts](https://github.com/AshOlogn/Paragraph-level-Simplification-of-Medical-Texts)
- However, Cochrane Library content is reused under Wiley permissions through RightsLink. Free republication of abstracts and PLS is granted only to registered Cochrane groups, with citation — [Cochrane Library permissions](https://cochranelibrary.com/en/help/permissions); [Cochrane documentation](https://documentation.cochrane.org/x/GBr-Bg)

**SciNews (Liu/Pu et al., LREC-COLING 2024)**
- Papers paired with Science X news reports across 9 disciplines: 41,872 samples, split 80/10/10 — [arXiv 2403.17768](https://arxiv.org/abs/2403.17768v2)
- The HF card says **cc-by-4.0**, but the dataset is **gated** (login and access request needed) — [HF dongqi-me/SciNews](https://huggingface.co/datasets/dongqi-me/SciNews)

**SciTLDR (AI2, Cachola et al., 2020)**
- 5.4K TLDRs over 3.2K CS papers, both author-written and expert-derived — [arXiv 2004.15011](https://arxiv.org/abs/2004.15011)
- The GitHub repo is **Apache-2.0**, while the HF card licence is "unknown". The split is 60/20/20 — [GitHub allenai/scitldr](https://github.com/allenai/scitldr); [HF allenai/scitldr](https://huggingface.co/datasets/allenai/scitldr)

**Paper Plain (August et al., ACM TOCHI 2023, AI2)**
- An interactive reader for medical papers with term definitions, in-situ section summaries, key questions linking to answering passages, and plain-language summaries of those passages. Users found papers easier to read **with no loss of comprehension** compared with a standard PDF reader. Readers used passage summaries more than definition tooltips. Testers **cross-checked summaries against the source** because summaries could be vague. The design lesson is to supplement the original text rather than replace it — [arXiv 2203.00130](https://arxiv.org/pdf/2203.00130)
- The related AI2 ScholarPhi reader (position-sensitive definitions) is **Apache-2.0** — [GitHub allenai/scholarphi](https://github.com/allenai/scholarphi). The `allenai/paper-plain` repo has no licence detected (GitHub API).

**Other annotated resources useful for the benchmark**
- **FactPICO** (ACL 2024): 345 LLM plain-language summaries of RCT abstracts (GPT-4, Llama-2, Alpaca) with expert factuality ratings and rationales. Annotations are **CC BY 4.0**, the repo is **MIT**, and the source abstracts come from Evidence Inference 2.0 / the PubMed OA subset — [arXiv 2402.11456](https://arxiv.org/html/2402.11456); [GitHub lilywchen/FactPICO](https://github.com/lilywchen/FactPICO)
- **SPICED** (Wright et al., EMNLP 2022): 6,000 pairs of scientific findings matched across papers, news and social media, labelled for information change. Code is **MIT** — [arXiv 2210.13001](https://arxiv.org/pdf/2210.13001); [GitHub copenlu/scientific-information-change](https://github.com/copenlu/scientific-information-change)
- **LongSciVerify** (Bishop et al., LREC-COLING 2024): human fine-grained factual-consistency labels for summaries of long scientific documents, released alongside LongDocFACTScore. The repo is **MIT** — [arXiv 2309.12455](https://arxiv.org/html/2309.12455v2); [GitHub jbshp/LongDocFACTScore](https://github.com/jbshp/LongDocFACTScore)
- **Elaborative simplification** (Srikanth & Li, Findings ACL 2021): 1.3K elaborations (added explanatory content) from Newsela. ElabQUD builds on the same 1,299 elaborations. Relevant because ResearchBridge's inline explanations are legitimate additions that a naive groundedness check would flag — [ACL Anthology 2021.findings-acl.455](https://www.aclanthology.org/2021.findings-acl.455); [arXiv 2305.10387](https://ar5iv.labs.arxiv.org/html/2305.10387)

### Inferences
- PLOS and eLife publish under CC-BY by policy, so eLife/PLOS-derived text is probably commercially reusable with attribution. This matches decisions.md §1.1. The publisher policy pages were not checked in this pass.
- For the §2.2 benchmark, the cleanest seed sources are **eLife/PLOS articles plus their expert lay summaries** (CC-BY, full text, long-form, the closest match to ResearchBridge's input) and **PLABA** (CC0, sentence-aligned, has a manual factuality protocol from TREC).
- FactPICO annotations (CC BY 4.0) are the best ready-made calibration set for "is an LLM judge as good as experts?" Its source domain is RCTs only.
- Avoid shipping Cochrane- or SciNews-derived text in a product. Using them for internal evaluation is lower risk but should still be noted.
- The MIT licence on CELLS covers the repo, but the underlying abstracts and lay summaries come from journals with mixed copyright. "MIT" does not clean the text.

### Gaps
- I could not confirm the licence of the eLife/PLOS Google Drive release or of the BioLaySumm 2023 data (the HF card for BioLaySumm 2025 has no licence).
- The BioLaySumm 2023 overview ([ar5iv 2309.17332](https://ar5iv.labs.arxiv.org/html/2309.17332)) was not read in detail. I recall it may have included some human evaluation, but did not verify this.
- No 2026 BioLaySumm edition was found in this pass. It is unknown whether one ran at BioNLP 2026.
- The SciNews news text licence is unverified beyond the HF card. Science X articles are presumably copyrighted.
- The PLABA-EVAL details were seen only in a search snippet.

---

## 2. Faithfulness/factuality metrics: code, licences, correlation with humans on scientific text

### Takeaway
All the major NLI- and QA-based checkers are open source under permissive licences: AlignScore (MIT), SummaC (Apache-2.0), MiniCheck (Apache-2.0 code; MIT small models; the 7B model is **CC-BY-NC**), FActScore (MIT), QAFactEval (BSD-3), G-Eval (MIT), TruLens (MIT), RAGAS (Apache-2.0) and Vectara HHEM (Apache-2.0). On scientific and lay text, however, they correlate only **weakly at the instance level** (Kendall τ ≈ 0.15–0.29 in FactPICO). They favour extractive outputs and penalise legitimate elaboration. A strong LLM judge (GPT-4) roughly doubled the correlation (τ ≈ 0.47) in FactPICO. No single metric covers all plain-language summarisation (PLS) criteria (APPLS).

### Cited Findings
**Licences of metric code and models**
- SummaC: Apache-2.0 — [GitHub tingofurro/summac](https://github.com/tingofurro/summac)
- AlignScore: code MIT, HF checkpoint `yzha/AlignScore` MIT — [GitHub yuh-zha/AlignScore](https://github.com/yuh-zha/AlignScore); [HF](https://huggingface.co/yzha/AlignScore)
- MiniCheck (EMNLP 2024): code Apache-2.0. The RoBERTa-L, DeBERTa-v3-L and Flan-T5-L checkpoints are **MIT**. **Bespoke-MiniCheck-7B is CC BY-NC 4.0**, with commercial licensing by contacting Bespoke Labs. Throughput is ~30 min for the 29K-example LLM-AggreFact test set on one A6000 with prefix caching — [GitHub Liyan06/MiniCheck](https://github.com/Liyan06/MiniCheck); [HF Bespoke-MiniCheck-7B README](https://huggingface.co/bespokelabs/Bespoke-MiniCheck-7B)
- The LLM-AggreFact benchmark (11 datasets) is **CC-BY-ND-4.0** — [HF lytang/LLM-AggreFact](https://huggingface.co/datasets/lytang/LLM-AggreFact)
- FActScore: MIT — [GitHub shmsw25/FActScore](https://github.com/shmsw25/FActScore)
- QAFactEval: BSD-3-Clause — [GitHub salesforce/QAFactEval](https://github.com/salesforce/QAFactEval)
- G-Eval: MIT. GPT-4 G-Eval reached Spearman 0.514 with humans on summarisation, and the authors flag that LLM evaluators may favour LLM-generated text — [GitHub nlpyang/geval](https://github.com/nlpyang/geval); [arXiv 2303.16634](https://arxiv.org/abs/2303.16634)
- TruLens (groundedness feedback): MIT — [GitHub truera/trulens](https://github.com/truera/trulens)
- RAGAS (faithfulness metric): Apache-2.0. The repo has moved to `vibrantlabsai/ragas` — [GitHub](https://github.com/vibrantlabsai/ragas)
- Vectara HHEM hallucination model: apache-2.0 — [HF vectara/hallucination_evaluation_model](https://huggingface.co/vectara/hallucination_evaluation_model)
- APPLS testbed: MIT — [GitHub LinguisticAnomalies/APPLS](https://github.com/LinguisticAnomalies/APPLS)
- LENS (learned simplification metric, used in BioLaySumm): the `Yao-Dou/LENS` repo has no licence detected (GitHub API).
- SALSA (simplification success/failure annotation framework): Apache-2.0 — [GitHub davidheineman/salsa](https://github.com/davidheineman/salsa)

**How the metrics perform on scientific and lay text**
- **FactPICO**, instance-level correlation with expert factuality ratings averaged over PICO and evidence inference (Kendall τb / Spearman ρ / pairwise accuracy): QAFactEval 0.289/0.406/0.611; QuestEval 0.290/0.412/0.611; AlignScore 0.244/0.348/0.589; DAE 0.152/0.219/0.545; **GPT-4 judge 0.475/0.619/0.676**; GPT-4 with PICO extraction 0.474/0.633/0.686; Mistral 0.047, Alpaca 0.081 and Llama-2 0.055 (τ) as judges, which is near zero. Existing metrics track experts at the **system level but not the instance level** — [FactPICO, arXiv 2402.11456](https://arxiv.org/html/2402.11456)
- **APPLS** (EMNLP 2024): perturbation-based meta-evaluation of 14 metrics across informativeness, simplification, coherence and faithfulness on two PLS datasets. "No single method captures all four criteria", so the authors recommend a suite of metrics — [ACL Anthology 2024.emnlp-main.519](https://aclanthology.org/2024.emnlp-main.519); [arXiv 2305.14341](https://arxiv.org/html/2305.14341v4)
- **Devaraj et al. 2022** (ACL Outstanding Paper): SARI correlates poorly with factuality. Semantic-similarity measures capture deletions but **miss insertions and substitutions**. A RoBERTa factuality classifier (with synthetic data augmentation) found the task "challenging". The repo `AshOlogn/Evaluating-Factuality-in-Text-Simplification` has **no licence detected** — [ACL Anthology 2022.acl-long.506](https://aclanthology.org/2022.acl-long.506); [arXiv 2204.07562](https://arxiv.org/abs/2204.07562v1)
- **BioLaySumm 2024/2025**: AlignScore and SummaC reward extractiveness. In 2025 the top SummaC system (0.920) had FKGL 16.45 — [2024 overview](https://arxiv.org/html/2408.08566v1); [2025 overview](https://aclanthology.org/2025.bionlp-1.31)
- **Long documents**: LongDocFACTScore improves correlation with human factuality on long scientific summaries over standard metrics — [arXiv 2309.12455](https://arxiv.org/html/2309.12455v2). A 2025 stress test of six reference-free metrics, including AlignScore, found inconsistent scores for semantically equivalent summaries, lower reliability for information-dense claims, and "no metric stays consistent under long-context conditions" — [Mujahid, Wright & Augenstein, arXiv 2511.07689](https://arxiv.org/pdf/2511.07689v1)
- **Crowdsourced PLS study (2025)**: among automatic metrics, only QAEval significantly predicted reader comprehension (β=0.039, p=0.035) in the rigorous subset. ROUGE, BLEU, METEOR, BERTScore, LENS, SARI and GPT-PPL did not — [Guo et al., arXiv 2505.10409](https://arxiv.org/html/2505.10409v1)
- **TREC PLABA**: reference-based automatic metrics did not correlate well with expert manual judgments — [arXiv 2507.14096](https://arxiv.org/abs/2507.14096)
- **Medical LLM-as-judge more broadly** (2024–26): experts agreed with LLM judges on preference 64–68% of the time in dietetics and mental health — [arXiv 2410.20266](https://arxiv.org/html/2410.20266v1). A 2026 clinical-query study found some judge models correlated **negatively** with experts (Kendall τ −0.200), plus self-preference — [arXiv 2606.28960](https://arxiv.org/pdf/2606.28960). (Both are search-snippet level, not read in full.)

### Inferences
- A practical metric stack for §2.2: (a) a sentence- or claim-level NLI checker (AlignScore or MiniCheck-Flan-T5/DeBERTa, both MIT) as a cheap first pass; (b) a QA-based check (QAFactEval, BSD-3), which did best among non-LLM metrics in FactPICO and in reader comprehension; (c) a strong-LLM rubric judge decomposed per claim (FactPICO-style), validated against the human reference. Do not use Bespoke-MiniCheck-7B commercially without a licence. Do not redistribute LLM-AggreFact derivatives (ND).
- Because NLI checkers flag legitimate elaborations and inline explanations as "unsupported", the rubric must distinguish **added background (correct/incorrect)** from **altered findings**. FactPICO's "added information: factual / non-factual" axis does this.
- RAGAS and TruLens "groundedness" use the same claim-decomposition-then-entailment design as FActScore. They are convenient wrappers, but no validation on scientific lay text was found for them.

### Gaps
- No published correlation numbers were found for RAGAS or TruLens groundedness, or for MiniCheck, specifically on scientific or lay-summary data.
- System-level correlation coefficients in FactPICO are reported only qualitatively.
- No head-to-head of 2025–26 frontier LLM judges (e.g., Claude 4.x, GPT-5.x) on FactPICO or PLS faithfulness was found. The GPT-4 numbers are the latest instance-level figures I could verify.
- I did not verify whether BioLaySumm 2025 ran any human evaluation (the text extracted from the overview showed none).

---

## 3. Known failure modes of LLM plain-language rewriting of science (quantitative)

### Takeaway
The best-quantified failure is **overgeneralisation**: generic, present-tense or action-guiding restatements of narrow findings. It occurred in up to 73% of summaries for some models, was ~4.85× more likely than in human expert summaries, and got **worse when the prompt asked for accuracy**. Other documented failures: non-factual insertions in 31–38% of GPT-4 and Llama-2 RCT lay summaries, deletions that grow with compression, susceptibility to and propagation of spin, and correlation-to-causation inflation (a 22–33% baseline in human press releases).

### Cited Findings
- **Peters & Chin-Yee 2025, Royal Society Open Science** (DOI 10.1098/rsos.241776): 4,900 summaries from 10 LLMs (4,300 of abstracts, 600 of full articles). Overgeneralisation was coded as three transitions: quantified → generic, past → present tense, descriptive → action-guiding. Inter-rater Cohen's κ 0.79–0.95 — [PMC12042776](https://pmc.ncbi.nlm.nih.gov/articles/PMC12042776/)
  - LLM abstract summaries overall were about twice as likely as the originals to contain generalised conclusions (B=0.693, p<0.001).
  - Overgeneralisation rates (simple / systematic / accuracy prompt): LLaMA 3.3 70B 69/56/73%; ChatGPT-4o 45/55/60%; DeepSeek 26/48/67%; GPT-4 Turbo 30/30/36%; GPT-3.5 Turbo 14/17/26%; ChatGPT-4.5 21% (simple); Claude 3.5 Sonnet 11/19/4%; Claude 3.7 Sonnet 20% (simple); Claude 2 ≈0%. Claude models were not significantly different from the originals.
  - **An accuracy prompt ("do not introduce inaccuracies") increased overgeneralisation** (OR 1.90, 95% CI 1.11–3.26).
  - Temperature 0 vs 0.7 gave ~76% lower odds (B=−1.432).
  - Against expert human summaries (NEJM Journal Watch): LLM vs NEJM JW OR 4.85 (3.06–7.70); NEJM JW vs original n.s.
  - Newer models generally did worse, except Claude.
  - Data is on OSF (osf.io/q936d), licence not stated. The article is CC BY 4.0.
  - Limitations: few prompt types, mostly medical texts — [arXiv 2504.00025](https://arxiv.org/pdf/2504.00025)
- **FactPICO**: summaries with ≥1 non-factual added span were Alpaca 7.0%, **GPT-4 31.3%, Llama-2 38.3%** (53 and 57 non-factual additions respectively). The paper text and table caption disagree on whether 31.3% is per summary or per addition. Simplicity vs factuality is the central tension — [arXiv 2402.11456](https://arxiv.org/html/2402.11456)
- **Devaraj et al. 2022**: error taxonomy of **insertion, deletion and substitution**, each with graded severity. Deletions are far more common than insertions in reference simplifications. Deletion severity correlates with length reduction. T5 hallucinated more on abstractive Newsela. Errors occur **in human references too** — [ACL 2022](https://aclanthology.org/2022.acl-long.506)
- **Spin**: in tests of 22 LLMs, models were "across the board more susceptible to spin than humans". LLM-generated plain-language summaries **carried spin forward**. Models can detect spin when asked, and prompting reduces its effect — [Yun et al., CHIL 2025, PMLR 287:458–479](https://proceedings.mlr.press/v287/yun25a.html); [arXiv 2502.07963](https://arxiv.org/abs/2502.07963)
- **Causal inflation baseline (human)**: 22% of health press releases about observational studies made exaggerated causal claims from correlational findings. Universities exaggerated 1.5× more than journals, and the trend was slightly decreasing over 10 years — [Yu, Wang, Guo & Li, COLING 2020](https://aclanthology.org/2020.coling-main.427)
- **Sumner et al., BMJ 2014** (462 UK university press releases, 668 news stories): exaggerated advice ~40%, exaggerated causal claims ~33%, exaggerated animal-to-human inference ~36%. News exaggeration was 58–86% when the press release exaggerated vs 10–18% when it did not. These figures come via secondary summaries — [doi 10.1136/bmj.g7015](https://doi.org/10.1136%2Fbmj.g7015); [Science Media Centre summary](https://www.sciencemediacentre.co.nz/?p=24277)
- **Exaggeration detection model**: an MT-PET detector trained on paper-vs-press-release claim pairs (Wright & Augenstein 2021). A secondary podcast summary reports ~33% of press releases exaggerate (unverified) — [arXiv 2108.13493 via search](https://blogs.nvidia.com/blog/exaggeration-detector/)
- **Hedges and certainty**: Pei & Jurgens (EMNLP 2021) annotated 2,167 findings for sentence- and aspect-level certainty. Hedge words alone only partly explain perceived certainty — [ACL Anthology 2021.emnlp-main.784](https://preview.aclanthology.org/setup/2021.emnlp-main.784). A 2026 preprint (SciZoom) found hedging words in ML/NLP abstracts fell ~22.8% between the pre- and post-LLM periods while assertive words barely changed. This is correlational, not a direct test of LLM summaries — [arXiv 2603.16131](https://arxiv.org/pdf/2603.16131). An OSF project by Peters et al. directly tests whether LLM summaries keep limitations and uncertainty, but results are preliminary — [OSF q936d](https://osf.io/q936d)
- **Readability vs factuality conflict**: see the BioLaySumm 2025 results above (MetinOZU had SummaC 0.920 at FKGL 16.45) — [2025 overview](https://aclanthology.org/2025.bionlp-1.31)
- **Superficiality and omission**: in the Cochrane RCT, the main concern with ChatGPT-4o PLS was superficiality. Hallucinations and omissions appeared during prompt development — [PMC12302524](https://pmc.ncbi.nlm.nih.gov/articles/PMC12302524/)

### Inferences
- The §2.2 rubric should explicitly code: (1) **scope generalisation** (Peters' three transitions); (2) **certainty and hedge loss**; (3) **correlation → causation** (Yu et al. coding scheme); (4) **non-factual added information**, separated from correct added background; (5) **omitted limitations or key findings** (deletion severity); (6) **spin carried forward**; (7) **substitution** (changed numbers, populations or comparators, following PICO).
- Do not rely on "be accurate" instructions. Peters & Chin-Yee show they can backfire. Use low temperature and measured checks instead.
- Model choice matters a lot (Claude ≈0–20% vs LLaMA 3.3 ~69% overgeneralisation), so the benchmark should compare candidate models, not just prompts.

### Gaps
- No peer-reviewed quantitative study was found that measures **hedge or limitation dropping** specifically in LLM lay summaries. Preliminary work only.
- No quantitative study was found of causal-language inflation **by LLMs** (as opposed to press releases), though the Yu et al. classifier could be applied to measure it.
- The Sumner et al. percentages were not checked against the BMJ full text.
- The Peters & Chin-Yee models predate 2026 frontier models. No replication on current models was found.

---

## 4. Human evaluation protocols for lay summaries: rubrics, raters, agreement

### Takeaway
Protocols converge on a few axes: factuality/faithfulness (often PICO-structured), completeness/informativeness, simplicity/readability, coherence, background, and brevity, rated on 3–5-point Likert scales by domain experts. Lay readers are used for comprehension and readability. Reported agreement is **moderate**: κ/α ≈ 0.2–0.65 for nuanced error judgments with crowd or student raters, and ≈ 0.8–0.95 only for crisp coding schemes (e.g., Peters' overgeneralisation coding). This is a credible target range for a small benchmark.

### Cited Findings
- **FactPICO rubric**: 2 senior (5th-year) medical students. P, I, C and O are each rated 4 = accurate, 3 = somewhat inaccurate/vague, 2 = severe inaccuracy or missing critical descriptor, 1 = missing. Evidence inference is rated 4 = accurate … 1 = not mentioned. Added information is span-highlighted and labelled factual or non-factual with a rationale. **Randolph's κ**: Population 0.56, Intervention 0.80, Comparator 0.73, Outcome 0.60, Evidence inference 0.47, Added info 0.65, Added-info correctness 0.86 — [arXiv 2402.11456](https://arxiv.org/html/2402.11456)
- **Devaraj et al. 2022**: MTurk workers passed a qualification of 10 sentence pairs, then each example got 3 annotators, paid $10/hour. **Krippendorff's α (ordinal)**: insertion 0.425 (moderate), deletion 0.639 (substantial), substitution 0.200 (fair, partly due to a skewed majority-0 label) — [ACL 2022 PDF](https://aclanthology.org/2022.acl-long.506)
- **Peters & Chin-Yee**: overgeneralisation coding (generic, tense, action-guiding) reached Cohen's κ 0.79–0.95 — [PMC12042776](https://pmc.ncbi.nlm.nih.gov/articles/PMC12042776/)
- **TREC PLABA**: biomedical-expert or contractor judgments on 4 axes (factual accuracy, completeness, simplicity, brevity), 3-point symmetric Likert scale rescaled to 0–100 — [arXiv 2507.14096](https://arxiv.org/abs/2507.14096)
- **Guo et al. 2025 crowdsourced PLS study**: 150 US MTurk lay participants (medical training excluded), 50 CELLS pairs × 7 versions, $1 per pair. 1,346 annotations; only 459 (34.1%) survived attention-check and time filtering. Ratings covered informativeness, simplicity, coherence, faithfulness and background, plus 3 MCQs per summary (Llama-3-70B-generated, manually reviewed) and free recall. Faithfulness ratings were the strongest predictor of MCQ accuracy (β=0.048) — [arXiv 2505.10409](https://arxiv.org/html/2505.10409v1)
- **Goldsack et al. 2022**: 2 domain experts, 10 articles per dataset, reading the generated summary next to the abstract and the reference — [arXiv 2210.09932](https://arxiv.org/pdf/2210.09932)
- **Cochrane ChatGPT-4o RCT**: 2 Cochrane editors and 11 lay assessors. Each summary was rated 4 times (2 expert, 2 lay) on 1–10 Likert scales for information, readability and detail, plus "submittable?", authorship guess and a 0–10 Cochrane PLS checklist (experts only). **Factual accuracy was not systematically measured, and inter-rater agreement was not reported** — [PMC12302524](https://pmc.ncbi.nlm.nih.gov/articles/PMC12302524/)
- **Annotation frameworks for simplification edits**: SALSA (Apache-2.0) offers an edit-level success/failure taxonomy — [GitHub davidheineman/salsa](https://github.com/davidheineman/salsa)

### Inferences
- For §2.2, a defensible design: 30–50 passages from CC-BY eLife/PLOS articles; 2–3 expert raters (domain PhD or senior students); a FactPICO-style per-element 4-point scale, generalised beyond RCTs to claims, scope, certainty, causality and limitations; added information span-labelled factual or non-factual; and agreement reported with Krippendorff's α (ordinal) per axis. Expect α ≈ 0.4–0.8, and plan an adjudication round.
- Crisp, operationalised codes (Peters-style binary transitions) give much higher agreement (κ ≥ 0.79) than holistic "faithfulness" Likert scales. Decompose the rubric into binary or ordinal checks.
- Lay raters are good for comprehension and readability, not for faithfulness. Guo et al. had to discard 66% of crowd annotations for quality.

### Gaps
- Typical agreement values for **holistic** faithfulness Likert ratings of long-form lay summaries were not found (most studies report per-element κ).
- No published protocol was found that specifically rates "nuance and limitation preservation" with reported agreement.

---

## 5. LLM-generated vs human (expert/community) explanations and lay summaries

### Takeaway
On **perceived** quality, LLM lay summaries now match or beat human-written ones (Cochrane RCT; Guo et al. ratings; TREC PLABA on accuracy and completeness; community-notes helpfulness). On **comprehension** and **generalisation accuracy**, human-written versions still win in the best-controlled studies: human PLS gave significantly higher MCQ accuracy, and LLMs overgeneralised 4.85× more than expert summaries. LLMs also beat crowd workers at labelling tasks. This favours LLM-drafted explanations with measured faithfulness checks over relying on community quality alone.

### Cited Findings
- **Guo, Sohn, Leroy & Cohen 2025** (150 lay MTurk participants, GPT-4 vs human PLS on CELLS): no LLM variant was rated significantly better than human. LLM PLS were more readable (lower FKGL, SMOG and ARI). **Human-written PLS produced significantly higher MCQ comprehension**, while recall did not differ. No data or code release was stated — [arXiv 2505.10409](https://arxiv.org/html/2505.10409v1)
- **Ágústsdóttir, Rosenberg & Baker 2025** (blinded, randomised non-inferiority trial, 18 Cochrane reviews): ChatGPT-4o vs human PLS medians were information 9 vs 8, readability 10 vs 8, detail 9 vs 8; "submittable" 64% vs 36%; checklist "describes limitations" 64% vs 36%. Both were still too hard to read (Lix ~47–50). Accuracy was not measured — [PMC12302524](https://pmc.ncbi.nlm.nih.gov/articles/PMC12302524/)
- A randomised non-inferiority trial protocol (ISRCTN85699985) compares AI-assisted vs human Cochrane PLS with the general public. Only the protocol was found — [ISRCTN](https://www.isrctn.com/pdf/ISRCTN85699985)
- **Sleep medicine** (Frontiers in AI 2024, 19 medical students): no significant readability or comprehension differences between LLM and human summaries. Small sample — [frontiersin.org 10.3389/frai.2024.1477535](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2024.1477535/epub)
- **Lightweight LLMs** (<8B, zero-shot) produced summaries with comparable desirable information to human references, and evaluators sometimes preferred or misattributed them (Nursal & Mitchell, ACL 2026 Findings; snippet only) — [ACL Anthology author page](https://aclanthology.org/people/batuhan-nursal/unverified/)
- **TREC PLABA**: top LLM systems matched human references on factual accuracy and completeness, but not on simplicity or brevity — [arXiv 2507.14096](https://arxiv.org/abs/2507.14096)
- **Peters & Chin-Yee**: LLM summaries vs expert NEJM Journal Watch summaries had OR 4.85 for overgeneralisation. The expert summaries did not differ from the originals — [PMC12042776](https://pmc.ncbi.nlm.nih.gov/articles/PMC12042776/)
- **Community annotation analogue (X Community Notes)**: a field deployment (Nov 2025–Jan 2026) compared 1,614 LLM notes with 1,332 human notes on the same posts, using 108,169 ratings from 42,521 raters. LLM notes got significantly higher helpfulness scores among raters who saw both. The authors caution about platform dynamics such as timing and exposure — [arXiv 2604.02592](https://arxiv.org/abs/2604.02592). AI writers produced 7.4% of all notes (31,464 notes from 24 active AI accounts, Sep 2025–Mar 2026) — [R Street](https://www.rstreet.org/research/ai-writers-on-community-notes-an-evaluation-of-seven-months-of-data/). A hybrid "Supernotes" approach (De et al. 2025) was rated more helpful than the best human notes (secondary citation) — [arXiv 2510.09585](https://arxiv.org/pdf/2510.09585)
- **LLM vs crowd annotators**: ChatGPT zero-shot accuracy beat MTurk crowd workers by ~25 points on average across 4 datasets (6,183 items), with higher intercoder agreement than crowd workers and trained annotators, at a fraction of the cost — [Gilardi, Alizadeh & Kubli, PNAS 2023](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10372638/)
- **Paper Plain**: AI-generated aids improved ease of reading **without comprehension loss** when they supplemented, rather than replaced, the original text — [arXiv 2203.00130](https://arxiv.org/pdf/2203.00130)

### Inferences
- For §2.1, the evidence suggests LLM explanations clear the "perceived quality" bar on day one, with residual risk concentrated in faithfulness and generalisation. That risk is measurable, which is exactly what §2.2 is designed to do. Community annotation has no published evidence of beating LLMs on scientific explanation quality. The closest analogue (Community Notes) currently favours LLM or hybrid notes on helpfulness.
- The §2.2 benchmark should include a **human (expert or community-style) explanation arm** alongside the LLM arm on the same passages. That is the only way to settle §2.1 with data rather than preference. Comprehension MCQs on a lay sample (Guo et al. design) are the key outcome, because ratings and comprehension disagree.
- The Paper Plain "supplement, don't replace" finding supports ResearchBridge's display-original-plus-rewrite design, and suggests showing a source link for each claim.

### Gaps
- No study was found that directly compares **community-written** (Genius-style) explanations of scientific passages with LLM explanations.
- The Community Notes evidence is about fact-checking social-media posts, not science explanation, and comes largely from one deployment.
- Neither the Cochrane RCT nor the Guo et al. study measured factual errors in its outputs.

---

## 6. Readability metrics on scientific text and jargon/prior-knowledge measures

### Takeaway
Classic formulas (FKGL, Dale-Chall, Coleman-Liau) are standard in BioLaySumm but correlate poorly with reader-perceived difficulty in health text. Adding a **jargon-span count** measurably improves them (MedReadMe). Jargon familiarity is highly **reader-dependent**, even within a subfield, so personalised jargon detection (Guo, August et al.) and frequency-based tools (De-Jargonizer) are the main reusable building blocks for ResearchBridge's "prior-knowledge burden" score.

### Cited Findings
- **Formula limits**: in health texts, FKGL-type formulas are "inadequate" because they rely on word and sentence length and ignore cohesion — [Kandula & Zeng-Treitler, AMIA 2008, PMC2655974](https://pmc.ncbi.nlm.nih.gov/articles/PMC2655974). Widely used formulas correlate highly with each other but **not adequately with lay readers' perceived difficulty** of Wikipedia diabetes articles and EHR notes — [Zheng & Yu, JMIR 2017](https://jmir.org/2017/3/e59/PDF)
- In the Guo et al. 2025 study, LLM PLS scored better on FKGL, SMOG and ARI than human PLS, yet produced **lower comprehension**. Lower formula scores did not mean better understanding — [arXiv 2505.10409](https://arxiv.org/html/2505.10409v1)
- **MedReadMe** (Jiang & Xu, EMNLP 2024): 4,520 sentences from 15 sources (encyclopedias, PLS, research papers) with CEFR-based readability ratings and fine-grained **jargon span annotations** (7-class taxonomy of difficulty reasons) by lay annotators. Adding a single "number of jargon spans" feature to readability formulas noticeably improves correlation with human judgments. Data is on GitHub, but the **repo has no licence detected** — [arXiv 2405.02144](https://arxiv.org/abs/2405.02144); [GitHub chaojiang06/medreadme](https://github.com/chaojiang06/medreadme)
- **De-Jargonizer** (Rakedzon, Baram-Tsabari et al., PLOS ONE 2017): classifies words as common, mid-frequency or jargon by frequency in a 90M-word BBC corpus (2012–2015). Across 5,000 PLOS abstract/lay-summary pairs, jargon averaged **14% in abstracts vs 10% in lay summaries**, still above the level recommended for public understanding. It is a free web tool (scienceandpublic.com) in English and Hebrew; one press report says it over-flags proper nouns. No open-source licence was found — [PMC5549884](https://pmc.ncbi.nlm.nih.gov/articles/PMC5549884); [Technion](https://www.technion.ac.il/en/2017/08/speaking-science-without-jargon/)
- **Personalised jargon identification** (Guo, Chang, Antoniak, Bransom, Cohen, Wang & August, NAACL 2024): more than 10K term-familiarity annotations from 11 CS researchers over 100 abstracts. Familiarity varied a lot, even within a subfield. Prompts including the reader's own publications and self-described subfield gave the best accuracy — [arXiv 2311.09481](https://arxiv.org/pdf/2311.09481). The repo `talaugust/PersonalizedJargon` is **Apache-2.0** (GitHub API)
- **"Explain Less, Understand More"** (2025): data-efficient personalisation of reader-dependent jargon on the same 11k annotations (60/20/20 split) — [arXiv 2505.16227](https://arxiv.org/pdf/2505.16227)
- **Definitions**: August et al. on generating scientific definitions with controllable complexity (repo `talaugust/definition-complexity`, **Apache-2.0**, GitHub API). A GPT-4 de-jargonising pilot for journalists found definitions generated from **abstract-only context were slightly more accurate** than those using RAG over the full text — [Nishal, Lee & Diakopoulos, arXiv 2410.12069](https://arxiv.org/pdf/2410.12069)
- **LENS**, a learned simplification metric, is used in BioLaySumm readability scoring — [BioLaySumm 2025 overview](https://aclanthology.org/2025.bionlp-1.31). It did not predict comprehension in Guo et al. 2025 — [arXiv 2505.10409](https://arxiv.org/html/2505.10409v1)
- **Background and familiarity**: in Guo et al. 2025, "somewhat familiar" readers comprehended best, and self-identified experts had the lowest MCQ accuracy (21% got more than 2 of 3 right). "Background information" ratings predicted comprehension (β=0.045) — [arXiv 2505.10409](https://arxiv.org/html/2505.10409v1)

### Inferences
- A defensible v0 "prior-knowledge burden" score: a jargon-span density from De-Jargonizer-style word frequency (reimplementable from any open news corpus), refined with a MedReadMe-style span detector, plus a reader-profile adjustment (PersonalizedJargon, Apache-2.0). Report FKGL and Dale-Chall only as secondary, since they are standard but weak.
- Validate any readability/convolution score against comprehension MCQs, not against formula scores. That is the gap Guo et al. 2025 exposed.

### Gaps
- No resource named "SciJargon" was found. It may not exist under that name.
- No open-source licence was found for the De-Jargonizer code or word lists.
- The MedReadMe data licence is unspecified, so ask the authors before commercial use.
- No validated "assumed-knowledge" metric for scientific papers was found beyond jargon familiarity and the background-information ratings above.
