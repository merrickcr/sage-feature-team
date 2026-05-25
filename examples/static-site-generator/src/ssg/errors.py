"""Custom exceptions for ssg.

Library modules raise these; only ``__main__`` decides how to render them.
"""

from __future__ import annotations


class FrontMatterError(ValueError):
    """Raised when a file's front-matter is not valid YAML.

    The message names the offending file.
    """
