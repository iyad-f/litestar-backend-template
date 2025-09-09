from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from asyncpg import PostgresConnectionError
from litestar import Controller, Response, get
from litestar.status_codes import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR
from redis import RedisError

from app.config.app import APP_CONFIG

from .schemas import Health

if TYPE_CHECKING:
    from typing import Final

    from app.lib.db import Connection

__all__ = ("SystemController",)


LOGGER: Final = logging.getLogger(__name__)


class SystemController(Controller):
    """System controller."""

    tags = ["System"]
    path = APP_CONFIG.base_url
    opt = {"exclude_from_auth": True}

    @get(path="/health")
    async def check_health(self, db_connection: Connection) -> Response[Health]:
        """Check health."""
        try:
            await db_connection.execute("SELECT 1")
        except PostgresConnectionError:
            db_ping = False
        else:
            db_ping = True

        try:
            cache_ping = await APP_CONFIG.redis.create_client().ping()
        except RedisError:
            cache_ping = False

        db_status = "online" if db_ping else "offline"
        cache_status = "online" if cache_ping else "offline"

        if db_ping and cache_ping:
            status_code = HTTP_200_OK
            LOGGER.debug(
                "System Health database_status=%s cache_status=%s",
                db_status,
                cache_status,
            )
        else:
            status_code = HTTP_500_INTERNAL_SERVER_ERROR
            LOGGER.warning(
                "System Health database_status=%s cache_status=%s",
                db_status,
                cache_status,
            )

        return Response(
            content=Health(database_status=db_status, cache_status=cache_status),
            status_code=status_code,
        )
