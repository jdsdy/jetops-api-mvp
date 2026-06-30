from fastapi import APIRouter, Depends

from app.api.integration_dependencies import verify_integration_api_key
from app.api.v1.integration.endpoints import analysis, test

integration_router = APIRouter(dependencies=[Depends(verify_integration_api_key)])
integration_router.include_router(test.router)
integration_router.include_router(analysis.router)
