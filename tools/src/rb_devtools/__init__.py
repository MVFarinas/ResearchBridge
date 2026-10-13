"""Repository checks for ResearchBridge, run by ``make lint``.

These enforce conventions that ruff cannot: a docstring on every function,
class and method (including private helpers and nested functions), and that
every discovered Python package is part of the lock file.
"""
