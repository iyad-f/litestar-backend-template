from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from msgspec import UNSET, UnsetType

from app.lib.exceptions import ValidationError
from app.lib.schemas import Struct

if TYPE_CHECKING:
    from typing import Any

__all__ = ("Role", "RoleCreate", "RoleUpdate")


def role_validation(self: RoleCreate | RoleUpdate) -> None:
    invalid_parameters: list[dict[str, Any]] = []
    name: str | UnsetType = self.name
    description: str | None | UnsetType = self.description

    if name is not UNSET and not 1 <= len(name) <= 100:
        invalid_parameters.append(
            {
                "field": "name",
                "message": "name must be between 1 and 100 charecters.",
            }
        )

    if (
        description is not None
        and description is not UNSET
        and not 6 <= len(description) <= 255
    ):
        invalid_parameters.append(
            {
                "field": "description",
                "message": "description must be between 6 and 255 characters.",
            }
        )

    if invalid_parameters:
        raise ValidationError(
            detail="Validation failed for one or more fields.",
            invalid_parameters=invalid_parameters,
        )


class Role(Struct):
    """Role response."""

    id: int
    name: str
    slug: str
    description: str | None
    updated_at: datetime | UnsetType = UNSET


class RoleCreate(Struct):
    """Role create."""

    name: str
    description: str | None

    __post_init__ = role_validation


class RoleUpdate(Struct):
    """Role update."""

    name: str | UnsetType = UNSET
    description: str | None | UnsetType = UNSET

    __post_init__ = role_validation
