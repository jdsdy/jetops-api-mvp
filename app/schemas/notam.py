from pydantic import BaseModel


class RawNotam(BaseModel):
    notam_id: str
    title: str | None = None
    q: str | None = None
    a: str | None = None
    b: str | None = None
    c: str | None = None
    d: str | None = None
    e: str | None = None
    f: str | None = None
    g: str | None = None
