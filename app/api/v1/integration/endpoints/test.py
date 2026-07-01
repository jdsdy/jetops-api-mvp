from fastapi import APIRouter, status

from app.schemas.integration_test import IntegrationTestResponse

router = APIRouter(tags=["integration"])


@router.get("/test", status_code=status.HTTP_200_OK)
def integration_test() -> IntegrationTestResponse:
    return IntegrationTestResponse(status="ok")
