from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .services import ActiveAccessTokenService, RefreshTokenService

if TYPE_CHECKING:
    from saq.types import Context


LOGGER = logging.getLogger(__name__)


async def remove_invalid_refresh_tokens(_: Context) -> None:
    """Task to remove all invalid refresh tokens."""
    # Circular import
    from app.config import LITESTAR_CONFIG

    LOGGER.info("Starting refresh token cleanup job.")

    async with LITESTAR_CONFIG.asyncpg.get_connection() as conn:
        refresh_token_service = RefreshTokenService(conn)  # pyright: ignore[reportArgumentType]
        deleted = await refresh_token_service.remove_invalid_tokens()

    LOGGER.info("Refresh token cleanup job completed. %s tokens deleted.", deleted)


async def remove_expired_access_tokens(_: Context) -> None:
    """Task to remove all expired access tokens."""
    # Circular import
    from app.config import LITESTAR_CONFIG

    LOGGER.info("Starting access token cleanup job.")

    async with LITESTAR_CONFIG.asyncpg.get_connection() as conn:
        active_access_token_service = ActiveAccessTokenService(conn)  # pyright: ignore[reportArgumentType]
        deleted = await active_access_token_service.remove_expired_tokens()

    LOGGER.info("Access token cleanup job completed. %s tokens deleted.", deleted)
