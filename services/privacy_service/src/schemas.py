from typing import Dict, Optional
from pydantic import BaseModel, Field

class RedactRequest(BaseModel):
    bucket: str = Field(..., description="GCS bucket where transcription artifact is stored")
    idem_key: str = Field(..., description="Key to use when fetching transcription artifact")
    language: Optional[str] = Field(default="en")
    policy: Optional[str] = Field(default="HIPAA Safe Harbor + extras")
    stable_masking: Optional[bool] = Field(default=True)

class RedactionSummary(BaseModel):
    entities: Dict[str, int] = Field(default_factory=dict)
    total: int = 0
    policy: Optional[str] = None

class RedactResponse(BaseModel):
    text: str = Field(..., description="Redacted text")
    summary: RedactionSummary = Field(default_factory=RedactionSummary)
    version: str = "v1"