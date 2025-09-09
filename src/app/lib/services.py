from __future__ import annotations

import asyncio

from passlib.context import CryptContext

from .db import Connection

__all__ = ("CryptService", "DBService")


class DBService:
    """Database service."""

    __slots__ = ("_conn",)

    _conn: Connection

    def __init__(self, db_connection: Connection) -> None:
        self._conn = db_connection


class CryptService:
    """Crypt service."""

    __slots__ = ("_crypt_context",)

    _crypt_context: CryptContext

    def __init__(self) -> None:
        self._crypt_context = CryptContext(schemes=["argon2"], deprecated="auto")

        # The reason for not instantiating loop here is, because this class initialised as a class variable mostly,
        # so the instantiation will happen before the eventloop runs.

    async def hash(self, secret: str) -> str:
        """Hash."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._crypt_context.hash, secret)

    async def verify(self, secret: str, hash_: str) -> bool:
        """Verify."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._crypt_context.verify, secret, hash_)
