from pydantic import ValidationError

from app.core.errors import (
    IntegrationAnalysisTooManyNotamsError,
    IntegrationAnalysisValidationError,
)
from app.schemas.integration_analysis import (
    MAX_INTEGRATION_NOTAMS,
    IntegrationAnalysisRequest,
)


def _format_validation_errors(error: ValidationError) -> str:
    messages: list[str] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        messages.append(f"{location}: {item['msg']}")
    return "; ".join(messages)


def validate_and_normalize_analysis_submission(
    payload: object,
) -> IntegrationAnalysisRequest:
    try:
        request = IntegrationAnalysisRequest.model_validate(payload)
    except ValidationError as error:
        raise IntegrationAnalysisValidationError(
            _format_validation_errors(error)
        ) from error

    if len(request.notams) > MAX_INTEGRATION_NOTAMS:
        raise IntegrationAnalysisTooManyNotamsError(
            f"NOTAM limit exceeded (max {MAX_INTEGRATION_NOTAMS})"
        )

    return request
