from __future__ import annotations

from typing import TYPE_CHECKING

from app.lib.jwt import Token
from app.middleware.auth import AuthenticatedUser

if TYPE_CHECKING:
    from typing import Any

    from litestar import Request

__all__ = ("provide_current_user",)


def provide_current_user(
    request: Request[AuthenticatedUser, Token, Any],
) -> AuthenticatedUser:
    """Provide the currently authenticated user from the request.

    Parameters
    ----------
    request : Request[AuthenticatedUser, Token, Any]
        The incoming request.

    Returns
    -------
    AuthenticatedUser
        The authenticated user.
    """
    return request.user
