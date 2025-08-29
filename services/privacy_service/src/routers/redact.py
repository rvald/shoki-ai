from fastapi import APIRouter, Header, HTTPException, status
from ..schemas import RedactRequest, RedactResponse
from ..service import redact_with_idempotency
from ..exceptions import RetryableError, PermanentError
from ..logging import jlog

router = APIRouter()

@router.post(
    "/redact",
    response_model=RedactResponse,
    summary="Redact sensitive information",
    status_code=status.HTTP_200_OK,
)
async def redact_text(
    payload: RedactRequest,
    x_correlation_id: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None),
    x_simulate_failure: str | None = Header(default=None),
) -> RedactResponse:
    try:
        return redact_with_idempotency(payload, x_correlation_id, x_idempotency_key, x_simulate_failure)
    except RetryableError as e:
        jlog(event="redact_failed", retryable=True, error=str(e),
             correlation_id=x_correlation_id, idempotency_key=x_idempotency_key)
        # Orchestrator should treat 503 as retryable
        raise HTTPException(status_code=503, detail=str(e))
    except PermanentError as e:
        jlog(event="redact_failed", retryable=False, error=str(e),
             correlation_id=x_correlation_id, idempotency_key=x_idempotency_key)
        raise HTTPException(status_code=422, detail=str(e))