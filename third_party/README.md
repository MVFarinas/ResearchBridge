# third_party/ — licences of vendored and adapted code

Every piece of copied or adapted third-party source keeps its licence here, in
`third_party/<name>/LICENSE` (and `NOTICE` for Apache-2.0), alongside a header in each copied
file naming the upstream URL, commit, licence and "modified by ResearchBridge" if changed. Each
entry also has a row in [docs/licence-inventory.md](../docs/licence-inventory.md) marked
`vendored` or `adapted`. Rules: [docs/conventions.md](../docs/conventions.md#reusing-other-peoples-code).

Nothing has been vendored or adapted yet (Phase 0; Track R's first half reused code only as
published packages, and reimplemented the Schwartz-Hearst algorithm and the De-Jargonizer method
from their papers). Published packages installed through the lock
files are recorded in the inventory but need no entry here.
