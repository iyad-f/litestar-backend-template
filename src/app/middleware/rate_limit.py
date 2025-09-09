from __future__ import annotations

import binascii
import math
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV
from litestar import Request
from litestar.datastructures import MutableScopeHeaders
from litestar.enums import ScopeType
from litestar.middleware import ASGIMiddleware
from litestar.serialization import decode_json, encode_json
from msgspec import Struct, field

from app.lib.exceptions import TooManyRequestsError
from app.utils.math import round_up

if TYPE_CHECKING:
    from typing import Self

    from litestar.stores.base import Store
    from litestar.types import ASGIApp, Message, Receive, Scope, Send


__all__ = ("RateLimitMiddleware", "RateLimitPolicy")


class RateLimitPolicy(Struct, frozen=True):
    """Rate limit policy.

    A rate limit policy defines how tokens are allocated and refilled
    for a given rate limit. It can also specify optional priority,
    header-setting behaviour, and exemption rules.

    Parameters
    ----------
    capacity : int
        Maximum number of tokens that the bucket can hold at any time.
        This represents the burst capacity of the rate limit.
    refill_rate : float
        Rate at which tokens are refilled, in tokens per second.
        For example, a value of 3 means 3 tokens are added each second
        until the bucket reaches its capacity.
    priority : int, optional
        Priority of the rate limit when multiple policies apply.
        Lower values take precedence (the default is 0).
    set_headers : bool, optional
        Whether to include the rate limit headers configured in
        :class:`RateLimitMiddleware` in responses
        (the default is True).
    set_429_headers : bool, optional
        Whether to include the 429-related headers configured in
        :class:`RateLimitMiddleware` when a request is rejected
        due to rate limiting (the default is True).
    is_exempt : Callable[[Request], Awaitable[bool]], optional
        Async predicate that determines if a given request is exempt
        from this policy. If provided and returns ``True``, the request
        bypasses rate limiting (the default is None).
    """

    capacity: int
    refill_rate: float
    priority: int = field(default=0)
    set_headers: bool = field(default=True)
    set_429_headers: bool = field(default=True)
    is_exempt: Callable[[Request[Any, Any, Any]], Awaitable[bool]] | None = field(
        default=None
    )

    def __gt__(self, other: RateLimitPolicy) -> bool:
        return self.priority < other.priority


class BucketState(Struct, frozen=True):
    """State of a token bucket in the storage.

    This struct stores the minimal state needed to persist and later
    reconstruct a :class:`TokenBucket`.

    Parameters
    ----------
    tokens : float
        Current number of tokens in the bucket.
    last_refill : float
        Timestamp (from :func:`time.monotonic`) of the last refill operation.
    """

    tokens: float
    last_refill: float


# This can be a normal class as well, but since we already have msgspec as a dependency and
# Struct's are faster to create, and there is no need of **kwargs or something which makes
# it necessary to use a class, we are fine with a struct.
class TokenBucket(Struct):
    """Token bucket used for rate limiting.

    This class implements the token bucket algorithm for rate limiting,
    where tokens accumulate over time at a fixed rate. Each request consumes
    one token, and requests are allowed only if at least one token is available.

    Parameters
    ----------
    store : :class:`litestar.stores.Store`
        Backend store used to persist bucket state.
    key : str
        Unique key under which the bucket is stored.
    capacity : int
        Maximum number of tokens the bucket can hold.
    refill_rate : float
        Rate at which tokens are refilled (tokens per second).
    tokens : float
        Current number of tokens in the bucket.
    last_refill : float
        Timestamp of the last refill (the default is time.monotonic()).
    """

    # storage related params.
    store: Store
    key: str

    # bucket related params
    capacity: int
    refill_rate: float
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)

    async def allow_request(self) -> bool:
        """Attempt to consume one token from the bucket.

        Returns
        -------
        bool
            True if a token was consumed,
            False if no tokens were available.
        """
        now = time.monotonic()
        tokens_to_add = (now - self.last_refill) * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

        allowed = self.tokens >= 1
        if allowed:
            self.tokens -= 1

        await self.save()

        return allowed

    async def save(self) -> None:
        """Persist the current state of the bucket."""
        to_store = BucketState(self.tokens, self.last_refill)
        await self.store.set(self.key, encode_json(to_store), expires_in=self.expires_in)

    @classmethod
    async def from_store_or_new(
        cls, store: Store, key: str, limit: RateLimitPolicy
    ) -> Self:
        """Load a token bucket from the store, or create a new one.

        Parameters
        ----------
        store : :class:`litestar.stores.Store`
            Backend store instance.
        key : str
            Unique key identifying the bucket.
        limit : RateLimitPolicy
            Rate limit policy specifying capacity and refill rate.

        Returns
        -------
        TokenBucket
            A restored or newly created token bucket instance.
        """
        kwargs: dict[str, Any] = {
            "store": store,
            "key": key,
            "capacity": limit.capacity,
            "refill_rate": limit.refill_rate,
        }
        cached = await store.get(key)

        if cached is not None:
            stored = decode_json(cached, target_type=BucketState)
            kwargs["tokens"] = stored.tokens
            kwargs["last_refill"] = stored.last_refill
        else:
            kwargs["tokens"] = limit.capacity

        return cls(**kwargs)

    def __gt__(self, other: TokenBucket) -> bool:
        return self.tokens > other.tokens

    @property
    def expires_in(self) -> int:
        """Number of seconds until the bucket entry expires in the store.

        The expiration is calculated as the time required to fully
        refill the bucket, plus a grace period of one minute.

        Returns
        -------
        int
            Expiration time in seconds.
        """
        return math.ceil(self.capacity / self.refill_rate) + 60

    @property
    def reset_after(self) -> float:
        """Number of seconds until the next token becomes available.

        At least one token is required to accept a request. If the
        bucket already has one or more tokens, the reset time is
        zero. Otherwise, the time is calculated as the deficit
        divided by the refill rate.

        Returns
        -------
        float
            Time in seconds until the bucket has at least one token.
        """
        return max(0, 1 - self.tokens) / self.refill_rate


class RateLimitMiddleware(ASGIMiddleware):
    """Token bucket-based rate limiting middleware.

    This middleware enforces both global and per-route rate limits
    using the token bucket algorithm. Limits are defined as
    :class:`RateLimitPolicy` objects and can be configured globally
    (applied to all requests) or on a per-route basis.

    Parameters
    ----------
    exclude_opt_key : str, optional
        Key to check in route options to exclude the route from rate limiting (the default is None).
    exclude_path_pattern : str or tuple[str, ...], optional
        Regex pattern(s) for paths that should bypass rate limiting (the default is None).
    global_limits : list[RateLimitPolicy], optional
        Policies applied globally across all requests (the default is None).
    store_key : str, optional
        The store key used to persist bucket state (the default is "rate_limit").
    route_limits_key : str, optional
        Key in route options where per-route limits are defined (the default is "rate_limits").
    authorization_header_key : str, optional
        The Authorization header name (the default is "Authorization").
    limit_header_key, remaining_header_key, reset_header_key, reset_after_header_key,
    bucket_header_key, scope_header_key, global_header_key : str
        Header names for emitted rate limit information.
    """

    __slots__ = (
        "_aesgcmsiv",
        "_encryption_nonce",
        "authorization_header_key",
        "bucket_header_key",
        "global_header_key",
        "global_limits",
        "limit_header_key",
        "remaining_header_key",
        "reset_after_header_key",
        "reset_header_key",
        "route_limits_key",
        "scope_header_key",
        "store_key",
    )

    global_limits: list[RateLimitPolicy]
    store_key: str
    route_limits_key: str
    authorization_header_key: str
    limit_header_key: str
    remaining_header_key: str
    reset_header_key: str
    reset_after_header_key: str
    bucket_header_key: str
    scope_header_key: str
    global_header_key: str
    _aesgcmsiv: AESGCMSIV
    _encryption_nonce: bytes

    def __init__(
        self,
        *,
        encryption_key: str,
        encryption_nonce: str,
        exclude_opt_key: str | None = None,
        exclude_path_pattern: str | tuple[str, ...] | None = None,
        global_limits: list[RateLimitPolicy] | None = None,
        store_key: str = "rate_limit",
        route_limits_key: str = "rate_limits",
        authorization_header_key: str = "Authorization",
        limit_header_key: str = "X-RateLimit-Limit",
        remaining_header_key: str = "X-RateLimit-Remaining",
        reset_header_key: str = "X-RateLimit-Reset",
        reset_after_header_key: str = "X-RateLimit-Reset-After",
        bucket_header_key: str = "X-RateLimit-Bucket",
        scope_header_key: str = "X-RateLimit-Scope",
        global_header_key: str = "X-RateLimit-Global",
    ) -> None:
        self.scopes = (ScopeType.HTTP,)
        self.exclude_opt_key = exclude_opt_key
        self.exclude_path_pattern = exclude_path_pattern

        if global_limits is not None:
            global_limits.sort()

        self.global_limits = global_limits or []
        self.store_key = store_key
        self.route_limits_key = route_limits_key
        self.authorization_header_key = authorization_header_key
        self.limit_header_key = limit_header_key
        self.remaining_header_key = remaining_header_key
        self.reset_header_key = reset_header_key
        self.reset_after_header_key = reset_after_header_key
        self.bucket_header_key = bucket_header_key
        self.scope_header_key = scope_header_key
        self.global_header_key = global_header_key

        # We dont really need this encryption elsewhere, so this isn't
        # a utils function, and hence we are saving the object creation
        # time of AESGCMSIV, on every request.
        self._aesgcmsiv = AESGCMSIV(binascii.unhexlify(encryption_key))
        self._encryption_nonce = binascii.unhexlify(encryption_nonce)

    async def handle(
        self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp
    ) -> None:
        """Handle ASGI call.

        Parameters
        ----------
        scope : Scope
            The ASGI connection scope.
        receive : Receive
            The ASGI receive function.
        send : Send
            The ASGI send function.
        next_app : ASGIApp
            The next ASGI application in the middleware stack to call.
        """
        app = scope["litestar_app"]
        request: Request[Any, Any, Any] = app.request_class(scope)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        store = app.stores.get(self.store_key)

        route_handler = scope["route_handler"]
        route_limits: list[RateLimitPolicy] = route_handler.opt.get(
            self.route_limits_key, []
        )
        route_limits.sort()

        most_limited = None

        for limit in self.global_limits:
            most_limited = await self._handle_limit(
                limit, request, store, most_limited, is_global=True
            )

        for limit in route_limits:
            most_limited = await self._handle_limit(limit, request, store, most_limited)

        if most_limited is not None:
            send = self._wrap_send(send, most_limited)

        await next_app(scope, receive, send)

    async def _handle_limit(
        self,
        limit: RateLimitPolicy,
        request: Request[Any, Any, Any],
        store: Store,
        most_limited: TokenBucket | None = None,
        *,
        is_global: bool = False,
    ) -> TokenBucket | None:
        is_exempt = limit.is_exempt

        if is_exempt is not None and await is_exempt(request):
            return None

        key = self._build_storage_key(request, limit, is_global=is_global)
        bucket = await TokenBucket.from_store_or_new(store, key, limit)

        if not await bucket.allow_request():
            # global is a reserved keyword :)
            kwargs: dict[str, Any] = {"global": is_global}

            if limit.set_429_headers:
                kwargs["headers"] = self._build_429_headers(bucket, is_global=is_global)

            detail = "You are being rate limited."
            raise TooManyRequestsError(
                detail=detail, retry_after=round_up(bucket.reset_after), **kwargs
            )

        return (
            None
            if not limit.set_headers
            else bucket
            if most_limited is None or most_limited > bucket
            else most_limited
        )

    def _build_storage_key(
        self,
        request: Request[Any, Any, Any],
        limit: RateLimitPolicy,
        *,
        is_global: bool = False,
    ) -> str:
        identifier = (
            request.headers.get(self.authorization_header_key)
            or request.headers.get("X-Forwarded-For")
            or request.headers.get("X-Real-IP")
            or getattr(request.client, "host", "anonymous")
        )

        if not is_global:
            identifier = (
                f"{identifier}::{request.method}::{request.scope['path_template']}"
            )

        return f"{identifier}::{limit.capacity}::{limit.refill_rate}"

    def _wrap_send(self, send: Send, bucket: TokenBucket) -> Send:
        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                headers = MutableScopeHeaders(message)
                for k, v in self._build_headers(bucket).items():
                    headers[k] = v
            await send(message)

        return send_wrapper

    def _build_headers(self, bucket: TokenBucket) -> dict[str, str]:
        reset_after = bucket.reset_after
        reset_timestamp = time.time() + reset_after

        # The best practice would be to have some associated data for security reasons,
        # but this case is not one of those cases where having no associated data poses
        # a security threat, so we are fine without it.
        result = self._aesgcmsiv.encrypt(
            self._encryption_nonce, bucket.key.encode("utf-8"), None
        )
        ciphertext, _ = result[:-16], result[-16:]
        bucket_hash = ciphertext.hex()

        return {
            self.limit_header_key: str(bucket.capacity),
            self.remaining_header_key: str(int(bucket.tokens)),
            self.reset_header_key: f"{round_up(reset_timestamp)}",
            self.reset_after_header_key: f"{round_up(reset_after)}",
            self.bucket_header_key: bucket_hash,
        }

    def _build_429_headers(
        self,
        bucket: TokenBucket,
        *,
        is_global: bool = False,
    ) -> dict[str, str]:
        headers = self._build_headers(bucket)
        headers[self.scope_header_key] = "global" if is_global else "user"

        if is_global:
            headers[self.global_header_key] = "true"

        return headers
