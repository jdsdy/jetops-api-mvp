from pydantic import BaseModel, RootModel

from app.schemas.analysis_context import FlightContext
from app.schemas.notam_topic import MISC_TOPIC


class NotamResult(BaseModel):
    notam_id: str
    category: int
    summary: str


class AnalysisOutput(RootModel[list[NotamResult]]):
    root: list[NotamResult]


class AnalysisNotamRow(BaseModel):
    id: int
    title: str | None = None
    notam_id: str
    topic: str | None = None
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


class BatchCallStats(BaseModel):
    duration_ms: int
    input_tokens: int
    output_tokens: int
    batch_size: int


class BatchAnalysisResult(BaseModel):
    results: list[NotamResult]
    batch_stats: list[BatchCallStats]
    model: str
    token_limit_hit: bool
    missing_notam_ids: list[str] = []

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
