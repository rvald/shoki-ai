from fastapi import FastAPI, APIRouter
from pydantic import BaseModel, Field
from . import audit_generation

router = APIRouter()

class ComplianceRequest(BaseModel):
    transcript: str = Field(..., min_length=1, description="Transcript text to audit")

class ComplianceResponse(BaseModel):
    audit: str

@router.post(
    "/audit",
    response_model=ComplianceResponse,
    summary="Audit transcript",
    description="Return the provided transcript for compliance auditing."
)
async def audit_request(payload: ComplianceRequest) -> ComplianceResponse:
    response = audit_generation.generate_audit(
        transcript=payload.transcript,
        model_name="deepseek-r1:7b"
    )
    return ComplianceResponse(audit=response)

app = FastAPI(title="Compliance API", version="1.0.0")
app.include_router(router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)