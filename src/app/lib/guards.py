from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import APP_CONFIG
from app.lib.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from typing import Any

    from litestar.connection import ASGIConnection
    from litestar.handlers.base import BaseRouteHandler

    from app.middleware.auth import AuthenticatedUser


__all__ = ("requires_admin",)


def requires_admin(
    connection: ASGIConnection[Any, AuthenticatedUser, Any, Any], _: BaseRouteHandler
) -> None:
    """
    Guard function to enforce that the currently authenticated user has administrative privileges.

    Parameters
    ----------
    connection : ASGIConnection[Any, AuthenticatedUser, Any, Any]
        The current ASGI connection object.
    _ : BaseRouteHandler
        The route handler associated with the request.

    Raises
    ------
    PermissionDeniedError
        If the authenticated user does not have the admin role.
    """
    admin = APP_CONFIG.roles.admin_role_slug
    if admin not in connection.user.roles:
        detail = "You do not have permission to perform this action. Admin privileges are required."
        raise PermissionDeniedError(detail=detail, missing_role=admin)
