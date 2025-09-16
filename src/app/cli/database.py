import asyncio

import click

from app.config import LITESTAR_CONFIG

from ._common import DB_DIR

__all__ = ("database_group",)


@click.group(name="database")
def database_group() -> None:
    """Group of commands for managing the database."""


@database_group.command()
def init() -> None:
    """Initialize the database by running all the migrations."""

    async def main() -> None:
        migrations_dir = DB_DIR / "migrations"

        async with LITESTAR_CONFIG.asyncpg.get_connection() as conn, conn.transaction():
            for file in sorted(migrations_dir.glob("*.sql")):
                sql = file.read_text("utf-8")
                await conn.execute(sql)

        click.echo("Database has been initialized.")

    asyncio.run(main())
