#!/usr/bin/env python
"""Django's command-line utility for the ResearchBridge backend."""

import os
import sys


def main() -> None:
    """Run a Django management command with the backend settings."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rb_backend.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
