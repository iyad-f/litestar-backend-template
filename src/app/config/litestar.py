from __future__ import annotations

import logging
import logging.handlers
import os
import pathlib
import platform
import sys
from typing import TYPE_CHECKING

from litestar.config.allowed_hosts import AllowedHostsConfig
from litestar.config.compression import CompressionConfig
from litestar.config.cors import CORSConfig
from litestar.config.csrf import CSRFConfig
from litestar.config.response_cache import ResponseCacheConfig, default_cache_key_builder
from litestar.logging.config import LoggingConfig
from litestar.middleware.logging import LoggingMiddlewareConfig
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import (
    JsonRenderPlugin,
    RapidocRenderPlugin,
    RedocRenderPlugin,
    ScalarRenderPlugin,
    StoplightRenderPlugin,
    SwaggerRenderPlugin,
    YamlRenderPlugin,
)
from litestar.openapi.spec import Contact, License
from litestar_asyncpg import AsyncpgConfig, PoolConfig
from litestar_saq import CronJob, QueueConfig, SAQConfig
from msgspec import field

from app import __version__ as app_version
from app.lib.db import Record
from app.lib.schemas import Struct

from .app import APP_CONFIG

if TYPE_CHECKING:
    from typing import Any, Final

    from litestar import Request

__all__ = ("LITESTAR_CONFIG",)


IS_NOT_WINDOWS: Final = platform.system() != "Windows"


def cache_key_builder(request: Request[Any, Any, Any]) -> str:
    return f"{APP_CONFIG.slug}:{default_cache_key_builder(request)}"


# Credit: https://github.com/Rapptz/discord.py/blob/master/discord/utils.py
def is_docker() -> bool:
    cgroup_path = pathlib.Path("/proc/self/cgroup")
    dockerenv_path = pathlib.Path("/.dockerenv")
    return dockerenv_path.exists() or (
        cgroup_path.is_file() and any("docker" in line for line in cgroup_path.open())
    )


def stream_supports_colour(stream: Any) -> bool:
    is_a_tty = hasattr(stream, "isatty") and stream.isatty()

    # Pycharm and Vscode support colour in their inbuilt editors
    if "PYCHARM_HOSTED" in os.environ or os.environ.get("TERM_PROGRAM") == "vscode":
        return is_a_tty

    if sys.platform != "win32":
        # Docker does not consistently have a tty attached to it
        return is_a_tty or is_docker()

    # ANSICON checks for things like ConEmu
    # WT_SESSION checks if this is Windows Terminal
    return is_a_tty and ("ANSICON" in os.environ or "WT_SESSION" in os.environ)


class ColourFormatter(logging.Formatter):
    _LEVEL_COLOURS = [
        (logging.DEBUG, "\x1b[40;1m"),
        (logging.INFO, "\x1b[34;1m"),
        (logging.WARNING, "\x1b[33;1m"),
        (logging.ERROR, "\x1b[31m"),
        (logging.CRITICAL, "\x1b[41m"),
    ]

    _FORMATS = {
        level: logging.Formatter(
            f"\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-8s\x1b[0m \x1b[35m%(name)s\x1b[0m %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        for level, colour in _LEVEL_COLOURS
    }

    def format(self, record: logging.LogRecord) -> str:
        formatter = self._FORMATS.get(record.levelno)
        if formatter is None:
            formatter = self._FORMATS[logging.DEBUG]

        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f"\x1b[31m{text}\x1b[0m"

        output = formatter.format(record)

        record.exc_text = None
        return output


def get_logging_config() -> LoggingConfig:
    logging_path: pathlib.Path = pathlib.Path("./logs/")
    logging_path.mkdir(exist_ok=True)
    formatter = (
        "colour" if stream_supports_colour(logging.StreamHandler().stream) else "standard"
    )

    return LoggingConfig(
        formatters={
            "standard": {
                "format": "[{asctime}] [{levelname}] {name}: {message}",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "style": "{",
            },
            "colour": {
                "()": ColourFormatter,
            },
        },
        handlers={
            "file": {
                "class": logging.handlers.RotatingFileHandler,
                "filename": logging_path / "litestar-backend-template.log",
                "mode": "w",
                "maxBytes": 32 * 1024 * 1024,
                "backupCount": 5,
                "encoding": "utf-8",
                "formatter": "standard",
            },
            "stream": {
                "class": logging.StreamHandler,
                "formatter": formatter,
            },
        },
        loggers={
            "litestar": {
                "propagate": False,
                "level": logging.getLevelName(APP_CONFIG.logging.level),
                "handlers": ["stream", "file"],
            },
            "_granian": {
                "propagate": False,
                "level": APP_CONFIG.logging.asgi_error_level,
                "handlers": ["stream"],
            },
            "granian.server": {
                "propagate": False,
                "level": APP_CONFIG.logging.asgi_error_level,
                "handlers": ["stream"],
            },
            "granian.access": {
                "propagate": False,
                "level": APP_CONFIG.logging.asgi_access_level,
                "handlers": ["stream"],
            },
        },
        root={
            "level": logging.getLevelName(APP_CONFIG.logging.level),
            "handlers": ["stream", "file"],
        },
        log_exceptions="always",
    )


class Config(Struct):
    allowed_hosts: AllowedHostsConfig = field(
        default_factory=lambda: AllowedHostsConfig(**APP_CONFIG.allowed_hosts.to_dict())
    )

    asyncpg: AsyncpgConfig = field(
        default_factory=lambda: AsyncpgConfig(
            pool_config=PoolConfig(
                dsn=APP_CONFIG.db.dsn,
                connect_kwargs={"command_timeout": APP_CONFIG.db.pool_command_timeout},
                record_class=Record,
            ),
            pool_app_state_key=APP_CONFIG.db.pool_app_state_key,
            pool_dependency_key=APP_CONFIG.db.pool_dependency_key,
            connection_dependency_key=APP_CONFIG.db.connection_dependency_key,
        )
    )

    cors: CORSConfig = field(
        default_factory=lambda: CORSConfig(**APP_CONFIG.cors.to_dict())
    )

    csrf: CSRFConfig = field(
        default_factory=lambda: CSRFConfig(
            secret=APP_CONFIG.csrf.secret, **APP_CONFIG.csrf.to_dict()
        )
    )

    response_cache: ResponseCacheConfig = field(
        default_factory=lambda: ResponseCacheConfig(
            **APP_CONFIG.response_cache.to_dict(), key_builder=cache_key_builder
        )
    )

    compression: CompressionConfig = field(
        default_factory=lambda: CompressionConfig(**APP_CONFIG.compression.to_dict())
    )

    # Windows doesn't support the fork multiprocessing method and only supports spawn
    # and hence evrything needs to be picklable, which is not the case, so we only set
    # separate processes and server_lifespan to True for os's other than windows, you
    # can try setting it to True for windows and see the errors for yourself.
    saq: SAQConfig = field(
        default_factory=lambda: SAQConfig(
            **APP_CONFIG.saq.to_dict(),
            use_server_lifespan=IS_NOT_WINDOWS,
            queue_configs=[
                QueueConfig(
                    dsn=APP_CONFIG.redis.url,
                    name="database-tasks",
                    tasks=[
                        "app.domain.users.tasks.remove_invalid_refresh_tokens",
                        "app.domain.users.tasks.remove_expired_access_tokens",
                    ],
                    scheduled_tasks=[
                        CronJob(
                            function="app.domain.users.tasks.remove_invalid_refresh_tokens",
                            cron="0 0 * * *",
                            timeout=500,
                        ),
                        CronJob(
                            function="app.domain.users.tasks.remove_expired_access_tokens",
                            cron="0 * * * *",
                            timeout=500,
                        ),
                    ],
                    separate_process=IS_NOT_WINDOWS,
                )
            ],
        )
    )

    openapi: OpenAPIConfig = field(
        default_factory=lambda: OpenAPIConfig(
            title=APP_CONFIG.name,
            version=app_version,
            contact=Contact(name="Iyad", url="https://github.com/iyad-f"),
            description="A backend template built with Litestar",
            license=License(
                name="Apache License 2.0",
                identifier="Apache-2.0",
                url="http://www.apache.org/licenses/LICENSE-2.0",
            ),
            use_handler_docstrings=True,
            # The first plugin in the list with path="/" will be rendered at /docs directly.
            # All plugins are also accessible at /docs/<plugin_name> (e.g., /docs/swagger,
            # /docs/redoc). If no plugin has path="/", the first plugin in the list will be
            # rendered at /docs.
            render_plugins=[
                ScalarRenderPlugin(),
                JsonRenderPlugin(),
                YamlRenderPlugin(),
                RapidocRenderPlugin(),
                RedocRenderPlugin(),
                StoplightRenderPlugin(),
                SwaggerRenderPlugin(),
            ],
            path="/docs",
        )
    )

    logging: LoggingConfig = field(default_factory=get_logging_config)

    logging_middleware: LoggingMiddlewareConfig = field(
        default_factory=lambda: LoggingMiddlewareConfig(
            **APP_CONFIG.logging.middleware.to_dict()
        )
    )


LITESTAR_CONFIG: Final = Config()
"""Configuration for litestar."""
