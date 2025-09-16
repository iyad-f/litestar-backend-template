from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.di import Provide
from litestar.exceptions import HTTPException
from litestar.middleware import DefineMiddleware
from litestar.plugins import InitPlugin as LitestarInitPlugin
from litestar.stores.registry import StoreRegistry
from litestar_asyncpg import AsyncpgPlugin
from litestar_granian import GranianPlugin
from litestar_saq import SAQPlugin

from app.cli import database_group, role_group, user_group
from app.config import APP_CONFIG, LITESTAR_CONFIG
from app.domain.notes.controllers import NoteController, UserNoteController
from app.domain.roles.controllers import RoleController
from app.domain.system.controllers import SystemController
from app.domain.users.controllers import (
    AuthController,
    UserController,
    UserRoleController,
)
from app.lib.dependencies import provide_current_user
from app.lib.exceptions import (
    HTTPError,
    http_error_to_http_response,
    litestar_http_exc_to_http_response,
)
from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware, RateLimitPolicy

from .stores import RedisStore

if TYPE_CHECKING:
    from click import Group
    from litestar.config.app import AppConfig

__all__ = ("InitPlugin",)


# This could be integrated into the init plugin, but I separated it
# for two reasons
# 1. To showcase the use of another custom plugin.
# 2. to keep all the middleware related stuff in this plugin.
class MiddlewarePlugin(LitestarInitPlugin):
    """Plugin to register middlewares.

    This plugin is responsible for adding all the middlewares to the application.
    """

    __slots__ = ()

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Add middlewares to the application.

        Parameters
        ----------
        app_config : AppConfig
            The application configuration.

        Returns
        -------
        AppConfig
            The updated configuration.
        """
        auth_middleware = DefineMiddleware(
            AuthMiddleware,
            exclude=["^/docs", "^/saq"],
        )
        rlm_config = APP_CONFIG.rate_limit_middleware
        rate_limit_middleware = RateLimitMiddleware(
            encryption_key=rlm_config.encryption_key,
            encryption_nonce=rlm_config.encryption_nonce,
            **rlm_config.to_dict(),
            authorization_header_key=APP_CONFIG.authorization_header_key,
            global_limits=[
                RateLimitPolicy(capacity=50, refill_rate=50, set_headers=False),
            ],
        )

        app_config.middleware.insert(0, auth_middleware)
        app_config.middleware.insert(1, rate_limit_middleware)
        app_config.middleware.append(LITESTAR_CONFIG.logging_middleware.middleware)

        return app_config


class InitPlugin(LitestarInitPlugin):
    """Application configuration and CLI initialization plugin.

    This plugin is responsible for configuring the Litestar application
    at startup and extending the CLI with project-specific commands.
    """

    __slots__ = ()

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Configure the application during initialization.

        Parameters
        ----------
        app_config : AppConfig
            The application configuration.

        Returns
        -------
        AppConfig
            The updated configuration.
        """
        app_config.debug = APP_CONFIG.debug

        app_config.allowed_hosts = LITESTAR_CONFIG.allowed_hosts

        app_config.cors_config = LITESTAR_CONFIG.cors

        app_config.csrf_config = LITESTAR_CONFIG.csrf

        app_config.openapi_config = LITESTAR_CONFIG.openapi

        app_config.response_cache_config = LITESTAR_CONFIG.response_cache

        app_config.compression_config = LITESTAR_CONFIG.compression

        app_config.logging_config = LITESTAR_CONFIG.logging

        redis = APP_CONFIG.redis.create_client()
        app_config.stores = StoreRegistry(
            default_factory=lambda name: RedisStore(
                redis, namespace=f"{APP_CONFIG.slug}:{name}"
            )
        )
        # redis.aclose is not in the stubs
        app_config.on_shutdown.append(redis.aclose)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownArgumentType, reportUnknownMemberType]

        app_config.plugins.extend(
            (
                MiddlewarePlugin(),
                AsyncpgPlugin(LITESTAR_CONFIG.asyncpg),
                SAQPlugin(LITESTAR_CONFIG.saq),
                GranianPlugin(),
            )
        )

        app_config.route_handlers.extend(
            (
                SystemController,
                AuthController,
                UserController,
                RoleController,
                UserRoleController,
                NoteController,
                UserNoteController,
            )
        )

        app_config.exception_handlers = {
            HTTPError: http_error_to_http_response,
            HTTPException: litestar_http_exc_to_http_response,
        }

        app_config.dependencies = {
            "current_user": Provide(provide_current_user, sync_to_thread=False)
        }

        return app_config

    def on_cli_init(self, group: Group) -> None:
        """Initialize the CLI with project-specific commands.

        Parameters
        ----------
        group : Group
            The Click command group representing the root of the CLI.
        """
        group.add_command(database_group)
        group.add_command(role_group)
        group.add_command(user_group)
