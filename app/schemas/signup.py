from pydantic import BaseModel


class VerifySignupCodeRequest(BaseModel):
    code: str
