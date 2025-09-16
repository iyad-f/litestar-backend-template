from __future__ import annotations

import os
import pathlib
from typing import TYPE_CHECKING, Literal

from litestar.data_extractors import RequestExtractorField, ResponseExtractorField
from msgspec import field, toml
from redis.asyncio import Redis

from app.lib.config import Struct
from app.utils.text import slugify

if TYPE_CHECKING:
    from typing import Final, Self

__all__ = ("APP_CONFIG",)

type HttpMethod = Literal[
    "GET", "POST", "DELETE", "PATCH", "PUT", "HEAD", "TRACE", "OPTIONS"
]
type CORSAllowedMethod = Literal[
    "GET", "POST", "DELETE", "PATCH", "PUT", "HEAD", "TRACE", "OPTIONS", "*"
]


def get_secret(filename: str) -> str:
    path = pathlib.Path(f"secrets/{filename}").resolve()

    if not path.exists():
        msg = f"Secret file not found at path: {str(path)!r}"
        raise ValueError(msg)

    return path.read_text("utf-8").strip()


class DatabaseConfig(Struct):
    host: str
    user: str
    db: str
    pool_command_timeout: int = field(default=30)
    pool_app_state_key: str = field(default="db_pool")
    pool_dependency_key: str = field(default="db_pool")
    connection_dependency_key: str = field(default="db_connection")

    @property
    def dsn(self) -> str:
        password = get_secret("postgres_password.txt")
        return f"postgres://{self.user}:{password}@{self.host}/{self.db}"


class ServerConfig(Struct):
    host: str = field(
        default_factory=lambda: "0.0.0.0" if os.getenv("IN_DOCKER") else "127.0.0.1"  # noqa: S104
    )
    port: int = field(default=8000)


class LoggingMiddlewareConfig(Struct):
    exclude: str = field(default=r"\A(?!x)x")
    exclude_opt_key: str = field(default="exclude_from_logging_middleware")
    include_compressed_body: bool = field(default=False)
    logger_name: str = field(default="litestar")
    request_cookies_to_obfuscate: set[str] = field(
        default_factory=lambda: {"session", "csrftoken"}
    )
    request_headers_to_obfuscate: set[str] = field(
        default_factory=lambda: {"Authorization", "X-API-KEY", "X-CSRF-TOKEN"}
    )
    response_cookies_to_obfuscate: set[str] = field(
        default_factory=lambda: {"session", "csrftoken"}
    )
    response_headers_to_obfuscate: set[str] = field(
        default_factory=lambda: {"Authorization", "X-API-KEY", "X-CSRF-TOKEN"}
    )
    request_log_message: str = field(default="HTTP Request")
    response_log_message: str = field(default="HTTP Response")
    request_log_fields: list[RequestExtractorField] = field(
        default_factory=lambda: [
            "path",
            "method",
            "query",
            "path_params",
        ]
    )
    response_log_fields: list[ResponseExtractorField] = field(
        default_factory=lambda: ["status_code"]
    )


class LoggingConfig(Struct):
    level: int = field(default=10)
    asgi_access_level: int = field(default=30)
    asgi_error_level: int = field(default=20)
    middleware: LoggingMiddlewareConfig = field(default_factory=LoggingMiddlewareConfig)


class CORSConfig(Struct):
    allow_origins: list[str] = field(default_factory=lambda: ["*"])
    allow_methods: list[CORSAllowedMethod] = field(default_factory=lambda: ["*"])
    allow_headers: list[str] = field(default_factory=lambda: ["*"])
    allow_credentials: bool = field(default=False)
    allow_origin_regex: str | None = field(default=None)
    expose_headers: list[str] = field(default_factory=list[str])
    max_age: int = field(default=600)


class CSRFConfig(Struct):
    cookie_name: str = field(default="csrftoken")
    cookie_path: str = field(default="/")
    header_name: str = field(default="X-CSRF-TOKEN")
    cookie_secure: bool = field(default=False)
    cookie_httponly: bool = field(default=False)
    cookie_samesite: Literal["lax", "strict", "none"] = field(default="lax")
    cookie_domain: str | None = field(default=None)
    safe_methods: set[HttpMethod] = field(
        default_factory=lambda: {"GET", "HEAD", "OPTIONS"}
    )
    exclude: list[str] | None = field(default=None)
    exclude_from_csrf_key: str = field(default="exclude_from_csrf")

    @property
    def secret(self) -> str:
        return get_secret("csrf_token.txt")


class AccessTokenConfig(Struct):
    iss: str = field(default="litestar-backend-template")
    aud: str = field(default="litestar-backend-template")
    type: str = field(default="Bearer")
    expiry: int = field(default=5)
    algorithm: str = field(default="HS256")
    cookie_name: str = field(default="access_token")
    blacklist_store: str = field(default="auth:access_token:blacklist")

    @property
    def secret(self) -> str:
        return get_secret("access_token_secret.txt")


class RefreshTokenConfig(Struct):
    expiry: int = field(default=60)
    cookie_name: str = field(default="refresh_token")


class ResponseCacheConfig(Struct):
    default_expiration: int = field(default=60)


class RedisConfig(Struct):
    url: str = field(default="redis://localhost:6379/0")
    socket_connect_timeout: int = field(default=5)
    socket_keepalive: bool = field(default=True)
    health_check_interval: int = field(default=5)

    def create_client(self) -> Redis[bytes]:
        return Redis.from_url(encoding="utf-8", decode_responses=False, **self.to_dict())


class CompressionConfig(Struct):
    backend: Literal["gzip"] = field(default="gzip")
    minimum_size: int = field(default=500)
    gzip_compress_level: int = field(default=9)
    exclude: list[str] | None = field(default_factory=lambda: ["/docs"])
    exclude_opt_key: str = field(default="exclude_from_compression")


class SAQConfig(Struct):
    worker_processes: int = field(default=1)
    web_enabled: bool = field(default=True)


class AllowedHostsConfig(Struct):
    allowed_hosts: list[str] = field(default_factory=lambda: ["*"])
    exclude: list[str] | None = field(default=None)
    exclude_opt_key: str | None = field(default=None)
    www_redirect: bool = field(default=True)


class RateLimitMiddlewareConfig(Struct):
    exclude_opt_key: str | None = field(default="exclude_from_rate_limit")
    exclude_path_pattern: tuple[str, ...] | None = field(default=None)
    store_key: str = field(default="rate_limit")
    route_limits_key: str = field(default="rate_limits")
    limit_header_key: str = field(default="X-RateLimit-Limit")
    remaining_header_key: str = field(default="X-RateLimit-Remaining")
    reset_header_key: str = field(default="X-RateLimit-Reset")
    reset_after_header_key: str = field(default="X-RateLimit-Reset-After")
    scope_header_key: str = field(default="X-RateLimit-Scope")
    global_header_key: str = field(default="X-RateLimit-Global")

    @property
    def encryption_key(self) -> str:
        return get_secret("rate_limit_bucket_encryption_key.txt")

    @property
    def encryption_nonce(self) -> str:
        return get_secret("rate_limit_bucket_encryption_nonce.txt")


class RolesConfig(Struct):
    default_role_slug: str = field(default="user")
    admin_role_slug: str = field(default="admin")


class Config(Struct):
    db: DatabaseConfig
    access_token: AccessTokenConfig
    refresh_token: RefreshTokenConfig
    csrf: CSRFConfig = field(default_factory=CSRFConfig)
    cors: CORSConfig = field(default_factory=CORSConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    response_cache: ResponseCacheConfig = field(default_factory=ResponseCacheConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    saq: SAQConfig = field(default_factory=SAQConfig)
    allowed_hosts: AllowedHostsConfig = field(default_factory=AllowedHostsConfig)
    rate_limit_middleware: RateLimitMiddlewareConfig = field(
        default_factory=RateLimitMiddlewareConfig
    )
    roles: RolesConfig = field(default_factory=RolesConfig)
    loc: str = field(default="app.asgi:create_app")
    debug: bool = field(default=False)
    name: str = field(default="litestar-backend-template")
    base_url: str = field(default="/api/v1")
    authorization_header_key: str = field(default="Authorization")

    @classmethod
    def from_toml(cls, filename: str) -> Self:
        config_file = pathlib.Path(filename).resolve()
        if not config_file.exists():
            msg = f"Config file not found at {str(config_file)!r}"
            raise RuntimeError(msg)

        with config_file.open("rb") as f:
            return toml.decode(f.read(), type=cls)

    @property
    def slug(self) -> str:
        return slugify(self.name)


APP_CONFIG: Final = Config.from_toml("config/app.toml")
"""The application configuration."""
