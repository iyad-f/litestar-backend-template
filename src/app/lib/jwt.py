from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import jwt
from litestar.types import Empty, EmptyType

from app.utils.time import utcnow

from .exceptions import ImproperlyConfiguredError, NotAuthorizedError

if TYPE_CHECKING:
    from typing import Any, Self


# Litestar's default Token class doesnt fit the way i want my
# JWT tokens to be.
class Token:
    """
    JSON Web Token (JWT) representation and utility methods.

    Parameters
    ----------
    iss : str or None, optional
        Issuer claim. Identifies the principal that issued the JWT.
    sub : str or None, optional
        Subject claim. Must be a non-empty string if provided.
    aud : str or list[str] or None, optional
        Audience claim. Identifies the recipients that the JWT is intended for.
    exp : datetime or None, optional
        Expiration time claim. Must be a datetime in the future if provided.
    iat : datetime or None or EmptyType, optional
        Issued-at claim. If ``Empty``, it defaults to the current UTC time.
        Must not be in the future.
    jti : str or None or EmptyType, optional
        Unique token identifier. If ``Empty``, a random value is generated.
    **claims : Any
        Additional custom claims to include in the token.

    Attributes
    ----------
    iss : str | None
        Issuer claim.
    sub : str | None
        Subject claim.
    aud : str | list[str] | None
        Audience claim.
    exp : datetime | None
        Expiration time claim.
    iat : datetime | None
        Issued-at claim.
    jti : str | None
        Token identifier claim.
    claims : dict[str, Any]
        Custom claims.

    Raises
    ------
    ImproperlyConfiguredError
        If ``sub`` is an empty string, ``exp`` is in the past, or ``iat`` is in the future.
    """

    __slots__ = (
        "aud",
        "claims",
        "exp",
        "iat",
        "iss",
        "jti",
        "sub",
    )

    def __init__(
        self,
        *,
        iss: str | None = None,
        sub: str | None = None,
        aud: str | list[str] | None = None,
        exp: datetime | None = None,
        iat: datetime | None | EmptyType = Empty,
        jti: str | None | EmptyType = Empty,
        **claims: Any,
    ) -> None:
        if sub is not None and len(sub) < 1:
            detail = "'sub' must be a string with a length greater than 0"
            raise ImproperlyConfiguredError(detail=detail)

        if exp is not None and exp < utcnow():
            detail = "'exp' value must be a datetime in the future or None"

        if iat is not None:
            if iat is Empty:
                iat = utcnow()
            elif iat > utcnow():
                detail = (
                    "'iat' must be the current datetime, a datetime of the past or None"
                )
                raise ImproperlyConfiguredError(detail=detail)

        if jti is Empty:
            jti = secrets.token_urlsafe(32)

        self.iss = iss
        self.sub = sub
        self.aud = aud
        self.iat = iat
        self.exp = exp
        self.jti = jti
        self.claims = claims

    @classmethod
    def from_encoded(
        cls,
        *,
        encoded_token: str,
        secret: str,
        algorithm: str,
        audience: str | list[str] | None = None,
        issuer: str | None = None,
        required_claims: list[str] | None = None,
        verify_exp: bool = True,
        verify_nbf: bool = True,
        strict_audience: bool = False,
    ) -> Self:
        """Decode a JWT and return a Token instance.

        Parameters
        ----------
        encoded_token : str
            The encoded JWT string to decode.
        secret : str
            The secret or key used to verify the token's signature.
        algorithm : str
            The algorithm to use for verifying the token.
        audience : str or list of str or None, optional
            Expected audience claim(s). Verification is enforced if provided.
        issuer : str or None, optional
            Expected issuer claim. Verification is enforced if provided.
        required_claims : list of str or None, optional
            List of claims that must be present in the payload.
        verify_exp : bool, default=True
            Whether to verify the "exp" (expiration) claim.
        verify_nbf : bool, default=True
            Whether to verify the "nbf" (not before) claim.
        strict_audience : bool, default=False
            If True, the "audience" parameter must be a single string.

        Returns
        -------
        Token
            A Token instance constructed from the decoded payload.

        Raises
        ------
        ValueError
            If strict_audience is True but audience is not a single string.
        NotAuthorizedError
            If the JWT is invalid.
        """
        if strict_audience and (audience is None or not isinstance(audience, str)):
            msg = "When using 'strict_audience=True', 'audience' must be a single string value"
            raise ValueError(msg)

        options: dict[str, Any] = {
            "verify_aud": bool(audience),
            "verify_iss": bool(issuer),
            "verify_exp": verify_exp,
            "verify_nbf": verify_nbf,
            "strict_aud": strict_audience,
        }

        if required_claims:
            options["require"] = required_claims

        try:
            payload: dict[str, Any] = jwt.decode(
                jwt=encoded_token,
                key=secret,
                algorithms=[algorithm],
                issuer=issuer,
                audience=audience,
                options=options,
            )

            try:
                payload["exp"] = datetime.fromtimestamp(payload["exp"], tz=UTC)
            except KeyError:
                pass

            try:
                payload["iat"] = datetime.fromtimestamp(payload["iat"], tz=UTC)
            except KeyError:
                pass

            return cls(**payload)
        except jwt.InvalidTokenError as e:
            detail = "Invalid JWT Token."
            raise NotAuthorizedError(detail=detail) from e

    def encode(self, *, secret: str, algorithm: str) -> str:
        """Encode this Token instance into a JWT string.

        Parameters
        ----------
        secret : str
            The secret or key to sign the token.
        algorithm : str
            The algorithm to use for signing.

        Returns
        -------
        str
            The encoded JWT string.

        Raises
        ------
        ImproperlyConfiguredError
            If encoding fails due to invalid token configuration.
        """
        try:
            payload = {
                k: v for k in self.__slots__ if (v := getattr(self, k)) is not None
            }
            claims: dict[str, Any] = payload.pop("claims")
            payload.update(claims)
            return jwt.encode(payload=payload, key=secret, algorithm=algorithm)
        except (jwt.DecodeError, NotImplementedError) as e:
            detail = "Failed to encode token."
            raise ImproperlyConfiguredError(detail=detail) from e

    @property
    def expires_in(self) -> int | None:
        """Number of seconds until the token expires.

        Returns
        -------
        int or None
            Remaining time in seconds until expiration, or None if no expiry is set.
        """
        return self.exp and int((self.exp - utcnow()).total_seconds())

    def __repr__(self) -> str:
        data = {k: v for k in self.__slots__ if (v := getattr(self, k)) is not None}
        claims: dict[str, Any] = data.pop("claims")
        data.update(claims)
        parts = [f"{k}={v!r}" for k, v in data.items()]
        return f"{self.__class__.__name__}({', '.join(parts)})"
