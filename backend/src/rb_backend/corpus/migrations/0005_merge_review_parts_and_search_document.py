"""Join Phase 2's review-part migration and Phases 4-5's search document migration.

Both branches added a ``0004`` migration on top of ``0003``. They touch
different tables (``corpus_licencereview`` and the new
``corpus_searchdocument``), so the merge has no operations; it exists so
databases that already applied either one migrate cleanly.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """No-op merge of the two ``0004`` corpus migrations."""

    dependencies = [
        ("corpus", "0004_review_part_survives_text_removal"),
        ("corpus", "0004_search_document"),
    ]

    operations = []
