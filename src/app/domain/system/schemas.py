from __future__ import annotations

from typing import Literal

from app.lib.schemas import Struct

__all__ = ("Health",)

type ServiceStatus = Literal["online", "offline"]


class Health(Struct):
    """Represents the system health."""

    database_status: ServiceStatus
    cache_status: ServiceStatus
