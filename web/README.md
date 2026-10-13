# web/ — Next.js reader (Phases 4-5)

**Owner: Phases 4 and 5.** Placeholder created in Phase 0; the app does not exist yet.

Purpose: the server-rendered reader (plain-English view, original + annotations, summary and
credibility panels) and, in Phase 5, search and lookup. See [Plan.md](../Plan.md).

When the app is created, `web/package.json` must define `lint`, `typecheck` and `test` (Vitest)
scripts and a lock file (`package-lock.json`); CI's web job and the Makefile targets switch on
automatically once `web/package.json` exists. TypeScript in strict mode, TSDoc on exports
([docs/conventions.md](../docs/conventions.md)).
