from __future__ import annotations

from typing import TYPE_CHECKING, dataclass_transform

import msgspec

if TYPE_CHECKING:
    from typing import Any


__all__ = ("Struct",)


@dataclass_transform(field_specifiers=(msgspec.field,), frozen_default=True)
class Struct(msgspec.Struct, frozen=True):
    """Base configuration struct for the application."""

    def to_dict(self) -> dict[str, Any]:
        """Convert the struct to a dictionary."""
        return msgspec.to_builtins(self)
