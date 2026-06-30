from fastapi import APIRouter

from app.api.v1.app.router import app_router
from app.api.v1.integration.router import integration_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(app_router)
api_router.include_router(integration_router)
