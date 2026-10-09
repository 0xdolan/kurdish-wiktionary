from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse


def problem_response(
    *,
    status: int,
    title: str,
    detail: str | list[Any],
    type_uri: str = "about:blank",
    instance: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": status,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    if extra:
        body["extra"] = extra
    return JSONResponse(status_code=status, content=body)


def problem_from_request(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str | list[Any],
    type_uri: str = "about:blank",
) -> JSONResponse:
    return problem_response(
        status=status,
        title=title,
        detail=detail,
        type_uri=type_uri,
        instance=str(request.url.path),
    )
