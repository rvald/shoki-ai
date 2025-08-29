from pydantic import BaseModel, Field
from typing import Optional

class SoapNoteRequest(BaseModel):
    text: str = Field(..., description="Redacted transcript text (no raw PHI)")
    language: Optional[str] = Field(default=None)

class SoapNoteResponse(BaseModel):
    soap_note: str = Field(..., description="SOAP note string")
    version: str = "v1"