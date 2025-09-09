from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Final

__all__ = ("DB_DIR",)

DB_DIR: Final = (pathlib.Path(__file__).parent.parent / "db").resolve()
