from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.params import Body, Parameter

if TYPE_CHECKING:
    from typing import Any

__all__ = ("After", "Around", "Before", "Limit", "RoleCreate", "RoleSlug", "RoleUpdate")


def RoleCreate() -> Any:
    """Role create param."""
    return Body(
        title="Role Creation Data",
        description="Information required to create a new role.",
    )


def RoleSlug(*, action: str) -> Any:
    """Role slug param."""
    return Parameter(
        title="Role Slug", description=f"The unique slug of the role to {action}."
    )


def Limit() -> Any:
    """Limit param."""
    return Parameter(
        title="Limit",
        description="Maximum number of roles to retrieve in this batch.",
    )


def Before() -> Any:
    """Before param."""
    return Parameter(
        title="Before ID",
        description="Retrieve roles with IDs smaller than this ID.",
    )


def After() -> Any:
    """After param."""
    return Parameter(
        title="After ID",
        description="Retrieve roles with IDs larger than this ID.",
    )


def Around() -> Any:
    """Around param."""
    return Parameter(
        title="Around ID",
        description="Retrieve roles around this ID.",
    )


def RoleUpdate() -> Any:
    """Role param."""
    return Body(title="Role Update Data", description="The updated fields for role.")
