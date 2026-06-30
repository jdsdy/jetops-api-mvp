from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.api_logging import log_v1_request_middleware
from app.api.v1.router import api_router
from app.core.errors import (
    IntegrationAnalysisTooManyNotamsError,
    IntegrationAnalysisValidationError,
    JobStepError,
)
from app.schemas.health import HealthResponse
from app.schemas.integration_analysis import IntegrationErrorCode

app = FastAPI(title="JetOps API")
app.middleware("http")(log_v1_request_middleware)
app.include_router(api_router)


@app.get("/health", status_code=200)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.exception_handler(JobStepError)
def job_step_error_handler(request: Request, exc: JobStepError) -> JSONResponse:
    request.state.error_message = exc.message
    return JSONResponse(
        status_code=exc.status_code,
        content={"id": str(exc.job_id)},
    )


@app.exception_handler(IntegrationAnalysisValidationError)
def integration_analysis_validation_error_handler(
    request: Request,
    exc: IntegrationAnalysisValidationError,
) -> JSONResponse:
    request.state.error_message = exc.message
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": IntegrationErrorCode.INVALID_REQUEST_FORMAT,
                "message": exc.message,
            }
        },
    )


@app.exception_handler(IntegrationAnalysisTooManyNotamsError)
def integration_analysis_too_many_notams_error_handler(
    request: Request,
    exc: IntegrationAnalysisTooManyNotamsError,
) -> JSONResponse:
    request.state.error_message = exc.message
    return JSONResponse(
        status_code=413,
        content={
            "error": {
                "code": IntegrationErrorCode.INVALID_REQUEST_FORMAT,
                "message": exc.message,
            }
        },
    )
