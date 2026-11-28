import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import ConnectionFailure, PyMongoError

logger = logging.getLogger(__name__)

MONGO_DOWN_MESSAGE = (
    "Cannot connect to MongoDB. Check that MONGODB_URI in backend/.env is correct and the database is running. "
    "For MongoDB Atlas, also make sure this computer's IP address is allowed under Network Access."
)


class AppError(Exception):
    """Base class for errors that should be shown to the user as {"detail": "..."}."""

    status_code = 500

    def __init__(self, detail: str, status_code: int | None = None):
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code


class OllamaUnavailableError(AppError):
    """Ollama is not running, unreachable, or timed out."""

    status_code = 503


class ModelNotAvailableError(AppError):
    """The requested model is not installed in Ollama."""

    status_code = 424


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class BadRequestError(AppError):
    status_code = 400


class FileTooLargeError(AppError):
    status_code = 413


class UnsupportedFileTypeError(AppError):
    status_code = 415


def describe_exception(exc: Exception) -> str:
    """Turn any exception into a safe, human readable message (used for in-stream errors)."""
    if isinstance(exc, AppError):
        return exc.detail
    if isinstance(exc, ConnectionFailure):
        return MONGO_DOWN_MESSAGE
    logger.error("Unexpected error", exc_info=exc)
    return "Something went wrong while generating the response"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(ConnectionFailure)
    async def mongo_down_handler(_: Request, exc: ConnectionFailure):
        logger.error("MongoDB connection failure: %s", exc)
        return JSONResponse(status_code=503, content={"detail": MONGO_DOWN_MESSAGE})

    @app.exception_handler(PyMongoError)
    async def mongo_error_handler(request: Request, exc: PyMongoError):
        logger.exception("Database error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Database error"})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        # Return a readable string the frontend can show directly.
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query"))
        message = first.get("msg", "Invalid request")
        detail = f"{field}: {message}" if field else message
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        # Never leak internal details to the client
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
