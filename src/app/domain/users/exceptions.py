from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.types import Empty

from app.lib.exceptions import NotFoundError, PermissionDeniedError
from app.utils.sentinel import issentinel

if TYPE_CHECKING:
    from app.utils.sentinel import SentinelType

__all__ = ("UserDisabledError", "UserNotFoundError")


class UserNotFoundError(NotFoundError):
    """Raised when a user is not found."""

    def __init__(
        self, *, user_id: int | SentinelType = Empty, name: str | SentinelType = Empty
    ) -> None:
        if not issentinel(user_id):
            detail = f"User with id '{user_id}' does not exist."
        elif not issentinel(name):
            detail = f"User '{name}' does not exist."
        else:
            msg = "One of 'user_id' or 'name' must be provided."
            raise ValueError(msg)

        super().__init__(detail=detail)


class UserDisabledError(PermissionDeniedError):
    """Raised when a user is disabled."""

    def __init__(
        self, *, user_id: int | SentinelType = Empty, name: str | SentinelType = Empty
    ) -> None:
        if not issentinel(user_id):
            detail = f"User with id '{user_id}' is disabled."
        elif not issentinel(name):
            detail = f"User '{name}' is disabled."
        else:
            msg = "One of 'user_id' or 'name' must be provided."
            raise ValueError(msg)

        super().__init__(detail=detail)
