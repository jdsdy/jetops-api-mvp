from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.schemas.signup import VerifySignupCodeRequest

router = APIRouter(prefix="/signup", tags=["signup"])


@router.post("", status_code=status.HTTP_200_OK)
def verify_signup_code(
    request: VerifySignupCodeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if request.code != settings.BETA_SIGNUP_CODE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signup code",
        )
