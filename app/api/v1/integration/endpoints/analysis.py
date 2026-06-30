from datetime import datetime
from uuid import UUID

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from app.api.integration_dependencies import IntegrationAuthDep
from app.api.rate_limit import rate_limit_integration_poll
from app.core.errors import (
    IntegrationAnalysisTooManyNotamsError,
    IntegrationAnalysisValidationError,
)
from app.core.supabase import get_supabase_client
from app.repositories.analysed_notam_repository import AnalysedNotamRepository
from app.repositories.job_repository import JobRepository
from app.schemas.integration_analysis import (
    DEFAULT_INTEGRATION_LIST_LIMIT,
    MAX_INTEGRATION_LIST_LIMIT,
    IntegrationAnalysisListParams,
    IntegrationAnalysisListResponse,
    IntegrationAnalysisPollResponse,
    IntegrationAnalysisRequest,
    IntegrationAnalysisStatus,
    IntegrationAnalysisSubmitResponse,
    IntegrationErrorCode,
)
from app.services.integration.analysis_submission import (
    validate_and_normalize_analysis_submission,
)
from app.services.integration.integration_analysis_service import (
    IntegrationAnalysisService,
)
from app.services.integration.integration_analysis_task import run_integration_analysis

router = APIRouter(prefix="/analysis", tags=["integration"])


def get_integration_analysis_service() -> IntegrationAnalysisService:
    client = get_supabase_client()
    return IntegrationAnalysisService(
        JobRepository(client),
        AnalysedNotamRepository(client),
    )


def _error_response(
    status_code: int,
    message: str,
    *,
    code: IntegrationErrorCode = IntegrationErrorCode.INVALID_REQUEST_FORMAT,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_analysis(
    request: Request,
    auth: IntegrationAuthDep,
    background_tasks: BackgroundTasks,
    service: IntegrationAnalysisService = Depends(get_integration_analysis_service),
) -> IntegrationAnalysisSubmitResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError as error:
        return _error_response(
            status.HTTP_400_BAD_REQUEST,
            "Malformed JSON body",
        )

    try:
        submission = validate_and_normalize_analysis_submission(body)
    except IntegrationAnalysisValidationError as error:
        return _error_response(status.HTTP_400_BAD_REQUEST, error.message)
    except IntegrationAnalysisTooManyNotamsError as error:
        return _error_response(status.HTTP_413_CONTENT_TOO_LARGE, error.message)

    response = service.submit_analysis(submission, auth.api_client_id)
    background_tasks.add_task(
        run_integration_analysis,
        response.job_id,
        submission,
    )
    return response


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=None,
)
def list_analyses(
    auth: IntegrationAuthDep,
    limit: int = Query(DEFAULT_INTEGRATION_LIST_LIMIT, ge=1, le=MAX_INTEGRATION_LIST_LIMIT),
    offset: int = Query(0, ge=0),
    status_filter: IntegrationAnalysisStatus | None = Query(None, alias="status"),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    service: IntegrationAnalysisService = Depends(get_integration_analysis_service),
) -> IntegrationAnalysisListResponse | JSONResponse:
    try:
        params = IntegrationAnalysisListParams(
            limit=limit,
            offset=offset,
            status=status_filter,
            from_=from_,
            to=to,
        )
        return service.list_analyses(params, auth.api_client_id)
    except ValueError as error:
        return _error_response(status.HTTP_400_BAD_REQUEST, str(error))


@router.get(
    "/{job_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_integration_poll)],
)
def get_analysis(
    job_id: UUID,
    auth: IntegrationAuthDep,
    service: IntegrationAnalysisService = Depends(get_integration_analysis_service),
) -> IntegrationAnalysisPollResponse:
    result = service.get_job_status(job_id, auth.api_client_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found",
        )
    return result
