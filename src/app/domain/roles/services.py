from __future__ import annotations

from typing import TYPE_CHECKING, overload

from asyncpg import UniqueViolationError
from litestar.types import Empty

from app.db import models
from app.lib.exceptions import NoFieldsToUpdateError, PermissionDeniedError
from app.lib.services import DBService
from app.lib.sonyflake import SONYFLAKE
from app.utils.db import rows_affected
from app.utils.sentinel import issentinel
from app.utils.text import slugify
from app.utils.validation import ensure_single_pagination_param

from .exceptions import RoleNotFoundError

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    from app.utils.sentinel import SentinelType


__all__ = ("RoleService",)


class RoleService(DBService):
    """Role service."""

    @overload
    async def create_role(
        self,
        *,
        name: str,
        description: str | None = ...,
        fields: Iterable[models.RoleField] = ...,
    ) -> models.Role: ...

    @overload
    async def create_role(
        self, *, name: str, description: str | None = ..., fields: SentinelType = ...
    ) -> None: ...

    async def create_role(
        self,
        *,
        name: str,
        description: str | None = None,
        fields: Iterable[models.RoleField] | SentinelType = Empty,
    ) -> models.Role | None:
        """Create Role."""
        query = """
        INSERT INTO roles (
            id,
            name,
            slug,
            description
        )
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (slug) DO NOTHING
        """
        role_id = await SONYFLAKE.next_id_async()
        slug = slugify(name)
        values = (role_id, name, slug, description)

        try:
            if not issentinel(fields):
                columns = ", ".join(fields)
                query += f" RETURNING {columns}"

                return await self._conn.fetchrow(query, *values, record_class=models.Role)

            await self._conn.execute(query, *values)
        except UniqueViolationError as e:
            detail = f"Role with name '{name}' already exists."
            raise PermissionDeniedError(detail=detail) from e
        else:
            return None

    async def fetch_role(
        self, *, slug: str, fields: Iterable[models.RoleField]
    ) -> models.Role:
        """Fetch a role."""
        query = f"""
        SELECT {", ".join(fields)} FROM roles
        WHERE slug = $1
        """

        role = await self._conn.fetchrow(query, slug, record_class=models.Role)

        if role is None:
            raise RoleNotFoundError(slug)

        return role

    async def fetch_roles(
        self,
        *,
        limit: int = 100,
        before: int | SentinelType = Empty,
        after: int | SentinelType = Empty,
        around: int | SentinelType = Empty,
        fields: Iterable[models.RoleField],
    ) -> list[models.Role]:
        """Fetch multiple roles."""
        ensure_single_pagination_param(before, after, around)
        limit = max(1, min(limit, 100))

        columns = ", ".join(fields)
        values: list[Any] = []

        if not issentinel(before):
            query = f"""
            SELECT {columns}
            FROM roles
            WHERE AND id < $1
            ORDER BY id DESC
            LIMIT $2
            """
            values.extend((before, limit))

        elif not issentinel(after):
            query = f"""
            SELECT {columns}
            FROM roles
            WHERE AND id > $1
            ORDER BY id ASC
            LIMIT $2
            """
            values.extend((after, limit))

        elif not issentinel(around):
            before_limit = limit // 2
            after_limit = limit - before_limit

            query = f"""
            SELECT {columns}
            FROM roles
            WHERE AND id < $1
            ORDER BY id DESC
            LIMIT $2

            UNION

            SELECT {columns}
            FROM roles
            WHERE AND id > $1
            ORDER BY id ASC
            LIMIT $3
            """
            values.extend((around, around, before_limit, after_limit))

        else:
            query = f"""
            SELECT {columns}
            FROM roles
            ORDER BY id ASC
            LIMIT $1
            """
            values.append(limit)

        return await self._conn.fetch(query, *values, record_class=models.Role)

    @overload
    async def update_role(
        self,
        *,
        current_slug: str,
        name: str | SentinelType = ...,
        description: str | None | SentinelType = ...,
        fields: Iterable[models.RoleField] = ...,
    ) -> models.Role: ...

    @overload
    async def update_role(
        self,
        *,
        current_slug: str,
        name: str | SentinelType = ...,
        description: str | None | SentinelType = ...,
        fields: SentinelType = ...,
    ) -> None: ...

    async def update_role(
        self,
        *,
        current_slug: str,
        name: str | SentinelType = Empty,
        description: str | None | SentinelType = Empty,
        fields: Iterable[models.RoleField] | SentinelType = Empty,
    ) -> models.Role | None:
        """Update a role."""
        cols: list[str] = []
        values: list[Any] = []

        if not issentinel(name):
            cols.extend(("name", "slug"))
            values.extend((name, slugify(name)))

        if not issentinel(description):
            cols.append("description")
            values.append(description)

        if not cols:
            raise NoFieldsToUpdateError

        set_parts = [f"{col} = ${idx}" for idx, col in enumerate(cols, 1)]
        set_parts.append("updated_at = NOW()")

        query = f"""
        UPDATE roles
        SET {", ".join(set_parts)}
        WHERE slug = ${len(cols) + 1}
        """

        if not issentinel(fields):
            query += f" RETURNING {', '.join(fields)}"
            role = await self._conn.fetchrow(query, *values, record_class=models.Role)

            if role is not None:
                return role

            updated = False
        else:
            status = await self._conn.execute(query, *values)
            updated = rows_affected(status)

        if not updated:
            raise RoleNotFoundError(current_slug)

        return None

    async def delete_role(self, *, slug: str) -> None:
        """Delete a role."""
        query = """
        DELETE FROM roles
        WHERE slug = $1
        """

        status = await self._conn.execute(query, slug)

        if not rows_affected(status):
            raise RoleNotFoundError(slug)
