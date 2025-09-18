from typing import List, Literal
from pydantic import BaseModel, Field, ConfigDict

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

class IssueFound(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    # Use alias to preserve the exact field name "type" in JSON
    type_: str = Field(..., alias="type", description="HIPAA identifier type (e.g., name, address, date, phone)")
    text: str = Field(..., description="Exact offending text as it appears in the transcript")
    position: str = Field(..., description="Character indices (start-end) or a clear descriptive location")
    rule: str = Field(..., description="Specific Safe Harbor rule violated")
    source: Literal["audit", "rescanned", "both"] = Field(..., description="Origin of detection")
    confidence: Literal["high", "medium", "low"] = Field(..., description="Confidence in the detection")


class RemediationStep(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    before: str = Field(..., description="Original snippet containing PHI")
    after: str = Field(..., description="Redacted or generalized replacement")
    # Use alias to preserve the exact field name "type" in JSON
    type_: str = Field(..., alias="type", description="HIPAA identifier type for the repaired item")
    position: str = Field(..., description="Character indices (start-end) or a clear descriptive location")
    rule: str = Field(..., description="Specific Safe Harbor rule applied")


class HipaaRemediationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    compliance_before: Literal["true", "false", "unknown"] = Field(..., description="Compliance status prior to remediation")
    audit_summary: str = Field(..., description="One-paragraph summary of the audit and implications")
    issues_found: List[IssueFound] = Field(default_factory=list, description="Merged/deduplicated list of detected PHI issues")
    remediation_steps: List[RemediationStep] = Field(default_factory=list, description="List of repairs applied to the transcript")
    transcript_sanitized: str = Field(..., description="Final HIPAA-compliant transcript text")
    compliance_after: bool = Field(..., description="True if sanitized transcript is HIPAA-compliant")
    comments: str = Field(..., description="Brief notes on trade-offs, residual risk, and SOAP guidance")