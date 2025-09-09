from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from msgspec import UNSET, UnsetType, field

from app.lib.exceptions import ValidationError
from app.lib.schemas import Struct

if TYPE_CHECKING:
    from typing import Any

__all__ = ("Note", "NoteCreate", "NoteUpdate")


def note_validation(self: NoteCreate | NoteUpdate) -> None:
    invalid_parameters: list[dict[str, Any]] = []
    title: str | UnsetType = self.title
    content: str | UnsetType = self.content

    if title is not UNSET and not 1 <= len(title) <= 100:
        invalid_parameters.append(
            {
                "field": "title",
                "message": "title must be between 1 and 100 charecters.",
            }
        )

    if content is not UNSET and not 1 <= len(content) <= 50000:
        invalid_parameters.append(
            {
                "field": "content",
                "message": "content must be between 1 and 50000 characters.",
            }
        )

    if invalid_parameters:
        raise ValidationError(
            detail="Validation failed for one or more fields.",
            invalid_parameters=invalid_parameters,
        )


class NoteCreate(Struct):
    """Note creation data."""

    title: str
    content: str
    locked: bool = field(default=False)

    __post_init__ = note_validation


class Note(Struct):
    """Note."""

    id: int
    owner_id: int
    title: str
    content: str
    locked: bool

    # for admins
    updated_at: datetime | UnsetType = UNSET
    deleted_at: datetime | None | UnsetType = UNSET


class NoteUpdate(Struct):
    """Note update data."""

    title: str | UnsetType = UNSET
    content: str | UnsetType = UNSET
    locked: bool | UnsetType = UNSET

    __post_init__ = note_validation
