from fastapi import APIRouter, Header, HTTPException, status

from ..exceptions import PermanentError, RetryableError
from ..logging import jlog
from ..schemas import RedactRequest, RedactResponse
from ..service import redact_with_idempotency

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
        # Offload to worker thread so we don't block event loop
        from anyio import to_thread
        return await to_thread.run_sync(
            redact_with_idempotency, payload, x_correlation_id, x_idempotency_key
        )
    except RetryableError as e:
        jlog(
            event="redact_failed",
            retryable=True,
            error=str(e),
            correlation_id=x_correlation_id,
            idempotency_key=x_idempotency_key,
        )
        raise HTTPException(status_code=503, detail=str(e))
    except PermanentError as e:
        jlog(
            event="redact_failed",
            retryable=False,
            error=str(e),
            correlation_id=x_correlation_id,
            idempotency_key=x_idempotency_key,
        )
        raise HTTPException(status_code=422, detail=str(e))