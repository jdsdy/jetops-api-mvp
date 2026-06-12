from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

PlanSource = Literal["foreflight", "naips", "ozrunways"]


class FlightData(BaseModel):
    departure_icao: str
    arrival_icao: str
    planned_dept_time: datetime | None
    planned_arr_time: datetime | None
    route: str | None = None
    cruise_level: str | None = None
    alt_icao: str | None
    source_app: PlanSource
