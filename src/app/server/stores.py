from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.stores.redis import RedisStore as LitestarRedisStore

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import timedelta

    from redis.asyncio import Redis

    type SetManyItem = tuple[str, str | bytes, int | timedelta | None]

__all__ = ("RedisStore", "SetManyItem")


class RedisStore(LitestarRedisStore):
    """Redis based, thread and process safe asynchronous key/value store.

    Extends :class:`litestar.stores.redis.RedisStore` to add additional
    functionality.
    """

    _redis: Redis[bytes]

    async def set_many(
        self, items: Iterable[SetManyItem], *, transaction: bool = True
    ) -> None:
        """Set multiple key-value pairs in Redis.

        Parameters
        ----------
        items : Iterable[SetManyItem]
            An iterable of tuples containing ``(key, value, expires_in)``.

        transaction : bool, optional
            If ``True`` all items are set atomically (the default is True).
        """
        pipe = self._redis.pipeline(transaction=transaction)

        for key, value, expires_in in items:
            value_bytes = value.encode("utf-8") if isinstance(value, str) else value
            pipe.set(self._make_key(key), value_bytes, expires_in)

        await pipe.execute()  # pyright: ignore[reportUnknownMemberType]
