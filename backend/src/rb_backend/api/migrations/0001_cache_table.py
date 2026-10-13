"""Create the database cache table (``rb_cache``) used for API rate limits.

Django creates cache tables with ``createcachetable`` rather than a model;
running it from a migration means every environment (and the test database)
gets the table with ``migrate`` alone.
"""

from django.core.management import call_command
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def create_cache_table(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Create the configured cache table if it does not exist yet.

    Args:
        apps: Historical app registry (unused).
        schema_editor: The schema editor, for its database alias.
    """
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    """Create the cache table; reversing leaves it in place (it holds only counters)."""

    dependencies: list[tuple[str, str]] = []

    operations = [migrations.RunPython(create_cache_table, migrations.RunPython.noop)]
