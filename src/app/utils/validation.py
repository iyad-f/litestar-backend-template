from __future__ import annotations

from typing import TYPE_CHECKING

from app.lib.exceptions import ValidationError

from .sentinel import issentinel

if TYPE_CHECKING:
    from typing import Any

__all__ = ("ensure_single_pagination_param",)


def ensure_single_pagination_param(*params: Any, message: str | None = None) -> None:
    """Validate that at most one pagination parameter is provided.

    This function checks a set of pagination parameters (e.g., ``before``,
    ``after``, ``around``) and raises a :class:`ValidationError` if more
    than one is specified. Parameters that are sentinels are ignored.

    Parameters
    ----------
    *params : Any
        Pagination parameters to validate.
    message : str, optional
        Custom error message to include in the validation error (the default is None).

    Raises
    ------
    ValidationError
        If more than one non-sentinel parameter is provided.
    """
    seen = False

    for param in params:
        if issentinel(param):
            continue

        if not seen:
            seen = True
            continue

        raise ValidationError(
            detail="Only one pagination parameter may be provided.",
            invalid_parameters=[
                {
                    "field": "query",
                    "message": message
                    or "Only one of 'before', 'after' or 'around' may be passed",
                }
            ],
        )
