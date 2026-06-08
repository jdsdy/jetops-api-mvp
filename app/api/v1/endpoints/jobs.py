from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.dependencies import (
    AuthenticatedUserDep,
    get_authenticated_user,
    verify_api_key,
)
from app.core.supabase import get_supabase_client
from app.repositories.job_repository import JobRepository
from app.schemas.job import CreateJobRequest, CreateJobResponse
from app.services.extraction_task import run_extraction
from app.services.job_service import JobService

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    dependencies=[Depends(verify_api_key), Depends(get_authenticated_user)],
)


def get_job_service() -> JobService:
    client = get_supabase_client()
    return JobService(JobRepository(client))


JobServiceDep = Annotated[JobService, Depends(get_job_service)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job(
    request: CreateJobRequest,
    user: AuthenticatedUserDep,
    job_service: JobServiceDep,
    background_tasks: BackgroundTasks,
) -> CreateJobResponse:
    try:
        job_id = job_service.create_job(request, user)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    background_tasks.add_task(
        run_extraction,
        job_id,
        request.flight_plan_id,
        request.storage_path,
    )

    return CreateJobResponse(id=job_id)
