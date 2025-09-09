from __future__ import annotations

from app.lib.exceptions import NotFoundError, PermissionDeniedError

__all__ = ("MissingNoteSecretError", "NoteNotFoundError")


class NoteNotFoundError(NotFoundError):
    """Raised when a note does not exist."""

    def __init__(self, note_id: int) -> None:
        msg = f"Note with id {note_id} does not exist."
        super().__init__(msg)


class MissingNoteSecretError(PermissionDeniedError):
    """Raised when locked notes are accessed without providing a secret."""

    def __init__(self, *, action: str = "access", plural: bool = False) -> None:
        noun = "notes" if plural else "a locked note"
        super().__init__(f"Secret is required to {action} {noun}.")
