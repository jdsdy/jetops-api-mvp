from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from uuid import UUID

from starlette.background import BackgroundTask, BackgroundTasks
from starlette.requests import Request
from starlette.responses import Response

from app.core.supabase import get_supabase_client
from app.repositories.api_log_repository import ApiLogRepository

API_SERVICE_NAME = "fastapi"
_V1_PREFIX = "/v1"
_logger = logging.getLogger(__name__)


def normalise_v1_path(path: str) -> str | None:
    if path == _V1_PREFIX or path.startswith(f"{_V1_PREFIX}/"):
        return path
    return None


def extract_organisation_id_from_body(body: bytes) -> UUID | None:
    if not body:
        return None

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, Mapping):
        return None

    organisation_id = payload.get("organisation_id")
    if organisation_id is None:
        return None

    try:
        return UUID(str(organisation_id))
    except ValueError:
        return None


def extract_error_message_from_response_body(body: bytes) -> str | None:
    if not body:
        return None

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, Mapping):
        return None

    detail = payload.get("detail")
    if detail is None:
        return None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        messages: list[str] = []
        for item in detail:
            if isinstance(item, Mapping) and item.get("msg") is not None:
                messages.append(str(item["msg"]))
            else:
                messages.append(str(item))
        return "; ".join(messages) if messages else None
    return str(detail)


async def _cache_request_body(request: Request) -> bytes:
    body = await request.body()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # noqa: SLF001
    return body


async def _response_with_body(response: Response) -> tuple[Response, bytes]:
    body = b"".join([chunk async for chunk in response.body_iterator])
    headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() != "content-length"
    }
    return (
        Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        ),
        body,
    )


def _schedule_api_log(
    response: Response,
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: int,
    user_id: UUID | None,
    organisation_id: UUID | None,
    api_client_id: UUID | None,
    error_message: str | None,
) -> None:
    log_kwargs = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "user_id": user_id,
        "organisation_id": organisation_id,
        "api_client_id": api_client_id,
        "error_message": error_message,
    }

    if response.background is None:
        response.background = BackgroundTask(_write_api_log, **log_kwargs)
        return

    if isinstance(response.background, BackgroundTasks):
        response.background.add_task(_write_api_log, **log_kwargs)
        return

    combined = BackgroundTasks()
    combined.add_task(
        response.background.func,
        *response.background.args,
        **response.background.kwargs,
    )
    combined.add_task(_write_api_log, **log_kwargs)
    response.background = combined


def _write_api_log(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: int,
    user_id: UUID | None,
    organisation_id: UUID | None,
    api_client_id: UUID | None,
    error_message: str | None,
) -> None:
    try:
        repository = ApiLogRepository(get_supabase_client())
        repository.insert_api_log(
            service=API_SERVICE_NAME,
            method=method,
            path=path,
            status_code=status_code,
            user_id=user_id,
            organisation_id=organisation_id,
            api_client_id=api_client_id,
            duration_ms=duration_ms,
            error_message=error_message,
        )
    except Exception:
        _logger.exception("Failed to write api_logs row for %s %s", method, path)


async def log_v1_request_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    path = normalise_v1_path(request.url.path)
    if path is None:
        return await call_next(request)

    organisation_id = None
    if request.method in {"POST", "PUT", "PATCH"}:
        body = await _cache_request_body(request)
        organisation_id = extract_organisation_id_from_body(body)

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)

    error_message = getattr(request.state, "error_message", None)
    if error_message is None and response.status_code >= 400:
        response, response_body = await _response_with_body(response)
        error_message = extract_error_message_from_response_body(response_body)

    _schedule_api_log(
        response,
        method=request.method,
        path=path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        user_id=getattr(request.state, "user_id", None),
        organisation_id=organisation_id,
        api_client_id=getattr(request.state, "api_client_id", None),
        error_message=error_message,
    )
    return response
