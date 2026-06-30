import hashlib
import logging
from datetime import UTC, datetime
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.supabase import get_supabase_client
from app.repositories.api_key_repository import ApiKeyRepository
from app.schemas.integration_auth import IntegrationAuthContext

integration_bearer_scheme = HTTPBearer(auto_error=False)
_logger = logging.getLogger(__name__)


def _raise_unauthorized() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
    )


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def validate_key_record(
    row: dict | None,
    now: datetime,
) -> IntegrationAuthContext | None:
    if row is None:
        return None

    if not row.get("is_active", False):
        return None

    if row.get("revoked_at") is not None:
        return None

    expires_at = row.get("expires_at")
    if expires_at is not None and _parse_timestamp(expires_at) < now:
        return None

    client = row.get("api_clients")
    if not isinstance(client, dict) or not client.get("is_active", False):
        return None

    organisation_id = client.get("organisation_id")
    return IntegrationAuthContext(
        api_key_id=UUID(str(row["id"])),
        api_client_id=UUID(str(row["api_client_id"])),
        organisation_id=UUID(str(organisation_id)) if organisation_id else None,
    )


def get_api_key_repository() -> ApiKeyRepository:
    return ApiKeyRepository(get_supabase_client())


def verify_integration_api_key(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(integration_bearer_scheme),
    ],
    background_tasks: BackgroundTasks,
    repository: Annotated[ApiKeyRepository, Depends(get_api_key_repository)],
) -> IntegrationAuthContext:
    if credentials is None:
        _raise_unauthorized()

    try:
        row = repository.lookup_by_hash(hash_api_key(credentials.credentials))
    except Exception:
        _logger.exception("Unexpected error during integration API key lookup")
        _raise_unauthorized()

    context = validate_key_record(row, datetime.now(UTC))
    if context is None:
        _raise_unauthorized()

    request.state.api_client_id = context.api_client_id
    request.state.organisation_id = context.organisation_id
    request.state.api_key_hash = hash_api_key(credentials.credentials)
    background_tasks.add_task(repository.touch_last_used, context.api_key_id)
    return context


IntegrationAuthDep = Annotated[IntegrationAuthContext, Depends(verify_integration_api_key)]
