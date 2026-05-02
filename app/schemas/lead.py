from pydantic import BaseModel, Field, field_validator


class SearchGlobalIn(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    country: str = Field(default="", max_length=80)
    sector: str = Field(default="", max_length=120)
    limit: int = Field(default=10, ge=1, le=50)
    min_confidence: float = Field(default=0.32, ge=0.05, le=0.95)


class CompanySearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    country: str = Field(default="", max_length=80)
    sector: str = Field(default="", max_length=120)
    limit: int = Field(default=10, ge=1, le=50)


class AnalyzeCompanyIn(BaseModel):
    website: str = Field(min_length=5, max_length=500)

    @field_validator("website")
    @classmethod
    def strip_website(cls, v: str) -> str:
        s = (v or "").strip()
        if not s.startswith(("http://", "https://")):
            s = "https://" + s
        return s[:500]


class ScoreLeadIn(BaseModel):
    website: str = ""
    description: str = ""
    sector: str = ""
    size_estimate: str = ""
    international_presence: int = Field(default=0, ge=0, le=50)
    has_corporate_email: bool = False
    has_phone: bool = False


class LeadTemperatureIn(BaseModel):
    temperature: str = Field(min_length=3, max_length=4)

    @field_validator("temperature")
    @classmethod
    def upper_temp(cls, v: str) -> str:
        t = (v or "").strip().upper()
        if t not in ("HOT", "WARM", "COLD"):
            raise ValueError("temperature must be HOT, WARM or COLD")
        return t


class LeadItemOut(BaseModel):
    id: int
    company_name: str
    website: str
    score: int
    classification: str
    temperature: str
    sector: str
    country: str
    contact_email: str
    contact_phone: str
