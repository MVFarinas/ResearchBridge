# web/ — the ResearchBridge reader (Phases 4-5)

Next.js 16 (App Router, TypeScript strict). Server-rendered pages, so papers are indexable and
readable without JavaScript. The browser never talks to the backend directly: pages, server
actions and the credibility slot call the API server-side at `RB_API_URL`.

| Route | What |
|---|---|
| `/` | Home: search box and what the availability tags mean. |
| `/search?q=…` | Corpus results and the wider OpenAlex record, filters (years, availability, type), sort by date. |
| `/papers/<key>` | The paper: original + explanations (Recogito annotation layer), plain-English view (empty state until generation exists), summary and credibility panels, licence and attribution. `?view=plain` or `?view=original`. |
| `/lookup` | Look up by DOI, PMID, PMC ID, arXiv ID or title (server action). |
| `/lookup/requests/<id>` | "Being prepared": refreshes itself until the paper is ready. |
| `/methodology` | States that the faithfulness benchmark is pending. |
| `/dev/annotations-demo` | **Development only**, SYNTHETIC data; a 404 in production builds. |

```sh
npm ci
NEXT_TELEMETRY_DISABLED=1 RB_API_URL=http://127.0.0.1:8000 npm run dev   # http://localhost:3000
npm run lint && npm run typecheck && npm test                             # what CI runs (plus build)
NEXT_TELEMETRY_DISABLED=1 npm run build && RB_API_URL=… npm start -- -p 3045
PLAYWRIGHT_BROWSERS_PATH=0 npx playwright install --only-shell chromium   # once, into node_modules
PLAYWRIGHT_BROWSERS_PATH=0 npm run test:e2e                               # needs the full stack running
```

Use `localhost`, not `127.0.0.1`, for `next dev`: Next 16 blocks dev resources requested from other
origins, which stops hydration. Conventions: TSDoc on every export (ESLint with
eslint-plugin-jsdoc), Vitest for logic and components, synthetic test data named synthetic
(`src/test/fixtures.ts`). See [docs/phase-notes/phase-4-5.md](../docs/phase-notes/phase-4-5.md).
