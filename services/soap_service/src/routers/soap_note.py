from fastapi import APIRouter
from ..schemas import SoapNoteRequest, SoapNoteRequestResponse
from ..service import generate_soap_note

router = APIRouter()

@router.post(
    "/soap_note",
    response_model=SoapNoteRequestResponse,
    summary="Generate SOAP note from transcript",
    description="Generates a soap note from the redacted transcript."
)
async def soap_note(payload: SoapNoteRequest) -> SoapNoteRequestResponse:
    response = generate_soap_note(
        transcript=payload.text,
        model_name="gpt-oss"
    )
    return SoapNoteRequestResponse(soap_note=response)