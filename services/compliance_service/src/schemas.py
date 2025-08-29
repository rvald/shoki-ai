from typing import List
from pydantic import BaseModel, Field

class FailIdentifier(BaseModel):
    type: str = Field(..., description="HIPAA identifier category")
    text: str = Field(..., description="The matched text (redacted upstream; include masked token)")
    position: str = Field(..., description="Location hint, e.g., 'segment 3, token 12'")

class AuditRequest(BaseModel):
    # IMPORTANT: This must be redacted text. Do not send raw PHI.
    transcript: str = Field(..., description="Redacted transcript text (no raw PHI)")

class AuditResponse(BaseModel):
    hipaa_compliant: bool
    fail_identifiers: List[FailIdentifier] = []
    comments: str = ""
    version: str = "v1"