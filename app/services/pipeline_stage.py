from __future__ import annotations

import time
from typing import Self
from uuid import UUID

from pydantic import BaseModel
from supabase import Client

from app.schemas.pipeline_stage import StageName

# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class PipelineStageLogRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def insert_log(
        self,
        *,
        analysis_job_id: UUID,
        stage_name: str,
        duration_ms: int,
        metadata: dict,
    ) -> None:
        self._client.table("pipeline_stage_logs").insert(
            {
                "analysis_job_id": str(analysis_job_id),
                "stage_name": stage_name,
                "duration_ms": duration_ms,
                "metadata": metadata,
            }
        ).execute()


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------


class _StageTracker:
    def __init__(self, logger: PipelineStageLogger, stage_name: StageName) -> None:
        self._logger = logger
        self._stage_name = stage_name
        self.metadata: BaseModel | None = None
        self._start = 0.0

    def __enter__(self) -> Self:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_args: object) -> bool:
        if self.metadata is not None:
            duration_ms = int((time.perf_counter() - self._start) * 1000)
            self._logger.log(self._stage_name, duration_ms, self.metadata)
        return False


class PipelineStageLogger:
    def __init__(self, client: Client, analysis_job_id: UUID) -> None:
        self._analysis_job_id = analysis_job_id
        self._repository = PipelineStageLogRepository(client)

    def log(
        self,
        stage_name: StageName,
        duration_ms: int,
        metadata: BaseModel,
    ) -> None:
        try:
            self._repository.insert_log(
                analysis_job_id=self._analysis_job_id,
                stage_name=stage_name,
                duration_ms=duration_ms,
                metadata=metadata.model_dump(mode="json"),
            )
        except Exception:
            pass

    def track(self, stage_name: StageName) -> _StageTracker:
        return _StageTracker(self, stage_name)
