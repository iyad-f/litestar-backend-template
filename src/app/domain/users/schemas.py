from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from msgspec import UNSET, UnsetType

from app.lib.exceptions import ValidationError
from app.lib.schemas import Struct

if TYPE_CHECKING:
    from typing import Any

__all__ = (
    "RefreshToken",
    "TokenResponse",
    "User",
    "UserCreate",
    "UserLogin",
    "UserSignup",
    "UserUpdate",
)

# Not using "msgspec.Meta" for validation here due to two reasons:
# 1. This way we can write better error messages.
# 2. msgspec stops validation at the first failure, whereas here we check for all
#    parameters and raise a single error containing all validation issues at once.


# This could be a mixin class which could be inherited by all of the schemas
# that need the validation, but that is not possible since gc is set to False
# for those structs and hence we cant inherit from a class.
def user_validation(self: UserSignup | UserCreate | UserUpdate) -> None:
    invalid_parameters: list[dict[str, Any]] = []
    name: str | UnsetType = getattr(self, "name")  # noqa: B009
    password: str | UnsetType = getattr(self, "password")  # noqa: B009
    locked_notes_secret: str | UnsetType = getattr(self, "locked_notes_secret")  # noqa: B009

    if name is not UNSET and not 1 <= len(name) <= 100:
        invalid_parameters.append(
            {
                "field": "name",
                "message": "name must be between 1 and 100 charecters.",
            }
        )

    if password is not UNSET and not 6 <= len(password) <= 100:
        invalid_parameters.append(
            {
                "field": "password",
                "message": "password must be between 6 and 100 characters.",
            }
        )

    if locked_notes_secret is not UNSET and not 6 <= len(locked_notes_secret) <= 100:
        invalid_parameters.append(
            {
                "field": "locked_notes_secret",
                "message": "locked notes secret must be between 6 and 100 characters.",
            }
        )

    if invalid_parameters:
        raise ValidationError(
            detail="Validation failed for one or more fields.",
            invalid_parameters=invalid_parameters,
        )


class User(Struct):
    """User response data."""

    id: int
    name: str

    # for admins
    disabled: bool | UnsetType = UNSET
    updated_at: datetime | UnsetType = UNSET
    deleted_at: datetime | None | UnsetType = UNSET


class UserSignup(Struct):
    """User signup data."""

    name: str
    password: str
    locked_notes_secret: str

    __post_init__ = user_validation


class UserLogin(Struct):
    """User login data."""

    name: str
    password: str


# This is basically the same as user signup. It could have an "admin" boolean field,
# but I don't want to allow admins to create other admins through the API. That should
# only be possible through the CLI.
class UserCreate(Struct):
    """User create data."""

    name: str
    password: str
    locked_notes_secret: str

    __post_init__ = user_validation


class UserUpdate(Struct):
    """User update data."""

    name: str | UnsetType = UNSET
    password: str | UnsetType = UNSET
    locked_notes_secret: str | UnsetType = UNSET

    __post_init__ = user_validation


class TokenResponse(Struct):
    """Token response data."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    refresh_token_expires_in: int


class RefreshToken(Struct):
    """Refresh token data."""

    refresh_token: str
