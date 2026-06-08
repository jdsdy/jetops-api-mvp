from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

PlanSource = Literal["foreflight", "naips"]


class FlightData(BaseModel):
    departure_icao: str
    arrival_icao: str
    planned_dept_time: datetime | None
    planned_arr_time: datetime | None
    route: str
    cruise_level: str
    alt_icao: str | None
    source_app: PlanSource
