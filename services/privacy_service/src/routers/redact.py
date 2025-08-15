from fastapi import APIRouter
from ..schemas import RedactRequest, RedactResponse
from ..service import anonymize_transcript

router = APIRouter()

@router.post(
    "/redact",
    response_model=RedactResponse,
    summary="Redact sensitive information",
    description="Redact sensitive information from the provided text."
)
async def redact_text(payload: RedactRequest) -> RedactResponse:
    """
    Redact sensitive information from the provided text.
    
    Args:
        payload (RedactRequest): The text to be redacted.
        
    Returns:
        RedactResponse: The redacted text.
    """
    redacted_text = anonymize_transcript(payload.text)
    
    return RedactResponse(text=redacted_text)