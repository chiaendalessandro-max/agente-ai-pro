from pydantic import BaseModel


class EmailDraftOut(BaseModel):
    id: int
    status: str
    subject: str
    body: str
    error: str
