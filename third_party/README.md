# third_party/ — licences of vendored and adapted code

Every piece of copied or adapted third-party source keeps its licence here, in
`third_party/<name>/LICENSE` (and `NOTICE` for Apache-2.0), alongside a header in each copied
file naming the upstream URL, commit, licence and "modified by ResearchBridge" if changed. Each
entry also has a row in [docs/licence-inventory.md](../docs/licence-inventory.md) marked
`vendored` or `adapted`. Rules: [docs/conventions.md](../docs/conventions.md#reusing-other-peoples-code).

Nothing has been vendored or adapted yet. Published packages installed through the lock files are
recorded in the inventory and need no entry here, with one exception: BSD-3-Clause packages that
are **bundled into the JavaScript served to browsers** (a redistribution in binary form) keep their
licence text here, so the notice can be reproduced in the site's documentation:

| Directory | Package | Licence text taken from |
|---|---|---|
| `recogito-text-annotator/` | `@recogito/text-annotator` 4.3.7 (web) | `LICENSE` at commit `0d375b0` (the npm `gitHead` of 4.3.7), recogito/text-annotator-js |
| `annotorious-core/` | `@annotorious/core` 3.9.4 (dependency of the above) | `LICENSE` on `main` of annotorious/annotorious, read 2026-10-13 (no tag for 3.9.4; npm declares BSD-3-Clause) |
