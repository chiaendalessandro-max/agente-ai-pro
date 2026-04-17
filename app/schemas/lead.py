from pydantic import BaseModel, Field


class SearchGlobalIn(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    country: str = Field(default="", max_length=80)
    sector: str = Field(default="", max_length=120)
    limit: int = Field(default=10, ge=1, le=50)


class AnalyzeCompanyIn(BaseModel):
    website: str = Field(min_length=5, max_length=500)


class ScoreLeadIn(BaseModel):
    website: str = ""
    description: str = ""
    sector: str = ""
    size_estimate: str = ""
    international_presence: int = 0
    has_corporate_email: bool = False
    has_phone: bool = False


class LeadItemOut(BaseModel):
    id: int
    company_name: str
    website: str
    score: int
    classification: str
    sector: str
    country: str
    contact_email: str
    contact_phone: str
