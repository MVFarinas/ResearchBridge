"""ResearchBridge Django backend (Plan.md Phase 2).

Apps:
    rb_backend.corpus: papers, versions, sections, paragraphs, figures, licence
        records, the licence review queue and the gated access layer.
    rb_backend.annotations: W3C Web Annotation-shaped annotations with
        provenance, plus revision, vote and report tables.
    rb_backend.ingestion: PMC Cloud Service ingestion, background tasks and the
        ``ingest_pmc`` and ``recheck_licences`` management commands.
"""
