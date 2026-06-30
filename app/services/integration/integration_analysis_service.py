from datetime import datetime
from uuid import UUID

from app.repositories.analysed_notam_repository import AnalysedNotamRepository
from app.repositories.job_repository import ACCEPTED, JobRepository
from app.schemas.integration_analysis import (
    IntegrationAnalysisError,
    IntegrationAnalysisListJobFlight,
    IntegrationAnalysisListJobItem,
    IntegrationAnalysisListJobSummary,
    IntegrationAnalysisListPagination,
    IntegrationAnalysisListParams,
    IntegrationAnalysisListResponse,
    IntegrationAnalysisNotamResult,
    IntegrationAnalysisPollResponse,
    IntegrationAnalysisRequest,
    IntegrationAnalysisResult,
    IntegrationAnalysisResultSummary,
    IntegrationAnalysisStage,
    IntegrationAnalysisStatus,
    IntegrationAnalysisSubmitResponse,
    IntegrationErrorCode,
)


def build_poll_url(job_id: UUID) -> str:
    return f"/v1/analysis/{job_id}"


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _build_result_summary(
    notams: list[IntegrationAnalysisNotamResult],
) -> IntegrationAnalysisResultSummary:
    priority_1 = sum(1 for notam in notams if notam.category == 1)
    priority_2 = sum(1 for notam in notams if notam.category == 2)
    priority_3 = sum(1 for notam in notams if notam.category == 3)
    return IntegrationAnalysisResultSummary(
        total_notams=len(notams),
        priority_1=priority_1,
        priority_2=priority_2,
        priority_3=priority_3,
    )


class IntegrationAnalysisService:
    def __init__(
        self,
        job_repository: JobRepository,
        analysed_notam_repository: AnalysedNotamRepository | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._analysed_notam_repository = analysed_notam_repository

    def submit_analysis(
        self,
        request: IntegrationAnalysisRequest,
        api_client_id: UUID,
    ) -> IntegrationAnalysisSubmitResponse:
        job_id, started_at = self._job_repository.create_integration_job(
            api_client_id=api_client_id,
            status=ACCEPTED,
            departure_icao=request.flight.departure_airfield.icao,
            arrival_icao=request.flight.arrival_airfield.icao,
        )
        return IntegrationAnalysisSubmitResponse(
            job_id=job_id,
            status=IntegrationAnalysisStatus.ACCEPTED,
            poll_url=build_poll_url(job_id),
            started_at=started_at,
        )

    def get_job_status(
        self,
        job_id: UUID,
        api_client_id: UUID,
    ) -> IntegrationAnalysisPollResponse | None:
        job = self._job_repository.get_integration_job(job_id)
        if job is None:
            return None
        if job.get("api_client_id") != str(api_client_id):
            return None

        status = IntegrationAnalysisStatus(str(job["status"]))
        started_at = _parse_timestamp(job.get("started_at"))
        if started_at is None:
            raise ValueError("Integration job missing started_at")

        response = IntegrationAnalysisPollResponse(
            job_id=UUID(str(job["id"])),
            status=status,
            started_at=started_at,
        )

        if status == IntegrationAnalysisStatus.PROCESSING:
            stage_value = job.get("stage")
            if stage_value is not None:
                response.stage = IntegrationAnalysisStage(str(stage_value))
            return response

        if status == IntegrationAnalysisStatus.ACCEPTED:
            return response

        completed_at = _parse_timestamp(job.get("completed_at"))
        response.completed_at = completed_at

        if status == IntegrationAnalysisStatus.COMPLETE:
            stage_value = job.get("stage")
            if stage_value is not None:
                response.stage = IntegrationAnalysisStage(str(stage_value))
            if self._analysed_notam_repository is None:
                raise RuntimeError("AnalysedNotamRepository required for complete jobs")
            rows = self._analysed_notam_repository.fetch_integration_results(job_id)
            notams = [
                IntegrationAnalysisNotamResult(
                    notam_id=row["notam_id"],
                    category=row["category"],
                    summary=row["summary"],
                )
                for row in rows
            ]
            response.result = IntegrationAnalysisResult(
                summary=_build_result_summary(notams),
                notams=notams,
            )
            return response

        if status == IntegrationAnalysisStatus.FAILED:
            error_code = job.get("error_code") or IntegrationErrorCode.INTERNAL_ERROR
            error_message = job.get("error_message") or "Analysis failed"
            response.error = IntegrationAnalysisError(
                code=IntegrationErrorCode(str(error_code)),
                message=str(error_message),
            )
            return response

        return response

    def list_analyses(
        self,
        params: IntegrationAnalysisListParams,
        api_client_id: UUID,
    ) -> IntegrationAnalysisListResponse:
        if (
            params.from_ is not None
            and params.to is not None
            and params.from_ > params.to
        ):
            raise ValueError("from must be before or equal to to")

        rows, total = self._job_repository.list_integration_jobs(
            api_client_id=api_client_id,
            limit=params.limit,
            offset=params.offset,
            status=params.status.value if params.status is not None else None,
            started_from=params.from_,
            started_to=params.to,
        )

        jobs: list[IntegrationAnalysisListJobItem] = []
        for row in rows:
            submitted_at = _parse_timestamp(row.get("started_at"))
            if submitted_at is None:
                raise ValueError("Integration job missing started_at")

            departure_icao = row.get("departure_icao")
            arrival_icao = row.get("arrival_icao")
            if not departure_icao or not arrival_icao:
                raise ValueError("Integration job missing departure or arrival ICAO")

            status = IntegrationAnalysisStatus(str(row["status"]))
            item = IntegrationAnalysisListJobItem(
                job_id=UUID(str(row["id"])),
                status=status,
                submitted_at=submitted_at,
                completed_at=_parse_timestamp(row.get("completed_at")),
                flight=IntegrationAnalysisListJobFlight(
                    departure_icao=str(departure_icao),
                    arrival_icao=str(arrival_icao),
                ),
            )
            if status == IntegrationAnalysisStatus.COMPLETE:
                total_notams = row.get("total_notams")
                if total_notams is not None:
                    item.summary = IntegrationAnalysisListJobSummary(
                        total_notams=int(total_notams),
                        category_1=int(row.get("cat1_notams") or 0),
                        category_2=int(row.get("cat2_notams") or 0),
                        category_3=int(row.get("cat3_notams") or 0),
                    )
            jobs.append(item)

        return IntegrationAnalysisListResponse(
            jobs=jobs,
            pagination=IntegrationAnalysisListPagination(
                total=total,
                limit=params.limit,
                offset=params.offset,
            ),
        )
