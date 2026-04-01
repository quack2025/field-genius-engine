"""Standardized error responses for the API.

All errors return:
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "request_id": "abc123"
  }
}

HTTP status codes are the source of truth for success/failure.
"""

from __future__ import annotations

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger(__name__)

# Map HTTP status codes to error codes
STATUS_TO_CODE = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
}


def _get_request_id(request: Request) -> str:
    """Extract request ID from structlog context or header."""
    try:
        ctx = structlog.contextvars.get_contextvars()
        return ctx.get("request_id", "unknown")
    except Exception:
        return request.headers.get("X-Request-Id", "unknown")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTPException with standardized error format."""
    status = exc.status_code
    code = STATUS_TO_CODE.get(status, "ERROR")
    request_id = _get_request_id(request)

    # Don't leak internal details for 500s
    if status >= 500:
        message = "An internal error occurred"
        logger.error("http_error", status=status, detail=str(exc.detail), request_id=request_id)
    else:
        message = str(exc.detail) if exc.detail else code
        logger.warning("http_error", status=status, detail=message, request_id=request_id)

    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        headers={"X-Request-Id": request_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors with standardized format."""
    request_id = _get_request_id(request)
    errors = exc.errors()

    # Build human-readable message
    fields = [f"{e.get('loc', ['?'])[-1]}: {e.get('msg', '?')}" for e in errors[:3]]
    message = "Validation failed: " + "; ".join(fields)

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": message,
                "request_id": request_id,
                "details": errors[:5],
            }
        },
        headers={"X-Request-Id": request_id},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions. Never leak internals."""
    request_id = _get_request_id(request)
    logger.error("unhandled_exception", error=str(exc), error_type=type(exc).__name__, request_id=request_id)

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred. Reference: " + request_id,
                "request_id": request_id,
            }
        },
        headers={"X-Request-Id": request_id},
    )
