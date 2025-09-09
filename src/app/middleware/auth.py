from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult
from msgspec import Struct

from app.config import APP_CONFIG
from app.lib.exceptions import NotAuthorizedError
from app.lib.jwt import Token

if TYPE_CHECKING:
    from typing import Any

    from litestar.connection import ASGIConnection

__all__ = ("AuthMiddleware", "AuthenticatedUser")


class AuthenticatedUser(Struct, frozen=True):
    """Represents an authenticated user.

    This structure stores the minimal information extracted from the JWT
    that identifies a user and their roles.

    Parameters
    ----------
    id : int
        The unique identifier of the user.
    roles : set of str
        A set of role slugs associated with the user.
    """

    id: int
    roles: set[str]


class AuthMiddleware(AbstractAuthenticationMiddleware):
    """Middleware for authenticating incoming requests using JWT tokens."""

    async def authenticate_request(
        self, connection: ASGIConnection[Any, AuthenticatedUser, Token, Any]
    ) -> AuthenticationResult:
        """Authenticate an incoming request.

        Parameters
        ----------
        connection : ASGIConnection[Any, AuthenticatedUser, Token, Any]
            The ASGI connection instance representing the current request.

        Returns
        -------
        AuthenticationResult
            An object containing the authenticated user and the validated token.

        Raises
        ------
        NotAuthorizedError
            If the JWT token is missing, invalid, expired, or has been revoked.
        """
        data = connection.headers.get(
            APP_CONFIG.authorization_header_key
        ) or connection.cookies.get(APP_CONFIG.access_token.cookie_name)

        if data is None:
            detail = "No JWT token found in request headers or cookies."
            raise NotAuthorizedError(detail=detail)

        at_config = APP_CONFIG.access_token
        encoded_token = data.replace(at_config.type, "").strip()
        token = Token.from_encoded(
            encoded_token=encoded_token,
            secret=at_config.secret,
            algorithm=at_config.algorithm,
            audience=at_config.aud,
            issuer=at_config.iss,
            required_claims=["sub", "exp", "jti", "roles"],
        )

        assert token.jti is not None
        assert token.sub is not None

        store = connection.app.stores.get(at_config.blacklist_store)

        if await store.exists(token.jti):
            detail = "The provided JWT token has been revoked."
            raise NotAuthorizedError(detail=detail)

        user = AuthenticatedUser(id=int(token.sub), roles=set(token.claims["roles"]))
        return AuthenticationResult(user, token)
