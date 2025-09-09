from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import sonyflake as sf

if TYPE_CHECKING:
    from typing import Final

__all__ = ("SONYFLAKE",)

SONYFLAKE: Final = sf.Sonyflake(
    start_time=datetime.datetime(2025, 1, 1, 0, 0, 0, 0, datetime.UTC),
)
"""The global sonyflake instance for the application."""
