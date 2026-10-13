"""Papers, versions and their content: sections, paragraphs and figures.

A :class:`Paper` is the work (identified by DOI, PMCID, PMID or arXiv ID); a
:class:`PaperVersion` is one version of it from one source, such as
``PMC10718527.1``. Content and licence decisions belong to a version, because
a new version may renumber paragraphs (rbcore's IDs are positional) or carry a
different licence. Exactly one version per paper is current.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from rb_backend.corpus.models.gated import GatedPermissions, gate_constraints
from rb_backend.corpus.querysets import (
    FigureQuerySet,
    PaperQuerySet,
    PaperVersionQuerySet,
    ParagraphQuerySet,
    SectionQuerySet,
)


class Source(models.TextChoices):
    """Where a paper version was ingested from."""

    PMC = "pmc", "PMC Cloud Service (pmc-oa-opendata)"


class ContentState(models.TextChoices):
    """Whether a version's full text has been fetched and parsed."""

    NONE = "none", "Not fetched yet"
    PARSED = "parsed", "Parsed"
    FAILED = "failed", "Fetch or parse failed"
    SKIPPED = "skipped", "Not fetched: the licence refuses it"
    REMOVED = "removed", "Removed: the licence gate rejected it"


class Paper(models.Model):
    """A scholarly work, independent of version and source.

    Attributes:
        doi: DOI, lower-cased, without a resolver prefix.
        pmcid: PMC accession ID with its ``PMC`` prefix.
        pmid: PubMed ID.
        arxiv_id: arXiv identifier (not ingested yet).
        is_retracted: Whether any source reports the paper as retracted.
        retraction_source: Which source said so, e.g. ``pmc:is_retracted``.
        retraction_date: Date of the retraction notice, when a source gives
            one (PMC does not).
        retraction_recorded_at: When ResearchBridge first recorded it.
        created_at: Row creation time.
        updated_at: Last update time.
    """

    doi = models.CharField(max_length=255, null=True, blank=True, unique=True)
    pmcid = models.CharField(max_length=32, null=True, blank=True, unique=True)
    pmid = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    arxiv_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    is_retracted = models.BooleanField(default=False)
    retraction_source = models.CharField(max_length=64, blank=True)
    retraction_date = models.DateField(null=True, blank=True)
    retraction_recorded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PaperQuerySet.as_manager()

    class Meta:
        """Every paper needs an identifier; a retraction needs a source."""

        constraints = [
            models.CheckConstraint(
                condition=Q(doi__isnull=False)
                | Q(pmcid__isnull=False)
                | Q(pmid__isnull=False)
                | Q(arxiv_id__isnull=False),
                name="paper_has_identifier",
            ),
            models.CheckConstraint(
                condition=Q(is_retracted=False) | ~Q(retraction_source=""),
                name="paper_retraction_has_source",
            ),
        ]

    def __str__(self) -> str:
        """Return the most specific identifier."""
        return self.pmcid or self.doi or self.pmid or self.arxiv_id or f"paper {self.pk}"

    @property
    def current_version(self) -> PaperVersion | None:
        """The current version, or None if none is current (unrestricted read)."""
        return self.versions.filter(is_current=True).first()


class PaperVersion(GatedPermissions):
    """One version of a paper from one source, with its licence decision.

    The licence decision (inherited fields) is recomputed by
    :func:`rb_backend.corpus.gate.evaluate_version` whenever its licence
    records change.

    Attributes:
        paper: The work.
        source: Ingestion source.
        source_version_id: The source's version ID, e.g. ``PMC10718527.1``.
        version_number: The version number within the source.
        is_current: Whether this is the version served for the paper.
        title: Article title.
        journal_title: Journal title.
        journal_nlm_ta: NLM title abbreviation.
        journal_issns: ISSNs.
        publisher: Publisher name.
        article_type: JATS ``@article-type``.
        subject_heading: JATS heading subject.
        language: ``xml:lang``.
        published_date: ISO 8601 at the precision available (YYYY[-MM[-DD]]).
        authors: Authors as dictionaries (name parts, ORCID, corresponding).
        citation: The source's citation string.
        coi_statements: Conflict-of-interest statements (raw text).
        funding: Funding statements and awards (raw text).
        is_pmc_openaccess: PMC JSON flag.
        is_manuscript: PMC JSON flag (author manuscript).
        is_historical_ocr: PMC JSON flag (scanned back issue).
        is_retracted: Retraction flag for this version, as the source says.
        metadata_url: URL of the metadata document (PMC JSON).
        metadata_sha256: SHA-256 of the last metadata document fetched.
        source_metadata: The raw metadata document, kept for audit.
        content_url: URL of the full text (JATS XML), with its ``md5``.
        content_md5: MD5 the source publishes for the full text.
        content_sha256: SHA-256 of the full text we parsed.
        content_state: Whether the full text was fetched and parsed.
        content_error: Why fetching or parsing failed, if it did.
        parser_version: rbcore version that parsed the content.
        metadata_retrieved_at: When the metadata was last fetched.
        content_retrieved_at: When the full text was last fetched.
        last_checked_at: When the source was last checked for changes.
        source_withdrawn_at: When the source was first found no longer to
            list this version (withdrawn or removed); None while it is listed.
            A withdrawn version goes to licence review.
        created_at: Row creation time.
        updated_at: Last update time.
    """

    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="versions")
    source = models.CharField(max_length=16, choices=Source.choices)
    source_version_id = models.CharField(max_length=64)
    version_number = models.PositiveIntegerField()
    is_current = models.BooleanField(default=False)

    title = models.TextField(blank=True)
    journal_title = models.CharField(max_length=512, blank=True)
    journal_nlm_ta = models.CharField(max_length=255, blank=True)
    journal_issns = models.JSONField(default=list, blank=True)
    publisher = models.CharField(max_length=512, blank=True)
    article_type = models.CharField(max_length=64, blank=True)
    subject_heading = models.CharField(max_length=512, blank=True)
    language = models.CharField(max_length=16, blank=True)
    published_date = models.CharField(max_length=10, blank=True)
    authors = models.JSONField(default=list, blank=True)
    citation = models.TextField(blank=True)
    coi_statements = models.JSONField(default=list, blank=True)
    funding = models.JSONField(default=dict, blank=True)

    is_pmc_openaccess = models.BooleanField(null=True, blank=True)
    is_manuscript = models.BooleanField(null=True, blank=True)
    is_historical_ocr = models.BooleanField(null=True, blank=True)
    is_retracted = models.BooleanField(default=False)

    metadata_url = models.URLField(max_length=1000)
    metadata_sha256 = models.CharField(max_length=64, blank=True)
    source_metadata = models.JSONField(default=dict, blank=True)
    content_url = models.URLField(max_length=1000, blank=True)
    content_md5 = models.CharField(max_length=32, blank=True)
    content_sha256 = models.CharField(max_length=64, blank=True)
    content_state = models.CharField(
        max_length=16, choices=ContentState.choices, default=ContentState.NONE
    )
    content_error = models.TextField(blank=True)
    parser_version = models.CharField(max_length=32, blank=True)

    metadata_retrieved_at = models.DateTimeField(null=True, blank=True)
    content_retrieved_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    source_withdrawn_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PaperVersionQuerySet.as_manager()

    class Meta:
        """One row per source version; at most one current version per paper."""

        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_version_id"], name="paperversion_unique_source_id"
            ),
            models.UniqueConstraint(
                fields=["paper"],
                condition=Q(is_current=True),
                name="paperversion_one_current_per_paper",
            ),
            *gate_constraints("paperversion"),
        ]

    def __str__(self) -> str:
        """Return the source version ID."""
        return self.source_version_id


class Section(models.Model):
    """A section (or root container: body, an abstract, back matter).

    Attributes:
        version: The paper version.
        stable_id: rbcore's positional ID, e.g. ``sec2.1`` or ``abs1``.
        parent: The enclosing section, or None for a root.
        kind: "body", "abstract", "back", "sec", "ack", "app" or "notes".
        title: Section title.
        label: Section label such as "2.1".
        sec_type: JATS ``@sec-type`` (or ``@abstract-type``).
        xml_id: The publisher's ``@id``.
        position: Document order within the version.
    """

    version = models.ForeignKey(PaperVersion, on_delete=models.CASCADE, related_name="sections")
    stable_id = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    kind = models.CharField(max_length=16)
    title = models.TextField(blank=True)
    label = models.CharField(max_length=64, blank=True)
    sec_type = models.CharField(max_length=128, blank=True)
    xml_id = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField()

    objects = SectionQuerySet.as_manager()

    class Meta:
        """Stable IDs are unique within a version."""

        ordering = ["version", "position"]
        constraints = [
            models.UniqueConstraint(fields=["version", "stable_id"], name="section_unique_id"),
        ]

    def __str__(self) -> str:
        """Return ``<version>/<stable id>``."""
        return f"{self.version_id}/{self.stable_id}"


class Paragraph(GatedPermissions):
    """A paragraph-level block: the alignment unit for rewrites and annotations.

    Attributes:
        version: The paper version.
        section: The section the paragraph belongs to.
        stable_id: rbcore's positional ID, e.g. ``sec2.1-p3``.
        kind: "p", "list-item", "quote", "boxed", "def" or "formula".
        text: Plain text with inline markup flattened.
        text_sha256: SHA-256 of ``text``, so annotations can detect drift.
        source_xml: The block's original JATS XML (untrusted; for rendering).
        position: Document order within the version.
        has_own_permissions: Whether a ``<permissions>`` block applies to the
            paragraph itself (otherwise it inherits the article licence).
    """

    version = models.ForeignKey(PaperVersion, on_delete=models.CASCADE, related_name="paragraphs")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="paragraphs")
    stable_id = models.CharField(max_length=160)
    kind = models.CharField(max_length=16)
    text = models.TextField()
    text_sha256 = models.CharField(max_length=64)
    source_xml = models.TextField(blank=True)
    position = models.PositiveIntegerField()
    has_own_permissions = models.BooleanField(default=False)

    objects = ParagraphQuerySet.as_manager()

    class Meta:
        """Stable IDs are unique within a version."""

        ordering = ["version", "position"]
        constraints = [
            models.UniqueConstraint(fields=["version", "stable_id"], name="paragraph_unique_id"),
            *gate_constraints("paragraph"),
        ]

    def __str__(self) -> str:
        """Return ``<version>/<stable id>``."""
        return f"{self.version_id}/{self.stable_id}"


class Figure(GatedPermissions):
    """A figure or table, with its own licence decision (§1.1 addendum).

    Attributes:
        version: The paper version.
        stable_id: rbcore's ID, ``fig3`` or ``table2``.
        kind: "figure" or "table".
        label: Label such as "Figure 1".
        caption_title: Caption title.
        caption: Caption text.
        section_stable_id: Stable ID of the section it appears in (or that
            first cites it), or "".
        xml_id: The publisher's ``@id``.
        graphics: ``xlink:href`` of each graphic.
        footnotes: Table footnotes.
        source_xml: The object's original JATS XML (untrusted).
        position: Document order among the version's figures and tables.
        has_own_permissions: Whether a ``<permissions>`` block applies to it.
    """

    class Kind(models.TextChoices):
        """Figure or table."""

        FIGURE = "figure", "Figure"
        TABLE = "table", "Table"

    version = models.ForeignKey(PaperVersion, on_delete=models.CASCADE, related_name="figures")
    stable_id = models.CharField(max_length=64)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    label = models.CharField(max_length=255, blank=True)
    caption_title = models.TextField(blank=True)
    caption = models.TextField(blank=True)
    section_stable_id = models.CharField(max_length=128, blank=True)
    xml_id = models.CharField(max_length=255, blank=True)
    graphics = models.JSONField(default=list, blank=True)
    footnotes = models.JSONField(default=list, blank=True)
    source_xml = models.TextField(blank=True)
    position = models.PositiveIntegerField()
    has_own_permissions = models.BooleanField(default=False)

    objects = FigureQuerySet.as_manager()

    class Meta:
        """Stable IDs are unique within a version."""

        ordering = ["version", "position"]
        constraints = [
            models.UniqueConstraint(fields=["version", "stable_id"], name="figure_unique_id"),
            *gate_constraints("figure"),
        ]

    def __str__(self) -> str:
        """Return ``<version>/<stable id>``."""
        return f"{self.version_id}/{self.stable_id}"
