from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import APP_CONFIG
from app.lib.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from typing import Any

    from litestar.connection import ASGIConnection
    from litestar.handlers.base import BaseRouteHandler


__all__ = ("forbid_admin_role",)


def forbid_admin_role(
    connection: ASGIConnection[Any, Any, Any, Any], _: BaseRouteHandler
) -> None:
    """Guard function to check if the admin role is being assigned.

    Parameters
    ----------
    connection : ASGIConnection[Any, Any, Any, Any]
        The ASGI connection instance representing the current request.
    _ : BaseRouteHandler
        The route handler being guarded (unused).

    Raises
    ------
    PermissionDeniedError
        If the requested `role_slug` corresponds to the admin role.
    """
    if connection.path_params["role_slug"] == APP_CONFIG.roles.admin_role_slug:
        detail = "You cannot assign the admin role."
        raise PermissionDeniedError(detail=detail)
