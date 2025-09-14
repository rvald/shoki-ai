from typing import Optional

from anyio import to_thread
from fastapi import APIRouter, Header, HTTPException, status

from ..exceptions import PermanentError, RetryableError
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
        # Offload to a worker thread so we don't block the event loop
        return await to_thread.run_sync(
            generate_soap_with_idempotency, payload, x_correlation_id, x_idempotency_key, x_simulate_failure
        )
    except RetryableError as e:
        jlog(
            event="soap_failed",
            retryable=True,
            error=str(e),
            correlation_id=x_correlation_id,
            idempotency_key=x_idempotency_key,
        )
        # Upstream (orchestrator) should treat 503 as retryable
        raise HTTPException(status_code=503, detail=str(e))
    except PermanentError as e:
        jlog(
            event="soap_failed",
            retryable=False,
            error=str(e),
            correlation_id=x_correlation_id,
            idempotency_key=x_idempotency_key,
        )
        raise HTTPException(status_code=422, detail=str(e))