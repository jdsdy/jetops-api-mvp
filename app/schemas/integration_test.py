from pydantic import BaseModel


class IntegrationTestResponse(BaseModel):
    status: str
