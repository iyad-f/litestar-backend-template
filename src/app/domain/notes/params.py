from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.params import Body, Parameter

if TYPE_CHECKING:
    from typing import Any

__all__ = (
    "After",
    "Around",
    "Before",
    "Deleted",
    "Limit",
    "Locked",
    "NoteID",
    "NoteUpdate",
    "OwnerID",
    "Secret",
)


def NoteCreate() -> Any:
    return Body(
        title="Note Creation Data",
        description="Information required to create a new note.",
    )


def Secret(*, action: str = "access", plural: bool = False) -> Any:
    """Secret param."""
    noun = "notes" if plural else "a locked note"
    return Parameter(
        title="Secret",
        description=f"Secret required to {action} {noun}.",
        header="X-Notes-Secret",
    )


def NoteID(*, action: str) -> Any:
    """Note Id param."""
    return Parameter(
        title="Note Identifier",
        description=f"The unique integer ID of the note to {action}.",
    )


def Locked() -> Any:
    """Locked param."""
    return Parameter(
        title="Locked",
        description="Wether to filter based on note is locked or not",
    )


def Limit() -> Any:
    """Limit param."""
    return Parameter(
        title="Limit",
        description="Maximum number of notes to retrieve in this batch.",
    )


def Before() -> Any:
    """Before param."""
    return Parameter(
        title="Before ID",
        description="Retrieve notes with IDs smaller than this ID.",
    )


def After() -> Any:
    """After param."""
    return Parameter(
        title="After ID",
        description="Retrieve notes with IDs larger than this ID.",
    )


def Around() -> Any:
    """Around param."""
    return Parameter(
        title="Around ID",
        description="Retrieve notes around this ID.",
    )


def NoteUpdate() -> Any:
    """Note update param."""
    return Body(
        title="Note Update Data",
        description="The updated fields for the note.",
    )


def OwnerID() -> Any:
    """Owner id param."""
    return Parameter(
        title="Owner ID",
        description="The unique integer ID of the owner of the notes.",
    )


def Deleted() -> Any:
    """Delete param."""
    return Parameter(title="Deleted", description="Wether the notes are deleted or not.")
