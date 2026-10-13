"""ResearchBridge shared core library.

Subpackages:
    rbcore.jats: safe JATS XML parsing into typed dataclasses.
    rbcore.licences: licence normalisation and the decisions.md §1.1 permission gate.
    rbcore.config: settings read from the environment (model IDs, optional keys).
    rbcore.llm: a small LLM client interface with a deterministic fake.
    rbcore.http: a polite, rate-limited, cached HTTP fetcher.
"""

__version__ = "0.1.0"
