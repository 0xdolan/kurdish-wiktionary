from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from src.api.deps import lifespan_context
from src.api.errors import problem_from_request, problem_response
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.routers import catalog, health, lexicon, mdx, words
from src.config import get_settings
from src.core.exceptions import AppError, DatabaseError
from src.core.logging import configure_logging, get_logger

logger = get_logger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting %s", settings.app_name)
    async with lifespan_context(app, settings):
        yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        description=(
            "Kurdish Wiktionary API. Use header `X-Data-Source: zim|sql` to select backend."
        ),
    )

    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.rate_limit_rpm,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(words.router, prefix=settings.api_prefix)
    app.include_router(mdx.router, prefix=settings.api_prefix)
    app.include_router(catalog.router, prefix=settings.api_prefix)
    app.include_router(lexicon.router, prefix=settings.api_prefix)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return problem_response(
            status=exc.status_code,
            title=exc.__class__.__name__,
            detail=exc.detail,
            type_uri=exc.type_uri,
            instance=exc.instance or str(request.url.path),
            extra=exc.extra or None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return problem_from_request(
            request,
            status=422,
            title="ValidationError",
            detail=list(exc.errors()),
            type_uri="https://wiktionary-to-mdx/errors/validation",
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.warning("Database error: %s", exc)
        db_error = DatabaseError("Database operation failed.")
        return problem_response(
            status=db_error.status_code,
            title=db_error.__class__.__name__,
            detail=db_error.detail,
            type_uri=db_error.type_uri,
            instance=str(request.url.path),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return problem_from_request(
            request,
            status=500,
            title="Internal Server Error",
            detail="An unexpected error occurred.",
        )

    return app


app = create_app()
