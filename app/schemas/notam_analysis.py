from pydantic import BaseModel, RootModel

from app.schemas.analysis_context import FlightContext
from app.schemas.notam_topic import MISC_TOPIC


class CategoryResult(BaseModel):
    notam_id: str
    category: int


class SummaryResult(BaseModel):
    notam_id: str
    summary: str


class NotamResult(BaseModel):
    notam_id: str
    category: int | None = None
    summary: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.category is not None and self.summary is not None


class AnalysisOutput(RootModel[list[NotamResult]]):
    root: list[NotamResult]


class CategoryOutput(RootModel[list[CategoryResult]]):
    root: list[CategoryResult]


class SummaryOutput(RootModel[list[SummaryResult]]):
    root: list[SummaryResult]


class SpecialistCategoryOutput(BaseModel):
    results: list[CategoryResult]
    rejected_notam_ids: list[str] = []


class SpecialistAnalysisOutput(BaseModel):
    results: list[NotamResult]
    rejected_notam_ids: list[str] = []


class AnalysisNotamRow(BaseModel):
    id: int
    title: str | None = None
    notam_id: str
    topic: str | None = None
    topic_confidence: int | None = None
    q: str | None = None
    a: str | None = None
    b: str | None = None
    c: str | None = None
    d: str | None = None
    e: str | None = None
    f: str | None = None
    g: str | None = None


class NotamBatchPayload(BaseModel):
    flight: FlightContext
    notams: list[AnalysisNotamRow]
    topic: str = MISC_TOPIC


class SummaryBatchPayload(BaseModel):
    notams: list[AnalysisNotamRow]


class BatchCallStats(BaseModel):
    duration_ms: int
    input_tokens: int
    output_tokens: int
    batch_size: int


class CategoryBatchResult(BaseModel):
    results: list[CategoryResult]
    batch_stats: list[BatchCallStats]
    model: str
    token_limit_hit: bool
    missing_notam_ids: list[str] = []
    rejected_notam_ids: list[str] = []

    @property
    def batches(self) -> int:
        return len(self.batch_stats)

    @property
    def notams_analysed(self) -> int:
        return len(self.results)

    @property
    def batch_sizes(self) -> list[int]:
        return [stat.batch_size for stat in self.batch_stats]

    @property
    def slowest_batch_ms(self) -> int:
        return max((stat.duration_ms for stat in self.batch_stats), default=0)

    @property
    def input_tokens(self) -> int:
        return sum(stat.input_tokens for stat in self.batch_stats)

    @property
    def output_tokens(self) -> int:
        return sum(stat.output_tokens for stat in self.batch_stats)


class SummaryBatchResult(BaseModel):
    results: list[SummaryResult]
    batch_stats: list[BatchCallStats]
    model: str
    token_limit_hit: bool
    missing_notam_ids: list[str] = []

    @property
    def batches(self) -> int:
        return len(self.batch_stats)

    @property
    def notams_summarized(self) -> int:
        return len(self.results)

    @property
    def batch_sizes(self) -> list[int]:
        return [stat.batch_size for stat in self.batch_stats]

    @property
    def slowest_batch_ms(self) -> int:
        return max((stat.duration_ms for stat in self.batch_stats), default=0)

    @property
    def input_tokens(self) -> int:
        return sum(stat.input_tokens for stat in self.batch_stats)

    @property
    def output_tokens(self) -> int:
        return sum(stat.output_tokens for stat in self.batch_stats)


class BatchAnalysisResult(BaseModel):
    """Backward-compatible aggregate used by metadata helpers and legacy tests."""

    results: list[NotamResult]
    batch_stats: list[BatchCallStats]
    model: str
    token_limit_hit: bool
    missing_notam_ids: list[str] = []
    rejected_notam_ids: list[str] = []

    @property
    def batches(self) -> int:
        return len(self.batch_stats)

    @property
    def notams_analysed(self) -> int:
        return len(self.results)

    @property
    def batch_sizes(self) -> list[int]:
        return [stat.batch_size for stat in self.batch_stats]

    @property
    def slowest_batch_ms(self) -> int:
        return max((stat.duration_ms for stat in self.batch_stats), default=0)

    @property
    def input_tokens(self) -> int:
        return sum(stat.input_tokens for stat in self.batch_stats)

    @property
    def output_tokens(self) -> int:
        return sum(stat.output_tokens for stat in self.batch_stats)


class AnalysisJobResult(BaseModel):
    results: list[NotamResult]
    category_result: CategoryBatchResult
    summary_result: SummaryBatchResult
    heuristic_category_count: int = 0

    @property
    def missing_category_notam_ids(self) -> list[str]:
        return self.category_result.missing_notam_ids

    @property
    def missing_summary_notam_ids(self) -> list[str]:
        return self.summary_result.missing_notam_ids

    @property
    def rejected_notam_ids(self) -> list[str]:
        return self.category_result.rejected_notam_ids

    @property
    def token_limit_hit(self) -> bool:
        return (
            self.category_result.token_limit_hit
            or self.summary_result.token_limit_hit
        )
