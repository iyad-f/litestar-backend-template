from __future__ import annotations

from typing import TYPE_CHECKING, dataclass_transform

from asyncpg import Record as AsyncpgRecord
from asyncpg.pool import PoolConnectionProxy

if TYPE_CHECKING:
    from typing import Any

    type Connection = PoolConnectionProxy[Record]
else:
    # PoolConnectionProxy at runtime isnt actually generic, so using
    # it that way as a type hint will cause litestar to error.
    type Connection = PoolConnectionProxy


__all__ = ("Connection", "Record")


# If you would ask me do we really need a custom record class here, I would say no, but since this
# is a template I wanted to include this aswell.


# Lie, because we are liars :)
@dataclass_transform()
class Record(AsyncpgRecord):
    """Base asyncpg Record class for the application."""

    def __getattr__(self, name: str) -> Any:
        return self[name]
