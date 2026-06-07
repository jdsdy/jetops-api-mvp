import secrets
from typing import Annotated, NoReturn

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase_auth.types import User

from app.core.config import get_settings
from app.core.supabase import get_supabase_client

bearer_scheme = HTTPBearer(auto_error=False)


def _raise_unauthorized() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
    )


def verify_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    settings = get_settings()
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.API_KEY):
        _raise_unauthorized()


def get_authenticated_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ] = None,
) -> User:
    if credentials is None:
        _raise_unauthorized()

    client = get_supabase_client()
    try:
        response = client.auth.get_user(credentials.credentials)
    except Exception:
        _raise_unauthorized()

    if response.user is None:
        _raise_unauthorized()

    return response.user


ApiKeyDep = Annotated[None, Depends(verify_api_key)]
AuthenticatedUserDep = Annotated[User, Depends(get_authenticated_user)]
