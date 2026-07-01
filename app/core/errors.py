from uuid import UUID


def extract_error_message(error: BaseException) -> str:
    message = getattr(error, "message", None)
    if message is not None:
        return str(message)
    return str(error)


class JobStepError(Exception):
    def __init__(self, job_id: UUID, status_code: int, message: str) -> None:
        self.job_id = job_id
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class IntegrationAnalysisValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class IntegrationAnalysisTooManyNotamsError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
