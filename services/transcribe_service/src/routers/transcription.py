from fastapi import APIRouter, Header, HTTPException, status
from anyio import to_thread, run
from ..exceptions import PermanentError, RetryableError
from ..logging import jlog
from ..schemas import TranscriptionRequest, TranscriptionResponse
from ..service import derive_idempotency_key, transcribe_with_idempotency

router = APIRouter()

@router.post(
    "/transcribe_audio",
    response_model=TranscriptionResponse,
    summary="Transcribe audio file",
    description="Transcribe an audio file stored in GCP Cloud Storage.",
    status_code=status.HTTP_200_OK,
)
async def transcribe_audio_endpoint(
    payload: TranscriptionRequest,
    x_correlation_id: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None)
) -> TranscriptionResponse:
    if not payload.name:
        raise HTTPException(status_code=400, detail="audio_file_name is required")

    idem = derive_idempotency_key(x_idempotency_key, payload.bucket, payload.name, payload.generation)

    try:
        # Offload sync call to a worker thread (non-blocking)
        return await to_thread.run_sync(transcribe_with_idempotency, payload, x_correlation_id, idem)
    except RetryableError as e:
        jlog(event="transcribe_failed", retryable=True, error=str(e), correlation_id=x_correlation_id, idempotency_key=idem)
        raise HTTPException(status_code=503, detail=str(e))
    except PermanentError as e:
        jlog(event="transcribe_failed", retryable=False, error=str(e), correlation_id=x_correlation_id, idempotency_key=idem)
        raise HTTPException(status_code=422, detail=str(e))