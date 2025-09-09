import asyncio

import click

from app.config import APP_CONFIG, LITESTAR_CONFIG
from app.domain.users.services import UserRoleService, UserService

__all__ = ("user_group",)


@click.group(name="user")
def user_group() -> None:
    """Manage application users."""


@user_group.command()
@click.option("--name", required=True, help="Name of the new user.")
@click.option("--password", help="Password for the new user.")
@click.option("--locked-notes-secret", help="Secret for locked notes.")
@click.option(
    "--admin",
    is_flag=True,
    default=False,
    help="Set this flag to create the user as an admin.",
)
def create(name: str, password: str, locked_notes_secret: str, *, admin: bool) -> None:
    """Create a new user."""

    async def main() -> None:
        async with LITESTAR_CONFIG.asyncpg.get_connection() as conn, conn.transaction():
            user_service = UserService(conn)  # pyright: ignore[reportArgumentType]
            user_role_service = UserRoleService(conn)  # pyright: ignore[reportArgumentType]

            user = await user_service.create_user(
                name=name,
                password=password,
                locked_notes_secret=locked_notes_secret,
                fields=("id",),
            )

            role_slugs: list[str] = [APP_CONFIG.roles.default_role_slug]
            if admin:
                role_slugs.append(APP_CONFIG.roles.admin_role_slug)

            await user_role_service.assign_roles(user_id=user.id, role_slugs=role_slugs)
            click.echo("Successfully created the user.")

    asyncio.run(main())


@user_group.command()
@click.option("--name", help="Name of the user to make admin.")
def promote_to_admin(name: str) -> None:
    """Promote a user to admin."""

    async def main() -> None:
        async with LITESTAR_CONFIG.asyncpg.get_connection() as conn:
            user_service = UserService(conn)  # pyright: ignore[reportArgumentType]
            user_role_service = UserRoleService(conn)  # pyright: ignore[reportArgumentType]

            user = await user_service.fetch_user(name=name, fields=("id",))
            await user_role_service.assign_role(
                user_id=user.id, role_slug=APP_CONFIG.roles.admin_role_slug
            )
            click.echo(f"Successfully made {name} an admin.")

    asyncio.run(main())


@user_group.command()
def assign_default_role() -> None:
    """Assign the default role to all active users."""

    async def main() -> None:
        async with LITESTAR_CONFIG.asyncpg.get_connection() as conn, conn.transaction():
            user_service = UserService(conn)  # pyright: ignore[reportArgumentType]
            users = await user_service.fetch_users(
                is_disabled=False, is_deleted=False, fields=("id",)
            )
            if not users:
                click.echo("The application has no users yet.")
                return

            user_role_service = UserRoleService(conn)  # pyright: ignore[reportArgumentType]
            await user_role_service.assign_role_to_many(
                user_ids=[u.id for u in users],
                role_slug=APP_CONFIG.roles.default_role_slug,
            )

        click.echo("Assigned default role to all active users.")

    asyncio.run(main())
