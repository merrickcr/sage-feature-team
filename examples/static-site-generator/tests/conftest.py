"""Shared pytest fixtures and path setup for the ssg test suite.

The project uses a ``src/`` layout (``src/ssg/``) and ships no packaging
config in v0.1, so we put ``src/`` on ``sys.path`` here. This lets vanilla
``python -m pytest`` from the project root import ``ssg`` without an install.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to ``tests/fixtures/``."""
    return FIXTURES_DIR


@pytest.fixture
def write_md(tmp_path: Path):
    """Factory writing a Markdown file into a temp dir and returning its path.

    Usage::

        path = write_md("hello-world.md", "# Hi")
    """

    def _write(filename: str, content: str) -> Path:
        path = tmp_path / filename
        path.write_text(content, encoding="utf-8")
        return path

    return _write
