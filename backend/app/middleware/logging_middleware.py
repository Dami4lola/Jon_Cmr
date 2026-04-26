"""
Request/Response logging middleware with structured JSON logging
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from pythonjsonlogger import jsonlogger

# Configure JSON logger
logger = logging.getLogger("obatek_api")
logger.setLevel(logging.INFO)

# Create JSON formatter
json_formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Console handler with JSON formatting
console_handler = logging.StreamHandler()
console_handler.setFormatter(json_formatter)
logger.addHandler(console_handler)

# Optional: File handler
# file_handler = logging.FileHandler("logs/api.log")
# file_handler.setFormatter(json_formatter)
# logger.addHandler(file_handler)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses"""

    async def dispatch(self, request: Request, call_next):
        # Skip logging for health checks and static files
        if request.url.path in ["/", "/api/health"] or request.url.path.startswith("/uploads"):
            return await call_next(request)

        # Start timer
        start_time = time.time()

        # Log request
        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            }
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Log response
            logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                }
            )

            return response

        except Exception as exc:
            # Calculate duration
            duration = time.time() - start_time

            # Log error
            logger.error(
                "Request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                exc_info=True
            )

            # Re-raise to let error handlers deal with it
            raise
