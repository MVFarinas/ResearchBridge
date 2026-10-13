# benchmark/ — faithfulness benchmark (Phase 1)

**Owner: Phase 1.** Placeholder created in Phase 0; the package itself does not exist yet.

Purpose: the decisions.md §1.4 benchmark: 12 biomedical rewrites, decomposed into claims and
scored claim by claim by human raters and an LLM judge, to choose the generation model and the
faithfulness gate. See [Plan.md](../Plan.md) "Phase 1".

To start: add `benchmark/pyproject.toml` (with `[tool.pytest.ini_options]` and `[tool.mypy]`),
code under `benchmark/src/`, tests under `benchmark/tests/`, then `make lock`. Use
`rbcore.jats` to parse the 12 papers, `rbcore.licences.decide` to check each passes §1.1 at its
primary source, and `rbcore.llm` for every model call.
