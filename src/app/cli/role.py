from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import click
from litestar.serialization import decode_json

from app.config import LITESTAR_CONFIG
from app.domain.roles.services import RoleService

from ._common import DB_DIR

if TYPE_CHECKING:
    from typing import TypedDict

    class Role(TypedDict):
        name: str
        description: str


__all__ = ("role_group",)


@click.group(name="role", short_help="Manage application roles.")
def role_group() -> None:
    """Group of commands for managing application roles."""


@role_group.command()
def init() -> None:
    """Create roles neccessary for the application."""

    async def main() -> None:
        fixture_path = DB_DIR / "fixtures" / "role.json"
        roles: list[Role] = decode_json(fixture_path.read_bytes())

        async with LITESTAR_CONFIG.asyncpg.get_connection() as conn:
            role_service = RoleService(conn)  # pyright: ignore[reportArgumentType]
            for role in roles:
                await role_service.create_role(**role)

        click.echo("Created neccessary roles.")

    asyncio.run(main())
