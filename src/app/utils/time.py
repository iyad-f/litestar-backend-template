from __future__ import annotations

import datetime

__all__ = ("utcnow",)


def utcnow() -> datetime.datetime:
    """Return the current UTC datetime.

    Returns
    -------
    datetime.datetime
        The current UTC datetime with timezone information.
    """
    return datetime.datetime.now(datetime.UTC)
