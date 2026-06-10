from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.dependencies import (
    AuthenticatedUserDep,
    get_authenticated_user,
    verify_api_key,
)
from app.core.supabase import get_supabase_client
from app.repositories.analysis_context_repository import AnalysisContextRepository
from app.repositories.job_repository import JobRepository
from app.schemas.analysis_context import BeginAnalysisResponse
from app.schemas.job import (
    BeginAnalysisRequest,
    CreateJobRequest,
    CreateJobResponse,
)
from app.services.analysis_service import AnalysisService
from app.services.analysis_task import run_analysis_task
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


def get_analysis_service() -> AnalysisService:
    client = get_supabase_client()
    return AnalysisService(JobRepository(client), AnalysisContextRepository(client))


JobServiceDep = Annotated[JobService, Depends(get_job_service)]
AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]


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


@router.post("/analysis", status_code=status.HTTP_200_OK)
def begin_analysis(
    request: BeginAnalysisRequest,
    analysis_service: AnalysisServiceDep,
    background_tasks: BackgroundTasks,
) -> BeginAnalysisResponse:
    try:
        response = analysis_service.begin_analysis(request)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    background_tasks.add_task(
        run_analysis_task,
        request.job_id,
        request.flight_plan_id,
    )
    return response
