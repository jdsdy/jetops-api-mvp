from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.api_logging import log_v1_request_middleware
from app.api.v1.router import api_router
from app.core.errors import JobStepError
from app.schemas.health import HealthResponse

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
