from __future__ import annotations

from typing import TYPE_CHECKING, overload

from litestar.types import Empty

from app.db import models
from app.lib.exceptions import NoFieldsToUpdateError
from app.lib.services import DBService
from app.lib.sonyflake import SONYFLAKE
from app.utils.db import rows_affected
from app.utils.sentinel import issentinel
from app.utils.validation import ensure_single_pagination_param

from . import exceptions

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    from app.utils.sentinel import SentinelType


__all__ = ("NoteService",)


class NoteService(DBService):
    """Note Service."""

    @overload
    async def create_note(
        self,
        *,
        owner_id: int,
        title: str,
        content: str,
        locked: bool = ...,
        fields: Iterable[models.NoteField] = ...,
    ) -> models.Note: ...

    @overload
    async def create_note(
        self,
        *,
        owner_id: int,
        title: str,
        content: str,
        locked: bool = ...,
        fields: SentinelType = ...,
    ) -> None: ...

    async def create_note(
        self,
        *,
        owner_id: int,
        title: str,
        content: str,
        locked: bool = False,
        fields: Iterable[models.NoteField] | SentinelType = Empty,
    ) -> models.Note | None:
        """Create a new note."""
        query = """
        INSERT INTO notes (
            id,
            owner_id,
            title,
            content,
            locked
        )
        VALUES ($1, $2, $3, $4, $5)
        """
        note_id = await SONYFLAKE.next_id_async()
        values = (note_id, owner_id, title, content, locked)

        if not issentinel(fields):
            query += f" RETURNING {', '.join(fields)}"
            return await self._conn.fetchrow(query, *values, record_class=models.Note)

        await self._conn.execute(query, *values)
        return None

    async def fetch_note(
        self,
        *,
        note_id: int,
        is_locked: bool | SentinelType = Empty,
        is_deleted: bool | SentinelType = Empty,
        fields: Iterable[models.NoteField],
    ) -> models.Note:
        """Fetch a note."""
        where_parts = ["id = $1"]

        if is_locked is False or is_locked is True:
            where_parts.append("locked = TRUE")

        if is_deleted is False:
            where_parts.append("deleted_at IS NULL")
        elif is_deleted is True:
            where_parts.append("deleted_at IS NOT NULL")

        query = f"""
        SELECT {", ".join(fields)}
        FROM notes
        WHERE {" AND ".join(where_parts)}
        """

        note = await self._conn.fetchrow(query, note_id, record_class=models.Note)

        if note is None:
            raise exceptions.NoteNotFoundError(note_id)

        return note

    async def fetch_notes(
        self,
        *,
        owner_id: int | SentinelType = Empty,
        is_locked: bool | SentinelType = Empty,
        is_deleted: bool | SentinelType = Empty,
        limit: int = 100,
        before: int | SentinelType = Empty,
        after: int | SentinelType = Empty,
        around: int | SentinelType = Empty,
        fields: Iterable[models.NoteField],
    ) -> list[models.Note]:
        """Fetch multiple notes."""
        ensure_single_pagination_param(before, after, around)
        limit = max(1, min(limit, 100))

        columns = ", ".join(fields)
        where_parts = ["TRUE"]
        values: list[Any] = []
        idx = 1

        if not issentinel(owner_id):
            where_parts.append(f"owner_id = ${idx}")
            values.append(owner_id)
            idx += 1

        if is_locked is True:
            where_parts.append("locked = TRUE")
        elif is_locked is False:
            where_parts.append("locked = FALSE")

        if is_deleted is True:
            where_parts.append("deleted_at IS NOT NULL")
        elif is_deleted is False:
            where_parts.append("deleted_at IS NULL")

        where_clause = " AND ".join(where_parts)

        if not issentinel(before):
            where_clause += f" AND id < ${idx}"
            query = f"""
            SELECT {columns}
            FROM notes
            WHERE {where_clause}
            ORDER BY id DESC
            LIMIT ${idx + 1}
            """
            values.extend((before, limit))

        elif not issentinel(after):
            where_clause += f" AND id > ${idx}"
            query = f"""
            SELECT {columns}
            FROM notes
            WHERE {where_clause}
            ORDER BY id ASC
            LIMIT ${idx + 1}
            """
            values.extend((after, limit))

        elif not issentinel(around):
            before_limit = limit // 2
            after_limit = limit - before_limit

            where_clause_before = where_clause + f" AND id < ${idx}"
            where_clause_after = where_clause + f" AND id > ${idx}"

            query = f"""
            SELECT {columns}
            FROM notes
            WHERE {where_clause_before}
            ORDER BY id DESC
            LIMIT ${idx + 1}

            UNION

            SELECT {columns}
            FROM notes
            WHERE {where_clause_after}
            ORDER BY id ASC
            LIMIT ${idx + 2}
            """
            values.extend((around, around, before_limit, after_limit))

        else:
            query = f"""
            SELECT {columns}
            FROM notes
            WHERE {where_clause}
            ORDER BY id ASC
            LIMIT ${idx}
            """
            values.append(limit)

        return await self._conn.fetch(query, *values, record_class=models.Note)

    @overload
    async def update_note(
        self,
        *,
        note_id: int,
        is_locked: bool | SentinelType = ...,
        is_deleted: bool | SentinelType = ...,
        title: str | SentinelType = ...,
        content: str | SentinelType = ...,
        locked: bool | SentinelType = ...,
        deleted: bool | SentinelType = ...,
        fields: Iterable[models.NoteField] = ...,
    ) -> models.Note: ...

    @overload
    async def update_note(
        self,
        *,
        note_id: int,
        is_locked: bool | SentinelType = ...,
        is_deleted: bool | SentinelType = ...,
        title: str | SentinelType = ...,
        content: str | SentinelType = ...,
        locked: bool | SentinelType = ...,
        deleted: bool | SentinelType = ...,
        fields: SentinelType = ...,
    ) -> None: ...

    async def update_note(
        self,
        *,
        note_id: int,
        is_locked: bool | SentinelType = Empty,
        is_deleted: bool | SentinelType = Empty,
        title: str | SentinelType = Empty,
        content: str | SentinelType = Empty,
        locked: bool | SentinelType = Empty,
        deleted: bool | SentinelType = Empty,
        fields: Iterable[models.NoteField] | SentinelType = Empty,
    ) -> models.Note | None:
        """Update a note."""
        cols: list[str] = []
        values: list[Any] = []

        if not issentinel(locked):
            cols.append("locked")
            values.append(locked)

        if not issentinel(title):
            cols.append("title")
            values.append(title)

        if not issentinel(content):
            cols.append("content")
            values.append(content)

        set_parts = [f"{col} = ${i}" for i, col in enumerate(cols, 1)]

        if deleted is True:
            set_parts.append("deleted_at = NOW()")
        elif deleted is False:
            set_parts.append("deleted_at = NULL")

        if not set_parts:
            raise NoFieldsToUpdateError

        set_parts.append("updated_at = NOW()")

        where_parts = [f"id = ${len(cols) + 1}"]

        if is_locked is False:
            where_parts.append("locked = FALSE")
        elif is_locked is True:
            where_parts.append("locked = TRUE")

        if is_deleted is False:
            where_parts.append("deleted_at IS NULL")
        elif is_deleted is True:
            where_parts.append("deleted_at IS NOT NULL")

        query = f"""
        UPDATE notes
        SET {", ".join(set_parts)}
        WHERE {" AND ".join(where_parts)}
        """
        values.append(note_id)

        if not issentinel(fields):
            query += f" RETURNING {', '.join(fields)}"
            note = await self._conn.fetchrow(query, *values, record_class=models.Note)

            if note is not None:
                return note

            updated = False
        else:
            status = await self._conn.execute(query, *values)
            updated = rows_affected(status)

        if not updated:
            raise exceptions.NoteNotFoundError(note_id=note_id)

        return None
