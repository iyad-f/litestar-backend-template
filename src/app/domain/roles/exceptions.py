from __future__ import annotations

from app.lib.exceptions import NotFoundError

__all__ = ("RoleNotFoundError",)


class RoleNotFoundError(NotFoundError):
    """Raises when a role is not found."""

    def __init__(self, slug: str) -> None:
        msg = f"Role '{slug}' was not found."
        super().__init__(msg)
