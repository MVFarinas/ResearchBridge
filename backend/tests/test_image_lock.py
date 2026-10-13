"""The Docker image installs exactly the versions the tests ran against."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+)", re.MULTILINE)


def pins(path: Path) -> dict[str, str]:
    """Read ``name==version`` pins from a pip-compile output file."""
    return {name.lower(): version for name, version in _PIN.findall(path.read_text())}


def test_backend_image_lock_matches_dev_lock() -> None:
    """Every pin in requirements/backend.txt equals the one in requirements/dev.txt."""
    dev = pins(ROOT / "requirements" / "dev.txt")
    image = pins(ROOT / "requirements" / "backend.txt")
    assert {"django", "procrastinate", "psycopg", "gunicorn"} <= set(image)
    assert {
        name: (version, dev.get(name))
        for name, version in image.items()
        if dev.get(name) != version
    } == {}


def test_dockerfile_installs_the_image_lock() -> None:
    """The Dockerfile reads the runtime lock and both local packages."""
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text()
    assert "COPY requirements/backend.txt" in dockerfile
    assert "pip install --no-deps /src/libs/rbcore /src/backend" in dockerfile
    assert "USER app" in dockerfile
