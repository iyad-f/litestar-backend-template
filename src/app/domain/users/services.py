from __future__ import annotations

import datetime
import secrets
from typing import TYPE_CHECKING, overload

from asyncpg import UniqueViolationError
from litestar import Request
from litestar.types import Empty

from app.config import APP_CONFIG
from app.db import models
from app.domain.roles.exceptions import RoleNotFoundError
from app.lib.db import Connection
from app.lib.exceptions import ConflictError, NoFieldsToUpdateError, PermissionDeniedError
from app.lib.services import CryptService, DBService
from app.lib.sonyflake import SONYFLAKE
from app.utils.db import get_rowcount, rows_affected
from app.utils.sentinel import issentinel
from app.utils.time import utcnow
from app.utils.validation import ensure_single_pagination_param

from . import exceptions

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any, ClassVar

    from app.server.stores import RedisStore, SetManyItem
    from app.utils.sentinel import SentinelType

__all__ = (
    "ActiveAccessTokenService",
    "RefreshTokenService",
    "UserRoleService",
    "UserService",
)


class UserService(DBService):
    """User service."""

    _crypt_service: ClassVar[CryptService] = CryptService()

    @overload
    async def create_user(
        self,
        *,
        name: str,
        password: str,
        locked_notes_secret: str,
        fields: Iterable[models.UserField] = ...,
    ) -> models.User: ...

    @overload
    async def create_user(
        self,
        *,
        name: str,
        password: str,
        locked_notes_secret: str,
        fields: SentinelType = ...,
    ) -> None: ...

    async def create_user(
        self,
        *,
        name: str,
        password: str,
        locked_notes_secret: str,
        fields: Iterable[models.UserField] | SentinelType = Empty,
    ) -> models.User | None:
        """Create a new user."""
        query = """
        INSERT INTO users (
            id,
            name,
            hashed_password,
            locked_notes_secret_hash
        )
        VALUES ($1, $2, $3, $4)
        """
        hashed_password = await self._crypt_service.hash(password)
        locked_notes_secret_hash = await self._crypt_service.hash(locked_notes_secret)
        user_id = await SONYFLAKE.next_id_async()
        values = (user_id, name, hashed_password, locked_notes_secret_hash)

        try:
            if not issentinel(fields):
                query += f" RETURNING {', '.join(fields)}"

                return await self._conn.fetchrow(query, *values, record_class=models.User)

            await self._conn.execute(query, *values)
        except UniqueViolationError as e:
            detail = f"User with name {name} already exists."
            raise PermissionDeniedError(detail=detail) from e
        else:
            return None

    async def fetch_user(
        self,
        *,
        user_id: int | SentinelType = Empty,
        name: str | SentinelType = Empty,
        is_disabled: bool | SentinelType = Empty,
        is_deleted: bool | SentinelType = Empty,
        fields: Iterable[models.UserField],
    ) -> models.User:
        """Fetch a user."""
        where_parts: list[str] = []
        values: list[Any] = []

        if not issentinel(user_id):
            where_parts.append("id = $1")
            values.append(user_id)

        elif not issentinel(name):
            where_parts.append("name = $1")
            values.append(name)

        else:
            msg = "One of 'user_id' or 'name' must be provided"
            raise ValueError(msg)

        if not issentinel(is_disabled):
            where_parts.append("disabled = $2")
            values.append(is_disabled)

        if is_deleted is True:
            where_parts.append("deleted_at IS NOT NULL")
        elif is_deleted is False:
            where_parts.append("deleted_at IS NULL")

        query = f"""
        SELECT {", ".join(fields)},
            CASE
                WHEN deleted_at IS NOT NULL THEN 1
                WHEN disabled THEN 2
                ELSE 0
            END AS status
        FROM users
        WHERE {" AND ".join(where_parts)}
        """

        user = await self._conn.fetchrow(query, *values, record_class=models.User)

        if user is None or (not is_deleted and user["status"] == 1):
            raise exceptions.UserNotFoundError(user_id=user_id, name=name)

        if not is_disabled and user["status"] == 2:
            raise exceptions.UserDisabledError(user_id=user_id, name=name)

        return user

    async def fetch_users(
        self,
        *,
        is_disabled: bool | SentinelType = Empty,
        is_deleted: bool | SentinelType = Empty,
        limit: int = 100,
        before: int | SentinelType = Empty,
        after: int | SentinelType = Empty,
        around: int | SentinelType = Empty,
        fields: Iterable[models.UserField],
    ) -> list[models.User]:
        """Fetch multiple users."""
        ensure_single_pagination_param(before, after, around)
        limit = max(1, min(limit, 100))

        columns = ", ".join(fields)
        where_parts = ["TRUE"]
        values: list[Any] = []
        idx = 1

        if not issentinel(is_disabled):
            where_parts.append(f"disabled = ${idx}")
            values.append(is_disabled)
            idx += 1

        if is_deleted is True:
            where_parts.append("deleted_at IS NOT NULL")
        elif is_deleted is False:
            where_parts.append("deleted_at IS NULL")

        where_clause = " AND ".join(where_parts)

        if not issentinel(before):
            where_clause += f" AND id < ${idx}"
            query = f"""
            SELECT {columns}
            FROM users
            WHERE {where_clause}
            ORDER BY id DESC
            LIMIT ${idx + 1}
            """
            values.extend((before, limit))

        elif not issentinel(after):
            where_clause += f" AND id > ${idx}"
            query = f"""
            SELECT {columns}
            FROM users
            WHERE {where_clause}
            ORDER BY id ASC
            LIMIT ${idx}
            """
            values.extend((after, limit))

        elif not issentinel(around):
            before_limit = limit // 2
            after_limit = limit - before_limit

            where_clause_before = where_clause + f" AND id < ${idx}"
            where_clause_after = where_clause + f" AND id > ${idx}"

            query = f"""
            SELECT {columns}
            FROM users
            WHERE {where_clause_before}
            ORDER BY id DESC
            LIMIT ${idx + 1}

            UNION

            SELECT {columns}
            FROM users
            WHERE {where_clause_after}
            ORDER BY id ASC
            LIMIT ${idx + 2}
            """
            values.extend((around, around, before_limit, after_limit))

        else:
            query = f"""
            SELECT {columns}
            FROM users
            WHERE {where_clause}
            ORDER BY id ASC
            LIMIT ${idx}
            """
            values.append(limit)

        return await self._conn.fetch(query, *values, record_class=models.User)

    @overload
    async def update_user(
        self,
        *,
        user_id: int,
        is_disabled: bool | SentinelType = ...,
        is_deleted: bool | SentinelType = ...,
        name: str | SentinelType = ...,
        password: str | SentinelType = ...,
        locked_notes_secret: str | SentinelType = ...,
        deleted: bool | SentinelType = ...,
        disabled: bool | SentinelType = ...,
        fields: Iterable[models.UserField] = ...,
    ) -> models.User: ...

    @overload
    async def update_user(
        self,
        *,
        user_id: int,
        is_disabled: bool | SentinelType = ...,
        is_deleted: bool | SentinelType = ...,
        name: str | SentinelType = ...,
        password: str | SentinelType = ...,
        locked_notes_secret: str | SentinelType = ...,
        deleted: bool | SentinelType = ...,
        disabled: bool | SentinelType = ...,
        fields: SentinelType = ...,
    ) -> None: ...

    async def update_user(
        self,
        *,
        user_id: int,
        is_disabled: bool | SentinelType = Empty,
        is_deleted: bool | SentinelType = Empty,
        name: str | SentinelType = Empty,
        password: str | SentinelType = Empty,
        locked_notes_secret: str | SentinelType = Empty,
        deleted: bool | SentinelType = Empty,
        disabled: bool | SentinelType = Empty,
        fields: Iterable[models.UserField] | SentinelType = Empty,
    ) -> models.User | None:
        """Update a user."""
        cols: list[str] = []
        values: list[Any] = []

        if not issentinel(disabled):
            cols.append("disabled")
            values.append(disabled)

        if not issentinel(name):
            cols.append("name")
            values.append(name)

        if not issentinel(password):
            cols.append("hashed_password")
            values.append(await self._crypt_service.hash(password))

        if not issentinel(locked_notes_secret):
            cols.append("locked_notes_secret_hash")
            values.append(await self._crypt_service.hash(locked_notes_secret))

        set_parts = [f"{col} = ${i}" for i, col in enumerate(cols, 1)]

        if deleted is True:
            set_parts.append("deleted_at = NOW()")
        elif deleted is False:
            set_parts.append("deleted_at = NULL")

        if not set_parts:
            raise NoFieldsToUpdateError

        set_parts.append("updated_at = NOW()")

        where_parts = [f"id = ${len(cols) + 1}"]

        if is_disabled is False:
            where_parts.append("disabled = FALSE")
        elif is_disabled is True:
            where_parts.append("disabled = TRUE")

        if is_deleted is False:
            where_parts.append("deleted_at IS NULL")
        elif is_deleted is True:
            where_parts.append("deleted_at IS NOT NULL")

        query = f"""
        UPDATE users
        SET {", ".join(set_parts)}
        WHERE {" AND ".join(where_parts)}
        """
        values.append(user_id)

        if not issentinel(fields):
            query += f" RETURNING {', '.join(fields)}"
            user = await self._conn.fetchrow(query, *values, record_class=models.User)

            if user is not None:
                return user

            updated = False
        else:
            status = await self._conn.execute(query, *values)
            updated = rows_affected(status)

        if not updated:
            raise exceptions.UserNotFoundError(user_id=user_id)

        return None

    async def authenticate_user(self, *, name: str, password: str) -> models.User:
        """Authenticate a user."""
        user = await self.fetch_user(
            name=name, is_deleted=False, fields=("id", "disabled", "hashed_password")
        )

        if user is None or not await self._crypt_service.verify(
            password, user.hashed_password
        ):
            detail = "The provided name or password was invalid."
            raise PermissionDeniedError(detail=detail)

        if user.disabled:
            detail = f"The account of user with id '{user.id}' has been disabled."
            raise PermissionDeniedError(detail=detail)

        return user

    async def verify_notes_secret(self, *, user_id: int, secret: str) -> None:
        """Verify notes secret."""
        user = await self.fetch_user(
            user_id=user_id, fields=("locked_notes_secret_hash",)
        )
        if not await self._crypt_service.verify(secret, user.locked_notes_secret_hash):
            detail = "The provided note secret is invalid."
            raise PermissionDeniedError(detail=detail)


class UserRoleService(DBService):
    """User role service."""

    async def assign_role(self, *, user_id: int, role_slug: str) -> None:
        """Assign role to a user."""
        # This is the solution that came to my mind at this point. If you come up with
        # something better, sure...
        query = """
        WITH
        selected_user AS (
            SELECT id FROM users WHERE id = $1
        ),
        selected_role AS (
            SELECT id FROM roles WHERE slug = $2
        ),
        inserted AS (
            INSERT INTO user_roles (id, user_id, role_id)
            SELECT $3, u.id, r.id
            FROM selected_user u, selected_role r
            ON CONFLICT (user_id, role_id) DO NOTHING
            RETURNING *
        )
        SELECT
            EXISTS (SELECT 1 FROM selected_user) AS user_exists,
            EXISTS (SELECT 1 FROM selected_role) AS role_exists,
            EXISTS (SELECT 1 FROM inserted) AS inserted
        """
        values = (user_id, role_slug, await SONYFLAKE.next_id_async())
        record = await self._conn.fetchrow(query, *values)

        assert record is not None

        if not record["user_exists"]:
            raise exceptions.UserNotFoundError(user_id=user_id)

        if not record["role_exists"]:
            raise RoleNotFoundError(slug=role_slug)

        if not record["inserted"]:
            detail = f"User with id '{user_id}' already has the role '{role_slug}'."
            raise ConflictError(detail=detail)

    async def assign_role_to_many(
        self, *, user_ids: Iterable[int], role_slug: str
    ) -> None:
        """Assign role to many users.

        Note: Don't use this method if you want row by row detail,
        use :meth:`assign_role` with a loop instead.
        """
        query = """
        INSERT INTO user_roles (
            id,
            user_id,
            role_id
        )
        SELECT $1, u.id, r.id
        FROM users u
        JOIN roles r ON r.slug = $3
        WHERE u.id = $2
        ON CONFLICT (user_id, role_id) DO NOTHING
        """
        values = [
            (
                await SONYFLAKE.next_id_async(),
                user_id,
                role_slug,
            )
            for user_id in user_ids
        ]
        await self._conn.executemany(query, values)

    async def assign_roles(self, *, user_id: int, role_slugs: Iterable[str]) -> None:
        """Assign multiple roles to a user.

        Note: Don't use this method if you want row by row detail,
        use :meth:`assign_role` with a loop instead.
        """
        query = """
        INSERT INTO user_roles (
            id,
            user_id,
            role_id
        )
        SELECT $1, u.id, r.id
        FROM users u, roles r
        WHERE u.id = $2 AND r.slug = $3
        ON CONFLICT (user_id, role_id) DO NOTHING
        """
        values = [
            (
                await SONYFLAKE.next_id_async(),
                user_id,
                role_slug,
            )
            for role_slug in role_slugs
        ]
        await self._conn.executemany(query, values)

    async def fetch_roles(
        self,
        *,
        user_id: int,
        fields: Iterable[models.RoleField],
    ) -> list[models.Role]:
        """Fetch all roles assigned to a user."""
        columns = ", ".join(f"r.{f}" for f in fields)
        query = f"""
        SELECT {columns}
        FROM roles r
        JOIN user_roles ur ON ur.role_id = r.id
        WHERE ur.user_id = $1
        """
        return await self._conn.fetch(query, user_id, record_class=models.Role)

    async def remove_role(self, *, user_id: int, role_slug: str) -> None:
        """Remove role from a user."""
        query = """
        DELETE FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id = $1 AND r.slug = $2
        """
        values = (user_id, role_slug)
        status = await self._conn.execute(query, *values)
        if not rows_affected(status):
            detail = (
                f"User with id '{user_id}' doesn't have the role with slug '{role_slug}'."
            )
            raise ConflictError(detail=detail)


class RefreshTokenService(DBService):
    """Refresh token service."""

    _crypt_service: ClassVar[CryptService] = CryptService()

    def generate_token(self) -> str:
        """Generate a new refresh token."""
        return secrets.token_urlsafe(32)

    async def create_token(
        self,
        *,
        token: str,
        user_id: int,
        fields: Iterable[models.RefreshTokenField] | SentinelType = Empty,
    ) -> models.RefreshToken | None:
        """Create a new token in the database."""
        query = """
        INSERT INTO refresh_tokens (
            id,
            user_id,
            token_prefix,
            hashed_token,
            expires_at
        )
        VALUES ($1, $2, $3, $4, $5)
        """
        token_id = await SONYFLAKE.next_id_async()
        hashed_token = await self._crypt_service.hash(token)
        expires_at = utcnow() + datetime.timedelta(
            minutes=APP_CONFIG.refresh_token.expiry
        )
        values = (token_id, user_id, token[:24], hashed_token, expires_at)

        if not issentinel(fields):
            query += f"RETURNING {', '.join(fields)}"

            return await self._conn.fetchrow(
                query, *values, record_class=models.RefreshToken
            )

        await self._conn.execute(query, *values)
        return None

    async def _fetch_token(
        self,
        *,
        token: str,
        is_valid: bool = True,
        fields: Iterable[models.RefreshTokenField],
    ) -> models.RefreshToken | None:
        columns = ", ".join(fields)
        query = f"""
        SELECT {columns}, hashed_token as temp_hash FROM refresh_tokens
        WHERE token_prefix = $1
        """

        if is_valid:
            query += " AND revoked = FALSE AND NOW() < expires_at"

        tokens = await self._conn.fetch(
            query, token[:24], record_class=models.RefreshToken
        )

        for t in tokens:
            if await self._crypt_service.verify(token, t["temp_hash"]):
                return t

        return None

    async def authenticate_token(self, *, token: str) -> models.RefreshToken:
        """Authenticate token."""
        found_token = await self._fetch_token(token=token, fields=("id", "user_id"))

        if found_token is None:
            detail = "Invalid refresh token"
            raise PermissionDeniedError(detail=detail)

        await self.revoke_token(token_id=found_token.id)

        return found_token

    async def revoke_token(
        self, *, token: str | SentinelType = Empty, token_id: int | SentinelType = Empty
    ) -> None:
        """Revoke token."""
        query = """
        UPDATE refresh_tokens SET revoked = TRUE
        WHERE id = $1
        """

        if not issentinel(token_id):
            await self._conn.execute(query, token_id)

        elif not issentinel(token):
            found_token = await self._fetch_token(
                token=token, fields=("id",), is_valid=False
            )
            if found_token is not None:
                await self._conn.execute(query, found_token.id)

        else:
            msg = "One of 'token' or 'token_id' must be provided."
            raise ValueError(msg)

    async def revoke_tokens(self, *, user_id: int) -> None:
        """Revoke all tokens of a user."""
        query = """
        UPDATE refresh_tokens SET revoked = TRUE
        WHERE user_id = $1 AND revoked = FALSE
        """
        await self._conn.execute(query, user_id)

    async def remove_invalid_tokens(self) -> int:
        """Remove invalid tokens."""
        query = """
        DELETE FROM refresh_tokens
        WHERE NOW() > expires_at OR revoked = TRUE
        """

        status = await self._conn.execute(query)
        return get_rowcount(status)


class ActiveAccessTokenService(DBService):
    """Atice access token service."""

    __slots__ = ("_store",)

    _store: RedisStore

    def __init__(
        self, db_connection: Connection, request: Request[Any, Any, Any] | None = None
    ) -> None:
        # This will be not None when we need the store
        if request is not None:
            store: RedisStore = request.app.stores.get(
                APP_CONFIG.access_token.blacklist_store
            )  # pyright: ignore[reportAssignmentType]
            self._store = store

        super().__init__(db_connection)

    async def create_token(
        self, *, user_id: int, jti: str, expires_at: datetime.datetime
    ) -> None:
        """Create a new access token in the database."""
        query = """
        INSERT INTO active_access_tokens (
            id,
            user_id,
            jti,
            expires_at
        )
        VALUES ($1, $2, $3, $4)
        -- The chances of this happening are negligible.
        ON CONFLICT (user_id, jti) DO NOTHING
        """
        values = (await SONYFLAKE.next_id_async(), user_id, jti, expires_at)
        await self._conn.execute(query, *values)

    async def fetch_tokens(
        self,
        *,
        user_id: int | SentinelType = Empty,
        role_slug: str | SentinelType = Empty,
        fields: Iterable[models.ActiveAccessTokenField],
    ) -> list[models.ActiveAccessToken]:
        """Fetch multiple tokens."""
        if not issentinel(user_id):
            columns = ", ".join(fields)
            query = f"""
            SELECT {columns} FROM active_access_tokens
            WHERE NOW() < expires_at AND user_id = $1
            """
            values = (user_id,)

        elif not issentinel(role_slug):
            columns = ", ".join(f"aat.{f}" for f in fields)
            query = f"""
            SELECT {columns}
            FROM active_access_tokens act
            WHERE NOW() < act.expires_at AND EXISTS (
                SELECT 1
                FROM user_roles ur
                JOIN roles r ON r.slug = $1 AND ur.role_id = r.id
                WHERE ur.user_id = act.user_id
            )
            """
            values = (role_slug,)

        else:
            msg = "One of 'user_id' or 'role_slug' must be provided."
            raise ValueError(msg)

        return await self._conn.fetch(
            query, *values, record_class=models.ActiveAccessToken
        )

    async def blacklist_token(self, *, jti: str, expires_in: int) -> None:
        """Blacklist a token."""
        await self._store.set(jti, "", max(1, expires_in))

    async def blacklist_tokens(
        self,
        *,
        user_id: int | SentinelType = Empty,
        role_slug: str | SentinelType = Empty,
    ) -> None:
        """Blacklist all active tokens of a user in redis."""
        tokens = await self.fetch_tokens(
            user_id=user_id, role_slug=role_slug, fields=("jti", "expires_at")
        )

        if not tokens:
            return

        items: list[SetManyItem] = [(t.jti, "", max(1, t.expires_in)) for t in tokens]
        await self._store.set_many(items, transaction=False)

    async def remove_expired_tokens(self) -> int:
        """Remove all expires tokens."""
        query = """
        DELETE FROM active_access_tokens
        WHERE NOW() > expires_at
        """

        status = await self._conn.execute(query)
        return get_rowcount(status)
