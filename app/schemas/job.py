from uuid import UUID

from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    organisation_id: UUID
    flight_id: UUID
    flight_plan_id: UUID
    storage_path: str


class CreateJobResponse(BaseModel):
    id: UUID
