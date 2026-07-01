from datetime import UTC, datetime
from uuid import UUID

import anthropic

from app.core.errors import extract_error_message
from app.core.supabase import get_supabase_client
from app.repositories.analysed_notam_repository import AnalysedNotamRepository
from app.repositories.job_repository import (
    COMPLETE,
    FAILED,
    PROCESSING,
    JobRepository,
)
from app.repositories.notam_repository import NotamRepository
from app.schemas.integration_analysis import (
    IntegrationAnalysisRequest,
    IntegrationAnalysisStage,
    IntegrationAnalysisStatus,
    IntegrationErrorCode,
    IntegrationNotamRequest,
)
from app.schemas.notam import RawNotam
from app.schemas.notam_analysis import AnalysisNotamRow, NotamResult
from app.schemas.notam_topic import MISC_TOPIC, ClassificationResult
from app.schemas.pipeline_stage import (
    build_context_object_metadata,
    build_notam_topic_classification_metadata,
)
from app.services.analysis.analysis_context import build_flight_context_from_integration
from app.services.analysis.analysis_task import execute_notam_analysis_with_retries
from app.services.extraction.notam_topic_classifier import classify_notam
from app.services.pipeline.pipeline_stage import PipelineStageLogger


def _integration_notam_to_raw(notam: IntegrationNotamRequest) -> RawNotam:
    return RawNotam(
        notam_id=notam.id,
        title=notam.title,
        q=notam.q,
        a=notam.a,
        b=notam.b,
        c=notam.c,
        d=notam.d,
        e=notam.e,
        f=notam.f,
        g=notam.g,
    )


def _classify_notams(
    notams: list[RawNotam],
) -> tuple[list[tuple[RawNotam, ClassificationResult]], int]:
    classified: list[tuple[RawNotam, ClassificationResult]] = []
    classification_errors = 0
    for notam in notams:
        try:
            classification = classify_notam(notam)
        except Exception:
            classification = ClassificationResult(topic=MISC_TOPIC, confidence=0)
            classification_errors += 1
        classified.append((notam, classification))
    return classified, classification_errors


def _build_notam_rows_from_classified(
    classified: list[tuple[RawNotam, ClassificationResult]],
) -> list[AnalysisNotamRow]:
    rows: list[AnalysisNotamRow] = []
    for index, (notam, classification) in enumerate(classified, start=1):
        rows.append(
            AnalysisNotamRow(
                id=index,
                title=notam.title,
                notam_id=notam.notam_id,
                topic=classification.topic,
                topic_confidence=classification.confidence,
                q=notam.q,
                a=notam.a,
                b=notam.b,
                c=notam.c,
                d=notam.d,
                e=notam.e,
                f=notam.f,
                g=notam.g,
            )
        )
    return rows


def _map_integration_error_code(error: BaseException) -> IntegrationErrorCode:
    if isinstance(error, anthropic.APIError):
        return IntegrationErrorCode.ANALYSIS_ERROR
    module = type(error).__module__
    if module.startswith("anthropic"):
        return IntegrationErrorCode.ANALYSIS_ERROR
    return IntegrationErrorCode.INTERNAL_ERROR


def _completed_notam_counts(
    results: list[NotamResult],
    errored_temp_ids: set[int],
    notam_rows: list[AnalysisNotamRow],
) -> tuple[int, int, int, int]:
    errored_notam_ids = {
        row.notam_id for row in notam_rows if row.id in errored_temp_ids
    }
    complete_results = [
        result
        for result in results
        if result.is_complete and result.notam_id not in errored_notam_ids
    ]
    return (
        len(complete_results),
        sum(1 for result in complete_results if result.category == 1),
        sum(1 for result in complete_results if result.category == 2),
        sum(1 for result in complete_results if result.category == 3),
    )


def _persist_analysed_results(
    job_id: UUID,
    raw_id_by_notam_id: dict[str, int],
    job_results: list[NotamResult],
    errored_temp_ids: set[int],
    notam_rows: list[AnalysisNotamRow],
) -> None:
    errored_notam_ids = {
        row.notam_id for row in notam_rows if row.id in errored_temp_ids
    }
    analysed_repository = AnalysedNotamRepository(get_supabase_client())
    persist_rows: list[tuple[int, NotamResult | None]] = []

    for result in job_results:
        if result.notam_id in errored_notam_ids:
            continue
        if not result.is_complete:
            continue
        raw_id = raw_id_by_notam_id.get(result.notam_id)
        if raw_id is None:
            continue
        persist_rows.append((raw_id, result))

    if persist_rows:
        analysed_repository.insert_analysed_notams(job_id, None, persist_rows)


def run_integration_analysis(
    job_id: UUID,
    submission: IntegrationAnalysisRequest,
) -> None:
    client = get_supabase_client()
    job_repository = JobRepository(client)
    notam_repository = NotamRepository(client)
    stage_logger = PipelineStageLogger(client, job_id)

    try:
        job_repository.update_integration_job(
            job_id,
            status=PROCESSING,
            stage=IntegrationAnalysisStage.TOPIC_IDENTIFICATION,
        )

        raw_notams = [_integration_notam_to_raw(notam) for notam in submission.notams]
        classified, classification_errors = _classify_notams(raw_notams)
        notam_rows = _build_notam_rows_from_classified(classified)
        flight = build_flight_context_from_integration(submission.flight)

        with stage_logger.track("notam_topic_classification") as topic_stage:
            topic_metadata = build_notam_topic_classification_metadata(
                [
                    (row.id, row.topic or MISC_TOPIC, row.topic_confidence or 0)
                    for row in notam_rows
                ],
                classification_errors=classification_errors,
            )
            topic_stage.metadata = topic_metadata

        with stage_logger.track("build_context_object") as ctx_stage:
            ctx_stage.metadata = build_context_object_metadata(flight)

        job_repository.update_integration_job(
            job_id,
            stage=IntegrationAnalysisStage.CLASSIFICATION,
        )

        def _on_retry() -> None:
            job_repository.update_integration_job(
                job_id,
                stage=IntegrationAnalysisStage.RETRY,
            )

        with stage_logger.track("notam_analysis") as analysis_stage:
            job_result, analysis_metadata, errored_temp_ids = (
                execute_notam_analysis_with_retries(
                    flight,
                    notam_rows,
                    on_retry=_on_retry,
                )
            )
            analysis_stage.metadata = analysis_metadata

        inserted_raw = notam_repository.insert_classified_notams(
            job_id,
            None,
            classified,
        )
        raw_id_by_notam_id = {
            row["notam_id"]: int(row["id"]) for row in inserted_raw
        }

        _persist_analysed_results(
            job_id,
            raw_id_by_notam_id,
            job_result.results,
            set(errored_temp_ids),
            notam_rows,
        )

        total_notams, cat1_notams, cat2_notams, cat3_notams = _completed_notam_counts(
            job_result.results,
            set(errored_temp_ids),
            notam_rows,
        )

        job_repository.update_integration_job(
            job_id,
            status=COMPLETE,
            stage=IntegrationAnalysisStage.COMPLETE,
            completed_at=datetime.now(UTC),
            total_notams=total_notams,
            cat1_notams=cat1_notams,
            cat2_notams=cat2_notams,
            cat3_notams=cat3_notams,
        )
    except Exception as error:
        error_code = _map_integration_error_code(error)
        job_repository.update_integration_job(
            job_id,
            status=FAILED,
            error_code=error_code,
            error_message=extract_error_message(error),
            completed_at=datetime.now(UTC),
            clear_stage=True,
        )
