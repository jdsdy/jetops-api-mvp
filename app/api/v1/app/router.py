from fastapi import APIRouter

from app.api.v1.app.endpoints import jobs, signup

app_router = APIRouter(prefix="/app")
app_router.include_router(jobs.router)
app_router.include_router(signup.router)
