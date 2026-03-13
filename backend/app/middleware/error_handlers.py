"""
Global exception handlers for FastAPI
"""
import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError

logger = logging.getLogger("obatek_api")


def register_exception_handlers(app: FastAPI):
    """Register all exception handlers with the FastAPI app"""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors"""
        errors = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            errors.append({
                "field": field,
                "message": error["msg"],
                "type": error["type"],
            })

        logger.warning(
            "Validation error",
            extra={
                "path": request.url.path,
                "method": request.method,
                "errors": errors,
            }
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation error",
                "errors": errors,
            },
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_error_handler(request: Request, exc: ValidationError):
        """Handle Pydantic ValidationError (non-request validation)"""
        errors = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            errors.append({
                "field": field,
                "message": error["msg"],
                "type": error["type"],
            })

        logger.warning(
            "Pydantic validation error",
            extra={
                "path": request.url.path,
                "method": request.method,
                "errors": errors,
            }
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Data validation error",
                "errors": errors,
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        """Handle database integrity constraint violations"""
        logger.error(
            "Database integrity error",
            extra={
                "path": request.url.path,
                "method": request.method,
                "error": str(exc.orig),
            },
            exc_info=True
        )

        # Try to extract useful info from the error
        error_msg = str(exc.orig)
        detail = "Database constraint violation"

        if "unique constraint" in error_msg.lower():
            detail = "A record with this data already exists"
        elif "foreign key constraint" in error_msg.lower():
            detail = "Referenced record does not exist"
        elif "not null constraint" in error_msg.lower():
            detail = "Required field is missing"

        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": detail,
                "type": "integrity_error",
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
        """Handle general SQLAlchemy database errors"""
        logger.error(
            "Database error",
            extra={
                "path": request.url.path,
                "method": request.method,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=True
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Database error occurred",
                "type": "database_error",
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle ValueError exceptions"""
        logger.warning(
            "Value error",
            extra={
                "path": request.url.path,
                "method": request.method,
                "error": str(exc),
            }
        )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": str(exc),
                "type": "value_error",
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Catch-all handler for unhandled exceptions"""
        logger.error(
            "Unhandled exception",
            extra={
                "path": request.url.path,
                "method": request.method,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=True
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred",
                "type": "internal_error",
            },
        )
