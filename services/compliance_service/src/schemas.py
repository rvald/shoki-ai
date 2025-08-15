from pydantic import BaseModel, Field

class AuditRequest(BaseModel):
    transcript: str = Field(..., min_length=1, description="Transcript text to audit")

class AuditResponse(BaseModel):
    audit: str