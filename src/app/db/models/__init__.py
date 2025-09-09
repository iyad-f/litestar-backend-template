"""Models."""

# Incase you're wondering why models is a dir and not a file
# it's cause in larger applications you'd usually split models into separate files
# like models/user.py for user-related stuff etc.
# here it's just a small example, but kept it this way to reflect how it'd look
# in a real app — that said, you can totally use a single big models.py too
# nothing wrong with long files, but splitting by entity is more common in larger applications.

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from app.lib.db import Record
from app.utils.time import utcnow

if TYPE_CHECKING:
    from datetime import datetime

__all__ = (
    "ActiveAccessToken",
    "ActiveAccessTokenField",
    "Note",
    "NoteField",
    "RefreshToken",
    "RefreshTokenField",
    "Role",
    "RoleField",
    "User",
    "UserField",
)


type UserField = Literal[
    "id",
    "name",
    "hashed_password",
    "locked_notes_secret_hash",
    "disabled",
    "updated_at",
    "deleted_at",
]


class User(Record):
    """Represents a user in db."""

    id: int
    name: str
    hashed_password: str
    locked_notes_secret_hash: str
    disabled: bool
    updated_at: datetime
    deleted_at: datetime | None


type RoleField = Literal["id", "name", "slug", "description", "updated_at"]


class Role(Record):
    """Represents a role in db."""

    id: int
    name: str
    slug: str
    description: str
    updated_at: datetime


type NoteField = Literal[
    "id",
    "owner_id",
    "title",
    "content",
    "locked",
    "hashed_password",
    "updated_at",
    "deleted_at",
]


class Note(Record):
    """Represents a note in db."""

    id: int
    owner_id: int
    title: str
    content: str
    locked: bool
    updated_at: datetime
    deleted_at: datetime | None


type RefreshTokenField = Literal[
    "id", "user_id", "token_prefix", "hashed_token", "expires_at", "used"
]


class RefreshToken(Record):
    """Represents a refresh token in db."""

    id: int
    user_id: int
    token_prefix: str
    hashed_token: str
    expires_at: datetime
    used: bool

    @property
    def expires_in(self) -> int:
        """The number of seconds after which the token will expire."""
        return int((self.expires_at - utcnow()).total_seconds())


type ActiveAccessTokenField = Literal["id", "user_id", "jti", "expires_at"]


class ActiveAccessToken(Record):
    """Represents a active access token in the db."""

    id: int
    user_id: int
    jti: str
    expires_at: datetime

    @property
    def expires_in(self) -> int:
        """The number of seconds after which the token will expire."""
        return int((self.expires_at - utcnow()).total_seconds())
