from fastapi import APIRouter, Header, HTTPException, status
from typing import Optional

from ..exceptions import RetryableError, PermanentError
from ..logging import jlog

from ..schemas import SoapNoteRequest, SoapNoteResponse
from ..service import generate_soap_with_idempotency

router = APIRouter()

@router.post(
    "/soap_note",
    response_model=SoapNoteResponse,
    summary="Generate SOAP note from redacted text",
    status_code=status.HTTP_200_OK,
)
async def soap_note(
    payload: SoapNoteRequest,
    x_correlation_id: Optional[str] = Header(default=None),
    x_idempotency_key: Optional[str] = Header(default=None),
    x_simulate_failure: Optional[str] = Header(default=None),
) -> SoapNoteResponse:
    try:
        return generate_soap_with_idempotency(payload, x_correlation_id, x_idempotency_key, x_simulate_failure)
    except RetryableError as e:
        jlog(event="soap_failed", retryable=True, error=str(e),
             correlation_id=x_correlation_id, idempotency_key=x_idempotency_key)
        # Orchestrator should treat 503 as retryable
        raise HTTPException(status_code=503, detail=str(e))
    except PermanentError as e:
        jlog(event="soap_failed", retryable=False, error=str(e),
             correlation_id=x_correlation_id, idempotency_key=x_idempotency_key)
        raise HTTPException(status_code=422, detail=str(e))