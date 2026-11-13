"""Uniform JSON error envelope: {"error": {"code": str, "message": str, "details": ...}}."""

import logging
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Raise from services/routes for expected, user-facing failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "app_error",
        status_code: int = 400,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    err = cast(AppError, exc)
    return error_response(err.status_code, err.code, err.message, err.details)


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    err = cast(StarletteHTTPException, exc)
    return error_response(err.status_code, "http_error", str(err.detail))


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    err = cast(RequestValidationError, exc)
    return error_response(422, "validation_error", "Request validation failed", err.errors())


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", extra={"path": request.url.path})
    return error_response(500, "internal_error", "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
