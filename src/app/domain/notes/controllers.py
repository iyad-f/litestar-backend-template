from __future__ import annotations

from typing import Annotated

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from msgspec import UNSET

from app.config import APP_CONFIG
from app.domain.users.services import UserService
from app.lib.exceptions import PermissionDeniedError
from app.lib.guards import requires_admin
from app.middleware.auth import AuthenticatedUser
from app.middleware.rate_limit import RateLimitPolicy
from app.utils.sentinel import none_to_sentinel

from . import exceptions, params, schemas, services

__all__ = ("NoteController", "UserNoteController")


class UserNoteController(Controller):
    """User Note Controller."""

    tags = ["User Notes"]
    path = f"{APP_CONFIG.base_url}/users"
    dependencies = {
        "note_service": Provide(services.NoteService, sync_to_thread=False),
        "user_service": Provide(UserService, sync_to_thread=False),
    }

    @post(
        path="/@me/notes",
        rate_limits=[
            RateLimitPolicy(capacity=10, refill_rate=1 / 10, priority=0),  # 10/minute
            RateLimitPolicy(capacity=100, refill_rate=1 / 20, priority=1),  # 1000/day
        ],
    )
    async def create_my_note(
        self,
        note_service: services.NoteService,
        user_service: UserService,
        current_user: AuthenticatedUser,
        data: Annotated[schemas.NoteCreate, params.NoteCreate()],
        secret: Annotated[str | None, params.Secret(action="create")] = None,
    ) -> schemas.Note:
        """Create a new note for the current user."""
        if data.locked:
            if secret is None:
                raise exceptions.MissingNoteSecretError(action="create")

            await user_service.verify_notes_secret(user_id=current_user.id, secret=secret)

        note = await note_service.create_note(
            owner_id=current_user.id,
            **data.to_dict(),
            fields=("id", "owner_id", "title", "content", "locked"),
        )
        return schemas.Note(**note)

    @get(
        path="/@me/{note_id:int}",
        rate_limits=(
            [
                RateLimitPolicy(capacity=60, refill_rate=1, priority=0),  # 60/minute
                RateLimitPolicy(capacity=10000, refill_rate=1 / 8, priority=1),  # 10k/day
            ]
        ),
    )
    async def get_my_note(
        self,
        note_service: services.NoteService,
        user_service: UserService,
        current_user: AuthenticatedUser,
        note_id: Annotated[int, params.NoteID(action="retrieve")],
        secret: Annotated[str | None, params.Secret()] = None,
    ) -> schemas.Note:
        """Get a note of the current user."""
        note = await note_service.fetch_note(
            note_id=note_id,
            is_deleted=False,
            fields=("id", "owner_id", "title", "content", "locked"),
        )

        if note.locked:
            if secret is None:
                raise exceptions.MissingNoteSecretError

            await user_service.verify_notes_secret(user_id=current_user.id, secret=secret)

        return schemas.Note(**note)

    @get(
        path="/@me/notes",
        cache=30,
        rate_limits=(
            [
                RateLimitPolicy(capacity=60, refill_rate=1)  # 60/minute
            ]
        ),
    )
    async def get_my_notes(
        self,
        note_service: services.NoteService,
        user_service: UserService,
        current_user: AuthenticatedUser,
        locked: Annotated[bool | None, params.Locked()] = None,
        secret: Annotated[str | None, params.Secret(plural=True)] = None,
        limit: Annotated[int, params.Limit()] = 100,
        before: Annotated[int | None, params.Before()] = None,
        after: Annotated[int | None, params.After()] = None,
        around: Annotated[int | None, params.Around()] = None,
    ) -> list[schemas.Note]:
        """Get notes of the current user."""
        # The secret is required when the user requests either all notes or only the locked ones.
        if locked is None or locked:
            if secret is None:
                raise exceptions.MissingNoteSecretError(plural=True)

            await user_service.verify_notes_secret(user_id=current_user.id, secret=secret)

        notes = await note_service.fetch_notes(
            owner_id=current_user.id,
            is_locked=none_to_sentinel(locked),
            is_deleted=False,
            limit=limit,
            before=none_to_sentinel(before),
            after=none_to_sentinel(after),
            around=none_to_sentinel(around),
            fields=("id", "owner_id", "title", "content", "locked"),
        )
        return [schemas.Note(**n) for n in notes]

    @patch(
        path="/@me/notes/{note_id:int}",
        rate_limits=[
            RateLimitPolicy(capacity=30, refill_rate=1 / 2)  # 30/minute
        ],
    )
    async def update_my_note(
        self,
        user_service: UserService,
        note_service: services.NoteService,
        current_user: AuthenticatedUser,
        note_id: Annotated[int, params.NoteID(action="update")],
        data: Annotated[schemas.NoteUpdate, params.NoteUpdate()],
        secret: Annotated[str | None, params.Secret(action="update")] = None,
    ) -> schemas.Note:
        """Update a note of the current user."""
        verified = False
        note = await note_service.fetch_note(note_id=note_id, fields=("locked",))

        if note.locked:
            if secret is None:
                raise exceptions.MissingNoteSecretError(action="update")

            await user_service.verify_notes_secret(user_id=current_user.id, secret=secret)
            verified = True

        if data.locked is not UNSET:
            if secret is None:
                detail = "Secret must be provided to update the locked field of a note."
                raise PermissionDeniedError(detail=detail)

            if not verified:
                await user_service.verify_notes_secret(
                    user_id=current_user.id, secret=secret
                )

        note = await note_service.update_note(
            note_id=note_id,
            is_deleted=False,
            **data.to_dict(),
            fields=("id", "owner_id", "title", "content", "locked"),
        )
        return schemas.Note(**note)

    @delete(
        path="/@me/notes/{note_id:int}",
        rate_limits=[
            RateLimitPolicy(capacity=10, refill_rate=1 / 6, priority=0)  # 10/minute
        ],
    )
    async def delete_my_note(
        self,
        note_service: services.NoteService,
        user_service: UserService,
        current_user: AuthenticatedUser,
        note_id: Annotated[int, params.NoteID(action="delete")],
        secret: Annotated[str | None, params.Secret(action="delete")] = None,
    ) -> None:
        """Delete a note of the current user."""
        note = await note_service.fetch_note(note_id=note_id, fields=("locked",))

        if note.locked:
            if secret is None:
                raise exceptions.MissingNoteSecretError(action="delete")

            await user_service.verify_notes_secret(user_id=current_user.id, secret=secret)

        await note_service.update_note(note_id=note_id, deleted=True)


class NoteController(Controller):
    """Note Controller."""

    tags = ["Notes"]
    path = f"{APP_CONFIG.base_url}/notes"
    dependencies = {"note_service": Provide(services.NoteService, sync_to_thread=False)}
    guards = [requires_admin]

    @get(path="/{note_id:int}")
    async def get_note(
        self,
        note_service: services.NoteService,
        note_id: Annotated[int, params.NoteID(action="retrieve")],
    ) -> schemas.Note:
        """Get a note."""
        note = await note_service.fetch_note(
            note_id=note_id,
            fields=(
                "id",
                "owner_id",
                "title",
                "content",
                "locked",
                "updated_at",
                "deleted_at",
            ),
        )
        return schemas.Note(**note)

    @get(cache=30)
    async def get_notes(
        self,
        note_service: services.NoteService,
        owner_id: Annotated[int | None, params.OwnerID()] = None,
        locked: Annotated[bool | None, params.Locked()] = None,
        deleted: Annotated[bool | None, params.Deleted()] = None,
        limit: Annotated[int, params.Limit()] = 100,
        before: Annotated[int | None, params.Before()] = None,
        after: Annotated[int | None, params.After()] = None,
        around: Annotated[int | None, params.Around()] = None,
    ) -> list[schemas.Note]:
        """Get notes of the current user."""
        notes = await note_service.fetch_notes(
            owner_id=none_to_sentinel(owner_id),
            is_locked=none_to_sentinel(locked),
            is_deleted=none_to_sentinel(deleted),
            limit=limit,
            before=none_to_sentinel(before),
            after=none_to_sentinel(after),
            around=none_to_sentinel(around),
            fields=(
                "id",
                "owner_id",
                "title",
                "content",
                "locked",
                "updated_at",
                "deleted_at",
            ),
        )
        return [schemas.Note(**n) for n in notes]

    @patch(path="/{note_id:int}")
    async def update_note(
        self,
        note_service: services.NoteService,
        note_id: Annotated[int, params.NoteID(action="update")],
        data: Annotated[schemas.NoteUpdate, params.NoteUpdate()],
    ) -> schemas.Note:
        """Update a note of the current user."""
        note = await note_service.update_note(
            note_id=note_id,
            **data.to_dict(),
            fields=(
                "id",
                "owner_id",
                "title",
                "content",
                "locked",
                "updated_at",
                "deleted_at",
            ),
        )
        return schemas.Note(**note)

    @delete(path="/{note_id:int}")
    async def delete_note(
        self,
        note_service: services.NoteService,
        note_id: Annotated[int, params.NoteID(action="delete")],
    ) -> None:
        """Delete a note of the current user."""
        await note_service.update_note(note_id=note_id, deleted=True)
