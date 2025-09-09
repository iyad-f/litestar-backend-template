from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.types import Empty
from msgspec import UNSET

if TYPE_CHECKING:
    from typing import Any, TypeIs  # noqa: TID251 # It's safe to use it here

    from litestar.types import EmptyType
    from msgspec import UnsetType

    type SentinelType = EmptyType | UnsetType

__all__ = ("SentinelType", "issentinel", "none_to_sentinel")


def issentinel(value: Any | SentinelType) -> TypeIs[SentinelType]:
    """Check whether a value is a sentinel.

    Parameters
    ----------
    value : Any or SentinelType
        The value to check.

    Returns
    -------
    TypeIs[SentinelType]
        True if the value is a sentinel (`Empty` or `UNSET`), False otherwise.
    """
    return value is Empty or value is UNSET


def none_to_sentinel[T](value: T | None) -> T | SentinelType:
    """Convert `None` to a sentinel value.

    Parameters
    ----------
    value : T or None
        The value to convert.

    Returns
    -------
    T or SentinelType
        Returns `Empty` if the input is `None`, otherwise returns the input value.

    Notes
    -----
    This function exists only due to a limitation in Litestar:
    https://github.com/litestar-org/litestar/issues/4247.
    It can be removed once native support for optional query parameters is added.
    """
    return Empty if value is None else value
