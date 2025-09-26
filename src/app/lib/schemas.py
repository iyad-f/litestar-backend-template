from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from typing import Any

__all__ = ("Message", "Struct")


# Most of the structs used for schema in this application reference scalar values only,
# and hence the gc=False default, If any of your structs reference containers like
# list's, dict's, structsmake sure to set gc=True.
# Read this: https://jcristharif.com/msgspec/structs.html#disabling-garbage-collection-advanced
class Struct(msgspec.Struct, gc=False):
    """Base schemas struct for application."""

    def to_dict(self) -> dict[str, Any]:
        """Convert the struct to a dictionary."""
        return msgspec.to_builtins(self)


class Message(Struct):
    """Message response."""

    message: str
