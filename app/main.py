from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.errors import JobStepError

app = FastAPI(title="JetOps API")
app.include_router(api_router)


@app.exception_handler(JobStepError)
def job_step_error_handler(_request, exc: JobStepError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"id": str(exc.job_id)},
    )
