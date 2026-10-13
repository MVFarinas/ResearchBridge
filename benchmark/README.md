# benchmark/: the faithfulness benchmark (`rbbench`)

**Owner: Phase 1.** The decisions.md §1.4 benchmark: about 12 biomedical passages, rewritten
paragraph by paragraph, decomposed into claims, scored claim by claim by human raters and an LLM
judge, to choose the generation model and the faithfulness gate. Phase notes:
[docs/phase-notes/phase-1.md](../docs/phase-notes/phase-1.md).

**State (2026-10-13):** the scaffold is complete and tested. Nothing has been sent to an LLM (no
API key), no rater has seen anything, and the 12 papers are **proposed, not chosen**. Everything
the user must decide or provide is listed in the phase notes.

## Layout

| Path | What |
|---|---|
| `selection/` | `slots_v1.yaml` (how candidates are chosen), `candidates.csv` (24 PROPOSED candidates, two per slot), `screening_log.csv`, README with the method |
| `prompts/` | Versioned prompts: `rewrite_v1.md`, `decompose_v1.md`, `judge_v1.md`. Never edited after use; a change is a new version |
| `rubric/` | `rubric_v1.yaml` (machine-readable), `rubric_v1.md`, `rater_guide_v1.md`, all DRAFT |
| `config/` | `rewrite_matrix_v1.yaml`: temperature 0 vs default |
| `comprehension/` | Lay comprehension study scaffold: JSON Schema, empty template, README |
| `src/rbbench/` | The package (one module per step) |
| `tests/` | pytest; `tests/js/` holds a Node runner for the packet form |

Downloads and generated files go to `<RB_DATA_DIR>/benchmark/` (default `data/benchmark/`,
gitignored): the HTTP cache, ingest outputs, rewrites, claims, packets, ratings, judgements, the
FactPICO data and the dry run.

## Commands

All steps run offline with the fake LLM client (`--client fake`, the default), whose output is
labelled synthetic. Real calls need `--client anthropic --live`, `ANTHROPIC_API_KEY`, and model
IDs in `RB_LLM_GENERATION_MODEL` / `RB_LLM_JUDGE_MODEL` (the judge must differ).

```sh
rbbench dry-run                        # everything, on the committed fixtures, all SYNTHETIC
rbbench select                         # rebuild selection/candidates.csv (network, cached, polite)
rbbench ingest                         # candidates -> data/benchmark/ingest (units, passages)
rbbench ingest --only S01A,S02B        # only some candidates (slot + option, PMCID or paper key)
rbbench ingest --fixtures              # the committed fixtures instead
rbbench rewrite                        # every passage x every matrix arm -> rewrites.jsonl
rbbench decompose --method llm         # or --method sentences (deterministic fallback)
rbbench packets --raters r1,r2 --packet-id round1   # HTML + JSON per rater, key.json
rbbench import-ratings --key data/benchmark/packets/key.json r1.ratings.json r2.ratings.json
rbbench agreement data/benchmark/ratings.jsonl
rbbench adjudicate data/benchmark/ratings.jsonl     # writes disagreements.csv to fill in
rbbench adjudicate data/benchmark/ratings.jsonl --adjudications data/benchmark/disagreements.csv
rbbench judge --finals data/benchmark/final_labels.jsonl
rbbench factpico download              # FactPICO (CC BY 4.0) into data/; never committed
rbbench factpico check                 # reproduce FactPICO's published Kendall tau-b
rbbench factpico calibrate --limit 20  # judge vs FactPICO experts
rbbench baselines                      # which optional metrics are installed
rbbench comprehension validate FILE    # validate a question set
```

A real run, once the key exists and the papers are approved:

```sh
set -a; source .env; set +a            # ANTHROPIC_API_KEY, RB_LLM_GENERATION_MODEL, RB_LLM_JUDGE_MODEL
rbbench ingest --only <the 12 approved>
rbbench rewrite --client anthropic --live
rbbench decompose --client anthropic --live
rbbench packets --raters <ids> --packet-id round1
# raters return their exports; then import-ratings, agreement, adjudicate
rbbench judge --client anthropic --live --finals data/benchmark/final_labels.jsonl
```

## Automatic baselines (optional, not installed)

The adapters in `rbbench.baselines` wrap AlignScore, MiniCheck and QAFactEval behind one
`score(pairs)` interface. None is a dependency and nothing downloads a model; each raises a clear
error until enabled. They need PyTorch and, for QAFactEval, AllenNLP, so install them in a
**separate virtualenv** (they pin old library versions that would break the locked environment):

- **AlignScore** (code MIT, weights MIT): `pip install git+https://github.com/yuh-zha/AlignScore`
  (pin a commit; `a0936d5` checked 2026-10-13), `python -m spacy download en_core_web_sm`, then
  download `AlignScore-large.ckpt` from huggingface.co/yzha/AlignScore into `data/models/` and pass
  its path as `ckpt_path`.
- **MiniCheck** (code Apache-2.0): `pip install "minicheck @ git+https://github.com/Liyan06/MiniCheck.git@b58b9fa"`.
  Only the MIT checkpoints (`roberta-large`, `deberta-v3-large`, `flan-t5-large`) are accepted;
  **Bespoke-MiniCheck-7B is CC BY-NC and refused** by the adapter.
- **QAFactEval** (code BSD-3-Clause): `pip install qafacteval`, then its `download_models.sh`;
  **check the licences of those models before use** (not verified).

Record the exact versions in docs/licence-inventory.md when enabling one.

## Rules this package follows

decisions.md §1.1 (licence gate at paper and paragraph level, through `rbcore.licences`), §1.4
(claim-level codes, separate judge model), docs/conventions.md (no fabricated results: every fake
or synthetic output says so; downloads in `data/`; polite, cached HTTP; XML parsed safely).
