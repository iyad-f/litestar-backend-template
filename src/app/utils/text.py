from __future__ import annotations

import re
import unicodedata

__all__ = ("slugify",)


def slugify(
    value: str, *, separator: str | None = None, allow_unicode: bool = False
) -> str:
    """Generate an ASCII (or Unicode) slug from the given string.

    Parameters
    ----------
    value : str
        The input string to slugify.
    separator : str, optional
        The separator to use in place of spaces and hyphens.
        If `None`, hyphens are used (the default is None).
    allow_unicode : bool, optional
        Whether to allow Unicode characters in the output. If False,
        non-ASCII characters are removed (the default is False).

    Returns
    -------
    str
        A slugified version of the input string.
    """
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    if separator is not None:
        return re.sub(r"[-\s]+", "-", value).strip("-_").replace("-", separator)
    return re.sub(r"[-\s]+", "-", value).strip("-_")
