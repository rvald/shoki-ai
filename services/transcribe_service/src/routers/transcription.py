import os
from fastapi import APIRouter, Header, HTTPException, status
from ..schemas import TranscriptionRequest, TranscriptionResponse
from ..service import transcribe_with_idempotency, derive_idempotency_key
from ..exceptions import RetryableError, PermanentError
from ..logging import jlog

router = APIRouter()

@router.post(  
    "/transcribe_audio",
    response_model=TranscriptionResponse,
    summary="Transcribe audio file",
    description="Transcribe an audio file stored in GCP Cloud Storage.",
    status_code=status.HTTP_200_OK
)

async def transcribe_audio_endpoint(
    payload: TranscriptionRequest,
    x_correlation_id: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None),
    x_simulate_failure: str | None = Header(default=None)
) -> TranscriptionResponse:
    # Basic input validation
    if not payload.audio_file_name:
        raise HTTPException(status_code=400, detail="audio_file_name is required")

    idem = derive_idempotency_key(x_idempotency_key, payload.bucket, payload.audio_file_name, payload.generation)

    try:
        return transcribe_with_idempotency(payload, x_correlation_id, idem, simulate_mode=x_simulate_failure)
    except RetryableError as e:
        jlog(event="transcribe_failed", retryable=True, error=str(e),
             correlation_id=x_correlation_id, idempotency_key=idem)
        # Orchestrator should treat 503 as retryable
        raise HTTPException(status_code=503, detail=str(e))
    except PermanentError as e:
        jlog(event="transcribe_failed", retryable=False, error=str(e),
             correlation_id=x_correlation_id, idempotency_key=idem)
        raise HTTPException(status_code=422, detail=str(e))
