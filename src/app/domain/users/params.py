from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.params import Body, Parameter

if TYPE_CHECKING:
    from typing import Any


__all__ = (
    "After",
    "Around",
    "Before",
    "Limit",
    "RefreshToken",
    "RoleSlug",
    "UserCreate",
    "UserID",
    "UserLogin",
    "UserSignup",
    "UserUpdate",
)


def UserSignup() -> Any:
    """User signup param."""
    return Body(
        title="Account Registration Data",
        description="Information required to register a new user.",
    )


def UserLogin() -> Any:
    """User login param."""
    return Body(
        title="User Login Data",
        description="Credentials required to log in to a user account.",
    )


def RefreshToken() -> Any:
    """Refresh token param."""
    return Body(
        title="Refresh Token Data",
        description="The refresh token used to obtain a new access token when the current one expires.",
    )


def UserUpdate() -> Any:
    """User update param."""
    return Body(
        title="User Update Data",
        description="The updated fields for the user.",
    )


def UserCreate() -> Any:
    """User create param."""
    return Body(
        title="User Creation Data",
        description="Information required to create a new user.",
    )


def UserID() -> Any:
    """UserID param."""
    return Parameter(
        title="User Identifier",
        description="The unique integer ID of the user to retrieve.",
    )


def Limit() -> Any:
    """Limit param."""
    return Parameter(
        title="Limit",
        description="Maximum number of users to retrieve in this batch.",
    )


def Before() -> Any:
    """Before param."""
    return Parameter(
        title="Before ID",
        description="Retrieve users with IDs smaller than this ID.",
    )


def After() -> Any:
    """After param."""
    return Parameter(
        title="After ID",
        description="Retrieve users with IDs larger than this ID.",
    )


def Around() -> Any:
    """Around param."""
    return Parameter(
        title="Around ID",
        description="Retrieve users around this ID.",
    )


def RoleSlug() -> Any:
    """Role slug param."""
    return Parameter(
        title="Role Slug", description="The unique slug of the role to assign."
    )
