import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from upstash_ratelimit import Response

from app.api.rate_limit import (
    RATE_LIMIT_EXCEEDED_DETAIL,
    _enforce_ratelimit,
    rate_limit_create_job,
    rate_limit_integration_poll,
)


def test_enforce_ratelimit_allows_when_under_limit() -> None:
    ratelimit = MagicMock()
    ratelimit.limit.return_value = Response(
        allowed=True,
        limit=1,
        remaining=0,
        reset=time.time() + 10,
    )

    _enforce_ratelimit(ratelimit, "user-123")

    ratelimit.limit.assert_called_once_with("user-123")


def test_enforce_ratelimit_raises_429_with_retry_after() -> None:
    ratelimit = MagicMock()
    ratelimit.limit.return_value = Response(
        allowed=False,
        limit=1,
        remaining=0,
        reset=time.time() + 8.2,
    )

    with pytest.raises(HTTPException) as exc_info:
        _enforce_ratelimit(ratelimit, "user-123")

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == RATE_LIMIT_EXCEEDED_DETAIL
    assert exc_info.value.headers is not None
    assert exc_info.value.headers["Retry-After"] == "9"


def test_rate_limit_create_job_uses_authenticated_user_id() -> None:
    user = MagicMock()
    user.id = "user-abc"
    ratelimit = MagicMock()
    ratelimit.limit.return_value = Response(
        allowed=True,
        limit=1,
        remaining=0,
        reset=time.time() + 10,
    )

    rate_limit_create_job(user=user, ratelimit=ratelimit)

    ratelimit.limit.assert_called_once_with("user-abc")


def test_rate_limit_integration_poll_uses_api_key_hash() -> None:
    from starlette.requests import Request

    request = Request(
        {
            "type": "http",
            "headers": [],
            "method": "GET",
            "path": "/v1/analysis/job-id",
        }
    )
    request.state.api_key_hash = "hashed-key"
    ratelimit = MagicMock()
    ratelimit.limit.return_value = Response(
        allowed=True,
        limit=10,
        remaining=9,
        reset=time.time() + 1,
    )

    rate_limit_integration_poll(request=request, ratelimit=ratelimit)

    ratelimit.limit.assert_called_once_with("hashed-key")
