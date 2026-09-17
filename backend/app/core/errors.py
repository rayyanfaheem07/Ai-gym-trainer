import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base application exception."""
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "BAD_REQUEST",
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        self.headers = headers or {}


class AuthenticationError(AppException):
    def __init__(self, message: str = "Could not validate credentials."):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_REQUIRED",
            headers={"WWW-Authenticate": "Bearer"},
        )


class DuplicateEntityError(AppException):
    def __init__(self, entity_name: str, field_name: str, field_value: str):
        super().__init__(
            message=f"{entity_name} with {field_name} '{field_value}' already exists.",
            status_code=status.HTTP_409_CONFLICT,
            error_code="DUPLICATE_ENTITY",
            details={"entity": entity_name, "field": field_name, "value": field_value},
        )


class EntityNotFoundError(AppException):
    def __init__(self, entity_name: str, entity_id: str):
        super().__init__(
            message=f"{entity_name} with id '{entity_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            details={"entity_name": entity_name, "entity_id": entity_id},
        )


class InvalidStateTransitionError(AppException):
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_STATE_TRANSITION",
        )


class ForbiddenAccessError(AppException):
    def __init__(self, message: str = "You do not have permission to access this resource."):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
        )


class AIInferenceError(AppException):
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="AI_INFERENCE_ERROR",
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Configures global exception handlers for the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"Domain exception on {request.method} {request.url.path}: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers if exc.headers else None,
            content={
                "detail": exc.message,
                "error_code": exc.error_code,
                "details": exc.details,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning(f"HTTP exception on {request.method} {request.url.path}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers if getattr(exc, "headers", None) else None,
            content={
                "detail": exc.detail,
                "error_code": "HTTP_ERROR",
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Request payload validation failed.",
                "error_code": "VALIDATION_ERROR",
                "errors": jsonable_encoder(exc.errors()),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred. Please contact support.",
                "error_code": "INTERNAL_SERVER_ERROR",
            },
        )

