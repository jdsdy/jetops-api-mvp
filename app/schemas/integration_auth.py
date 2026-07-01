from uuid import UUID

from pydantic import BaseModel


class IntegrationAuthContext(BaseModel):
    api_key_id: UUID
    api_client_id: UUID
    organisation_id: UUID | None
