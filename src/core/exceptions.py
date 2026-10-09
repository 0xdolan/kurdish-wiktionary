from typing import Any


class AppError(Exception):
    """Base application error with HTTP mapping metadata."""

    status_code: int = 500
    type_uri: str = "about:blank"

    def __init__(
        self,
        detail: str,
        *,
        instance: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.instance = instance
        self.extra = extra or {}


class NotFoundError(AppError):
    status_code = 404
    type_uri = "https://wiktionary-to-mdx/errors/not-found"


class ZimError(AppError):
    status_code = 503
    type_uri = "https://wiktionary-to-mdx/errors/zim"


class DatabaseError(AppError):
    status_code = 503
    type_uri = "https://wiktionary-to-mdx/errors/database"
