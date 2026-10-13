# Enable the pgvector extension (decisions.md §1.6: Postgres + pgvector).
# No vector columns exist yet; embeddings arrive with search (Phase 5).
from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True
    dependencies: list[tuple[str, str]] = []
    operations = [CreateExtension("vector")]
