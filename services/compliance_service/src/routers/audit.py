from typing import Optional

from anyio import to_thread
from fastapi import APIRouter, Header, HTTPException, status

from ..exceptions import PermanentError, RetryableError
from ..logging import jlog
from ..schemas import AuditRequest, AuditResponse
from ..service import generate_audit_with_idempotency

router = APIRouter()

@router.post(
    "/audit",
    response_model=AuditResponse,
    summary="Audit redacted transcript for HIPAA compliance",
    status_code=status.HTTP_200_OK,
)
async def audit_request(
    payload: AuditRequest,
    x_correlation_id: Optional[str] = Header(default=None),
    x_idempotency_key: Optional[str] = Header(default=None),
) -> AuditResponse:
    try:
        # Offload to worker thread so we don't block event loop
        return await to_thread.run_sync(
            generate_audit_with_idempotency, payload, x_correlation_id, x_idempotency_key
        )
    except RetryableError as e:
        jlog(event="audit_failed", retryable=True, error=str(e), correlation_id=x_correlation_id, idempotency_key=x_idempotency_key)
        raise HTTPException(status_code=503, detail=str(e))
    except PermanentError as e:
        jlog(event="audit_failed", retryable=False, error=str(e), correlation_id=x_correlation_id, idempotency_key=x_idempotency_key)
        raise HTTPException(status_code=422, detail=str(e))