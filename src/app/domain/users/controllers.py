from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Annotated

from litestar import (
    Controller,
    Response,
    delete,
    get,
    patch,
    post,
    put,
    status_codes,
)
from litestar.di import Provide
from litestar.params import Body, Parameter
from msgspec import UNSET

from app.config import APP_CONFIG
from app.lib.exceptions import NotAuthorizedError
from app.lib.guards import requires_admin
from app.lib.jwt import Token
from app.lib.schemas import Message
from app.middleware.auth import AuthenticatedUser
from app.middleware.rate_limit import RateLimitPolicy
from app.utils.sentinel import none_to_sentinel
from app.utils.time import utcnow

from . import guards, params, schemas, services

if TYPE_CHECKING:
    from typing import Any

    from litestar import Request

__all__ = ("AuthController", "UserController", "UserRoleController")


class TokenResponse(Response[schemas.TokenResponse]):
    def __init__(
        self,
        *,
        content: schemas.TokenResponse,
    ) -> None:
        super().__init__(content=content)

        access_token = content.access_token
        refresh_token = content.refresh_token

        self.set_header(
            key=APP_CONFIG.authorization_header_key,
            value=f"{APP_CONFIG.access_token.type} {access_token}",
        )

        self.set_cookie(
            key=APP_CONFIG.access_token.cookie_name,
            value=access_token,
            httponly=True,
            secure=True,
            max_age=content.expires_in,
        )

        self.set_cookie(
            key=APP_CONFIG.refresh_token.cookie_name,
            value=refresh_token,
            httponly=True,
            secure=True,
            max_age=content.refresh_token_expires_in,
        )


async def revoke_current_session(
    request: Request[Any, Any, Any],
    refresh_token_service: services.RefreshTokenService,
    active_access_token_service: services.ActiveAccessTokenService,
    *,
    delete: bool = False,
) -> Response[Any]:
    acookie = APP_CONFIG.access_token.cookie_name
    rcookie = APP_CONFIG.refresh_token.cookie_name

    access_token = request.cookies.pop(acookie, None)
    refresh_token = request.cookies.pop(rcookie, None)

    if access_token is not None:
        try:
            token = Token.from_encoded(
                encoded_token=access_token,
                secret=APP_CONFIG.access_token.secret,
                algorithm=APP_CONFIG.access_token.algorithm,
                required_claims=["jti", "exp"],
            )
        except NotAuthorizedError:
            pass
        else:
            assert token.jti is not None
            assert token.expires_in is not None
            await active_access_token_service.blacklist_token(
                jti=token.jti, expires_in=token.expires_in
            )

    if refresh_token is not None:
        await refresh_token_service.revoke_token(token=refresh_token)

    if delete:
        response = Response(content=None, status_code=status_codes.HTTP_204_NO_CONTENT)
    else:
        content = Message(message="Successfully logged out.")
        response = Response(content=content, status_code=status_codes.HTTP_200_OK)

    response.delete_cookie(acookie)
    response.delete_cookie(rcookie)

    return response


class AuthController(Controller):
    """Authentication controller."""

    tags = ["Authentication"]
    path = f"{APP_CONFIG.base_url}/auth"
    opt = {"exclude_from_auth": True}
    dependencies = {
        "user_service": Provide(services.UserService, sync_to_thread=False),
        "user_role_service": Provide(services.UserRoleService, sync_to_thread=False),
        "refresh_token_service": Provide(
            services.RefreshTokenService, sync_to_thread=False
        ),
        "active_access_token_service": Provide(
            services.ActiveAccessTokenService, sync_to_thread=False
        ),
    }

    @post(
        path="/signup",
        rate_limits=[
            RateLimitPolicy(capacity=5, refill_rate=1 / 12, priority=0),
            RateLimitPolicy(capacity=100, refill_rate=1 / 864, priority=1),
        ],
    )
    async def signup(
        self,
        user_service: services.UserService,
        user_role_service: services.UserRoleService,
        data: Annotated[schemas.UserSignup, params.UserSignup()],
    ) -> Message:
        """Signup a new user."""
        user = await user_service.create_user(**data.to_dict(), fields=("id",))
        await user_role_service.assign_role(
            user_id=user.id, role_slug=APP_CONFIG.roles.default_role_slug
        )
        return Message(message="successfully signed up.")

    @post(
        path="/login",
        rate_limits=[
            RateLimitPolicy(capacity=10, refill_rate=1 / 6, priority=0),
            RateLimitPolicy(capacity=500, refill_rate=1 / 1728, priority=1),
        ],
    )
    async def login(
        self,
        user_service: services.UserService,
        user_role_service: services.UserRoleService,
        refresh_token_service: services.RefreshTokenService,
        active_access_token_service: services.ActiveAccessTokenService,
        data: Annotated[schemas.UserLogin, params.UserLogin()],
    ) -> TokenResponse:
        """Login a user."""
        user = await user_service.authenticate_user(**data.to_dict())
        return await self._create_token_response(
            user_role_service, refresh_token_service, active_access_token_service, user.id
        )

    @post(
        path="/logout",
        rate_limits=[RateLimitPolicy(capacity=30, refill_rate=1 / 2)],
    )
    async def logout(
        self,
        request: Request[Any, Any, Any],
        refresh_token_service: services.RefreshTokenService,
        active_access_token_service: services.ActiveAccessTokenService,
    ) -> Response[Message]:
        """Logout a user."""
        return await revoke_current_session(
            request, refresh_token_service, active_access_token_service
        )

    @post(
        path="/refresh-token",
        rate_limits=[RateLimitPolicy(capacity=60, refill_rate=1)],
    )
    async def refresh_token(
        self,
        user_role_service: services.UserRoleService,
        refresh_token_service: services.RefreshTokenService,
        active_access_token_service: services.ActiveAccessTokenService,
        data: Annotated[schemas.RefreshToken, params.RefreshToken()],
    ) -> TokenResponse:
        """Refresh token."""
        token = await refresh_token_service.authenticate_token(token=data.refresh_token)
        return await self._create_token_response(
            user_role_service,
            refresh_token_service,
            active_access_token_service,
            token.user_id,
        )

    @staticmethod
    async def _create_token_response(
        user_role_service: services.UserRoleService,
        refresh_token_service: services.RefreshTokenService,
        active_access_token_service: services.ActiveAccessTokenService,
        user_id: int,
    ) -> TokenResponse:
        at_config = APP_CONFIG.access_token
        exp = utcnow() + datetime.timedelta(minutes=at_config.expiry)
        roles = await user_role_service.fetch_roles(user_id=user_id, fields=("slug",))
        access_token_model = Token(
            iss=at_config.iss,
            sub=str(user_id),
            aud=at_config.aud,
            exp=exp,
            roles=[r.slug for r in roles],
        )
        access_token = access_token_model.encode(
            secret=APP_CONFIG.access_token.secret,
            algorithm=APP_CONFIG.access_token.algorithm,
        )

        assert access_token_model.jti is not None
        await active_access_token_service.create_token(
            user_id=user_id, jti=access_token_model.jti, expires_at=exp
        )

        refresh_token = refresh_token_service.generate_token()
        refresh_token_model = await refresh_token_service.create_token(
            token=refresh_token, user_id=user_id, fields=("expires_at",)
        )

        assert refresh_token_model is not None
        assert access_token_model.expires_in is not None

        content = schemas.TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=APP_CONFIG.access_token.type,
            expires_in=access_token_model.expires_in,
            refresh_token_expires_in=refresh_token_model.expires_in,
        )

        return TokenResponse(content=content)


class UserController(Controller):
    """User controller."""

    tags = ["Users"]
    path = f"{APP_CONFIG.base_url}/users"
    dependencies = {
        "user_service": Provide(services.UserService, sync_to_thread=False),
        "active_access_token_service": Provide(
            services.ActiveAccessTokenService, sync_to_thread=False
        ),
        "refresh_token_service": Provide(
            services.RefreshTokenService, sync_to_thread=False
        ),
    }

    @get(
        path="/@me",
        rate_limits=(RateLimitPolicy(capacity=60, refill_rate=1)),
    )
    async def get_me(
        self,
        user_service: services.UserService,
        current_user: AuthenticatedUser,
    ) -> schemas.User:
        """Get current user."""
        user = await user_service.fetch_user(
            user_id=current_user.id,
            is_disabled=False,
            is_deleted=False,
            fields=("id", "name"),
        )
        return schemas.User(id=user.id, name=user.name)

    @patch(
        path="/@me",
        rate_limits=(RateLimitPolicy(capacity=30, refill_rate=1 / 2)),
    )
    async def update_me(
        self,
        user_service: services.UserService,
        active_access_token_service: services.ActiveAccessTokenService,
        current_user: AuthenticatedUser,
        data: Annotated[schemas.UserUpdate, params.UserUpdate()],
    ) -> schemas.User:
        """Update current user."""
        user = await user_service.update_user(
            user_id=current_user.id, **data.to_dict(), fields=("id", "name")
        )

        if data.password is not UNSET:
            await active_access_token_service.blacklist_tokens(user_id=current_user.id)

        return schemas.User(**user)

    @delete(
        path="/@me",
        rate_limits=(RateLimitPolicy(capacity=10, refill_rate=1 / 6)),
    )
    async def delete_me(
        self,
        user_service: services.UserService,
        current_user: AuthenticatedUser,
        request: Request[Any, Any, Any],
        active_access_token_service: services.ActiveAccessTokenService,
        refresh_token_service: services.RefreshTokenService,
    ) -> None:
        """Delete the current user."""
        await user_service.update_user(user_id=current_user.id, deleted=True)
        await revoke_current_session(
            request, refresh_token_service, active_access_token_service, delete=True
        )

    @post(
        dependencies={
            "user_role_service": Provide(services.UserRoleService, sync_to_thread=False),
        },
        guards=(requires_admin,),
    )
    async def create_user(
        self,
        user_service: services.UserService,
        user_role_service: services.UserRoleService,
        data: Annotated[schemas.UserCreate, params.UserCreate()],
    ) -> Message:
        """Create a new user."""
        user = await user_service.create_user(**data.to_dict(), fields=("id",))
        await user_role_service.assign_role(
            user_id=user.id, role_slug=APP_CONFIG.roles.default_role_slug
        )
        return Message(message="successfully created a new user.")

    @get(path="/{user_id:int}", guards=(requires_admin,))
    async def get_user(
        self,
        user_service: services.UserService,
        user_id: Annotated[int, params.UserID()],
    ) -> schemas.User:
        """Get a user."""
        user = await user_service.fetch_user(
            user_id=user_id, fields=("id", "name", "disabled", "updated_at", "deleted_at")
        )
        return schemas.User(
            id=user.id,
            name=user.name,
            disabled=user.disabled,
            updated_at=user.updated_at,
            deleted_at=user.deleted_at,
        )

    @get(cache=30, guards=(requires_admin,))
    async def get_users(
        self,
        user_service: services.UserService,
        limit: Annotated[int, params.Limit()] = 100,
        before: Annotated[int | None, params.Before()] = None,
        after: Annotated[int | None, params.After()] = None,
        around: Annotated[int | None, params.Around()] = None,
    ) -> list[schemas.User]:
        """Get users."""
        users = await user_service.fetch_users(
            limit=limit,
            before=none_to_sentinel(before),
            after=none_to_sentinel(after),
            around=none_to_sentinel(around),
            fields=("id", "name", "disabled", "updated_at", "deleted_at"),
        )
        return [schemas.User(**u) for u in users]

    @patch(path="/{user_id:int}", guards=(requires_admin,))
    async def update_user(
        self,
        user_service: services.UserService,
        user_id: Annotated[
            int,
            Parameter(
                title="User Identifier",
                description="The unique integer ID of the user to update.",
            ),
        ],
        data: Annotated[
            schemas.UserUpdate,
            Body(
                title="User Update Data",
                description="The updated fields for the user.",
            ),
        ],
    ) -> schemas.User:
        """Update a user."""
        user = await user_service.update_user(
            user_id=user_id,
            **data.to_dict(),
            fields=("id", "name", "disabled", "updated_at", "deleted_at"),
        )
        return schemas.User(**user)

    @delete(path="/{user_id:int}", guards=(requires_admin,))
    async def delete_user(
        self,
        user_service: services.UserService,
        active_access_token_service: services.ActiveAccessTokenService,
        refresh_token_service: services.RefreshTokenService,
        user_id: Annotated[int, params.UserID()],
    ) -> None:
        """Delete a note of the current user."""
        await user_service.update_user(user_id=user_id, deleted=True)
        await active_access_token_service.blacklist_tokens(user_id=user_id)
        await refresh_token_service.revoke_tokens(user_id=user_id)


class UserRoleController(Controller):
    """UserRoleController."""

    tags = ["User Roles"]
    path = f"{APP_CONFIG.base_url}/users" + "/{user_id:int}/roles/{role_slug:str}"
    dependencies = {
        "user_role_service": Provide(services.UserRoleService, sync_to_thread=False),
        "active_access_token_service": Provide(
            services.ActiveAccessTokenService, sync_to_thread=False
        ),
    }
    guards = (requires_admin, guards.forbid_admin_role)

    @put()
    async def assign_role(
        self,
        user_role_service: services.UserRoleService,
        active_access_token_service: services.ActiveAccessTokenService,
        user_id: Annotated[int, params.UserID()],
        role_slug: Annotated[str, params.RoleSlug()],
    ) -> Message:
        """Assign a role to a user."""
        await user_role_service.assign_role(user_id=user_id, role_slug=role_slug)
        await active_access_token_service.blacklist_tokens(user_id=user_id)
        return Message(
            message=f"Successfully assigned role '{role_slug}' to user with id '{user_id}'."
        )

    @delete()
    async def remove_role(
        self,
        user_role_service: services.UserRoleService,
        active_access_token_service: services.ActiveAccessTokenService,
        user_id: Annotated[int, params.UserID()],
        role_slug: Annotated[str, params.RoleSlug()],
    ) -> None:
        """Remove a role from a user."""
        await user_role_service.remove_role(user_id=user_id, role_slug=role_slug)
        await active_access_token_service.blacklist_tokens(user_id=user_id)
