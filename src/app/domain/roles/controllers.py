from __future__ import annotations

from typing import Annotated

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide

from app.config import APP_CONFIG
from app.domain.users.services import ActiveAccessTokenService
from app.lib.guards import requires_admin
from app.utils.sentinel import issentinel, none_to_sentinel

from . import params, schemas, services

__all__ = ("RoleController",)


class RoleController(Controller):
    """Role Controller."""

    tags = ["Roles"]
    path = f"{APP_CONFIG.base_url}/roles"
    dependencies = {
        "role_service": Provide(services.RoleService, sync_to_thread=False),
        "active_access_token_service": Provide(
            ActiveAccessTokenService, sync_to_thread=False
        ),
    }
    guards = [requires_admin]

    @post()
    async def create_role(
        self,
        role_service: services.RoleService,
        data: Annotated[schemas.RoleCreate, params.RoleCreate()],
    ) -> schemas.Role:
        """Create a role."""
        role = await role_service.create_role(
            **data.to_dict(), fields=("id", "name", "slug", "description")
        )
        return schemas.Role(**role)

    @get(path="/{role_slug:str}")
    async def get_role(
        self,
        role_service: services.RoleService,
        role_slug: Annotated[str, params.RoleSlug(action="retrieve")],
    ) -> schemas.Role:
        """Get a role."""
        role = await role_service.fetch_role(
            slug=role_slug, fields=("id", "name", "slug", "description", "updated_at")
        )
        return schemas.Role(**role)

    @get()
    async def get_roles(
        self,
        role_service: services.RoleService,
        limit: Annotated[int, params.Limit()] = 100,
        before: Annotated[int | None, params.Before()] = None,
        after: Annotated[int | None, params.After()] = None,
        around: Annotated[int | None, params.Around()] = None,
    ) -> list[schemas.Role]:
        """Get roles."""
        roles = await role_service.fetch_roles(
            limit=limit,
            before=none_to_sentinel(before),
            after=none_to_sentinel(after),
            around=none_to_sentinel(around),
            fields=("id", "name", "slug", "description", "updated_at"),
        )
        return [schemas.Role(**r) for r in roles]

    @patch(path="/{role_slug:str}")
    async def update_role(
        self,
        role_service: services.RoleService,
        active_access_token_service: ActiveAccessTokenService,
        role_slug: Annotated[str, params.RoleSlug(action="update")],
        data: Annotated[schemas.RoleUpdate, params.RoleUpdate()],
    ) -> schemas.Role:
        """Update a role."""
        role = await role_service.update_role(
            current_slug=role_slug,
            **data.to_dict(),
            fields=("id", "name", "slug", "description", "updated_at"),
        )

        if not issentinel(data.name):
            await active_access_token_service.blacklist_tokens(role_slug=role_slug)

        return schemas.Role(**role)

    @delete(path="/{role_slug:str}")
    async def delete_role(
        self,
        role_service: services.RoleService,
        active_access_token_service: ActiveAccessTokenService,
        role_slug: Annotated[str, params.RoleSlug(action="delete")],
    ) -> None:
        """Delete a role."""
        await role_service.delete_role(slug=role_slug)
        await active_access_token_service.blacklist_tokens(role_slug=role_slug)
