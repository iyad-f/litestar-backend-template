from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, cast

from litestar import Response, status_codes
from litestar.exceptions import InternalServerException, ValidationException

if TYPE_CHECKING:
    from typing import Any, ClassVar

    from litestar import Request
    from litestar.exceptions import HTTPException


__all__ = (
    "ClientError",
    "ConflictError",
    "HTTPError",
    "ImproperlyConfiguredError",
    "NoFieldsToUpdateError",
    "NotAuthorizedError",
    "NotFoundError",
    "PermissionDeniedError",
    "TooManyRequestsError",
    "ValidationError",
    "http_error_to_http_response",
    "litestar_http_exc_to_http_response",
)


class ApplicationError(Exception):
    """Base error class for all application errors."""


class HTTPError(ApplicationError):
    """HTTP error based on RFC 9457 Problem Details.

    Parameters
    ----------
    *args : Any
        Positional arguments passed to the base ``ApplicationError``.
        If ``detail`` is not provided first arg should be error detail.
    type_ : str, optional
        A URI reference that identifies the problem type.
    status_code : int, optional
        The HTTP status code.
    title : str, optional
        A short, human-readable summary of the problem type.
    detail : str, optional
        A human-readable explanation specific to this occurrence. Defaults
        to the first positional argument if not provided.
    instance : str, optional
        A URI reference that identifies the specific occurrence of the problem.
    headers : dict[str, str], optional
        HTTP headers to include in the response.
    **extension : Any
        Additional extension members to include in the problem details object.

    Notes
    -----
    This implementation follows :rfc:`7807` (Problem Details for HTTP APIs).
    """

    _PROBLEM_DETAILS_MEDIA_TYPE: ClassVar[str] = "application/problem+json"
    type_: str | None
    status_code: int | None
    title: str | None
    detail: str | None
    instance: str | None
    headers: dict[str, str] | None
    extension: dict[str, Any]

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = None,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        self.type_ = type_
        self.status_code = status_code
        self.title = title
        self.detail = detail or (args[0] if args else None)
        self.instance = instance
        self.headers = headers
        self.extension = extension

        super().__init__(*args)

    def to_response(self, request: Request[Any, Any, Any]) -> Response[dict[str, Any]]:
        """Convert Api Error to response."""
        problem_details: dict[str, Any] = {}

        if self.type_ is not None:
            problem_details["type"] = self.type_

        if self.status_code is not None:
            problem_details["status"] = self.status_code

        if self.title is not None:
            problem_details["title"] = self.title
        elif self.status_code is not None:
            problem_details["title"] = HTTPStatus(self.status_code).phrase

        if self.detail is not None:
            problem_details["detail"] = self.detail

        problem_details["instance"] = self.instance or str(request.url)

        if self.extension:
            problem_details.update(self.extension)

        return Response(
            content=problem_details,
            headers=self.headers,
            media_type=self._PROBLEM_DETAILS_MEDIA_TYPE,
            status_code=self.status_code,
        )

    def __repr__(self) -> str:
        return f"{self.status_code} - {self.__class__.__name__} - {self.detail}"


class ImproperlyConfiguredError(HTTPError):
    """Improper configuration error."""

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_500_INTERNAL_SERVER_ERROR,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class ClientError(HTTPError):
    """Raised when a client side error occurs."""

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_400_BAD_REQUEST,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class ValidationError(ClientError):
    """Raised when a client data validation error occurs.."""


class NoFieldsToUpdateError(ValidationError):
    """Raised when there are no fields to update."""

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_400_BAD_REQUEST,
        title: str | None = None,
        detail: str | None = "No fields provided to update.",
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        invalid_parameters = [
            {
                "field": "body",
                "message": "At least one field must be provided for update.",
            }
        ]
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            invalid_parameters=invalid_parameters,
            **extension,
        )


class NotAuthorizedError(ClientError):
    """Raised when the request lacks valid authentication credentials for the requested resource."""

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_401_UNAUTHORIZED,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class PermissionDeniedError(ClientError):
    """Raised when the request understood, but not authorized."""

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_403_FORBIDDEN,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class NotFoundError(ClientError):
    """Raised when we cannot find the requested resource."""

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_404_NOT_FOUND,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class TooManyRequestsError(ClientError):
    """Raised when request limits have been exceeded."""

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_429_TOO_MANY_REQUESTS,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class InternalServerError(HTTPError):
    """Raised when the server encountered an unexpected condition that prevented it from fulfilling the request."""

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_500_INTERNAL_SERVER_ERROR,
        title: str | None = None,
        detail: str
        | None = "Something went wrong on our end. Please contact support if the issue persists.",
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class ConflictError(ClientError):
    """Raised when a request results in a conflict."""

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_409_CONFLICT,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


def http_error_to_http_response(
    request: Request[Any, Any, Any], error: HTTPError
) -> Response[dict[str, Any]]:
    """Convert HTTP error to HTTP response.

    Parameters
    ----------
    request : Request[Any, Any, Any]
        The incoming request.
    error: HTTPError
        The HTTP error that needs to be converted.
    """
    return error.to_response(request)


def litestar_http_exc_to_http_response(
    request: Request[Any, Any, Any], exception: HTTPException
) -> Response[Any]:
    """Convert Litestar HTTP exception to HTTP response.

    Parameters
    ----------
    request : Request[Any, Any, Any]
        The incoming request.
    exception: HTTPException
        The HTTP exception that needs to be converted.
    """
    if isinstance(exception, ValidationException):
        kwargs: dict[str, Any] = {
            "headers": exception.headers,
            "status_code": exception.status_code,
        }
        extra = exception.extra
        invalid_parameters: list[dict[str, Any]] = []

        if isinstance(extra, list):
            for data in extra:
                if not isinstance(data, dict):
                    continue

                data = cast("dict[str, Any]", data)
                params: dict[str, Any] = {}

                if message := data.get("message"):
                    params["message"] = message

                if field := data.get("key"):
                    params["field"] = field

                if params:
                    invalid_parameters.append(params)

        if invalid_parameters:
            kwargs["invalid_parameters"] = invalid_parameters
            kwargs["detail"] = "Validation failed for one or more fields."
        else:
            kwargs["detail"] = exception.detail

        exc = ValidationError(**kwargs)

    elif isinstance(exception, InternalServerException):
        exc = InternalServerError(
            status_code=exception.status_code, headers=exception.headers
        )

    else:
        exc = HTTPError(
            detail=exception.detail,
            status_code=exception.status_code,
            headers=exception.headers,
        )

    return exc.to_response(request)
