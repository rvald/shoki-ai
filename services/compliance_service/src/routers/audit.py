from fastapi import APIRouter
from ..schemas import AuditRequest, AuditResponse
from ..service import generate_audit

router = APIRouter()

@router.post(
    "/audit",
    response_model=AuditResponse,
    summary="Audit transcript",
    description="Return the provided transcript for compliance auditing."
)
async def audit_request(payload: AuditRequest) -> AuditResponse:
    response = generate_audit(
        transcript=payload.transcript,
        model_name="gpt-oss"
    )
    return AuditResponse(audit=response)