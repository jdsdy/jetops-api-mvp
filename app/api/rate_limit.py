import math
import time
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from upstash_ratelimit import FixedWindow, Ratelimit
from upstash_redis import Redis

from app.api.dependencies import AuthenticatedUserDep
from app.core.config import get_settings

RATE_LIMIT_EXCEEDED_DETAIL = "Rate limit exceeded. Please try again later."


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    return Redis(
        url=settings.UPSTASH_REDIS_REST_URL,
        token=settings.UPSTASH_REDIS_REST_TOKEN,
    )


@lru_cache
def get_create_job_ratelimit() -> Ratelimit:
    return Ratelimit(
        redis=get_redis(),
        limiter=FixedWindow(max_requests=1, window=10),
        prefix="@upstash/ratelimit/jetops/post/v1/jobs",
    )


@lru_cache
def get_begin_analysis_ratelimit() -> Ratelimit:
    return Ratelimit(
        redis=get_redis(),
        limiter=FixedWindow(max_requests=1, window=120),
        prefix="@upstash/ratelimit/jetops/post/v1/jobs/analysis",
    )


def _enforce_ratelimit(ratelimit: Ratelimit, identifier: str) -> None:
    response = ratelimit.limit(identifier)
    if response.allowed:
        return

    headers: dict[str, str] = {}
    retry_after = max(1, math.ceil(response.reset - time.time()))
    headers["Retry-After"] = str(retry_after)

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=RATE_LIMIT_EXCEEDED_DETAIL,
        headers=headers,
    )


def rate_limit_create_job(
    user: AuthenticatedUserDep,
    ratelimit: Annotated[Ratelimit, Depends(get_create_job_ratelimit)],
) -> None:
    _enforce_ratelimit(ratelimit, user.id)


def rate_limit_begin_analysis(
    user: AuthenticatedUserDep,
    ratelimit: Annotated[Ratelimit, Depends(get_begin_analysis_ratelimit)],
) -> None:
    _enforce_ratelimit(ratelimit, user.id)
