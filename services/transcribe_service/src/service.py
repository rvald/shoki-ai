import os, time, hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from .schemas import TranscriptionRequest, TranscriptionResponse, Transcription, Segment
from .exceptions import RetryableError, PermanentError
from .logging import jlog
from .storage import load_artifact, save_artifact, download_blob_to_tmp

import logging
retry_logger = logging.getLogger("tenacity")

GOOGLE_CLOUD_STORAGE_BUCKET = os.environ.get("GOOGLE_CLOUD_STORAGE_BUCKET")
GOOGLE_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
WHISPER_MODEL_SIZE  = "small" 

_SIM_ATTEMPTS: dict[str, int] = {}

# Global Whisper model (load once)
import whisper
_MODEL = None

def load_model_once():
    global _MODEL
    if _MODEL is None:
        _MODEL = whisper.load_model(WHISPER_MODEL_SIZE)
    return _MODEL

def hash_preview(
    s: str
) -> str:
    return f"sha256={hashlib.sha256(s.encode()).hexdigest()[:12]},len={len(s)}"


def run_transcribe_step(
    local_path: str,
    language_hint: Optional[str]
) -> Dict[str, Any]:

    # Actual backend
    return transcribe_backend(local_path, language_hint)


def transcribe_backend(
    file_path: str, 
    language_hint: Optional[str]
) -> Dict[str, Any]:
    
    """Runs Whisper; classify expected errors."""
    try:
        model = load_model_once()
        result = model.transcribe(
            file_path,
            language=language_hint,
            task="transcribe",
            verbose=False,
        )
        segments = [{"start": s["start"], "end": s["end"], "text": s["text"].strip()} # type: ignore
                    for s in result.get("segments", [])]
        return {
            "text": result.get("text", "").strip(), # type: ignore
            "language": result.get("language"),
            "segments": segments,
            "duration": result.get("duration", 0),
            "model_used": WHISPER_MODEL_SIZE,
        }
    except RuntimeError as e:
        # Often retryable on resource hiccups
        raise RetryableError(f"whisper runtime: {e}") from e
    except Exception as e:
        # Default to permanent for unknown processing errors (audio corrupt, etc.)
        raise PermanentError(f"whisper failure: {e}") from e

def build_response(
    payload: Dict[str, Any], 
    audio_name: str
) -> TranscriptionResponse:
    now = datetime.now(timezone.utc).isoformat()
    segs = [Segment(**s) for s in payload.get("segments", [])]
    return TranscriptionResponse(
        transcription=Transcription(
            text=payload["text"],
            language=payload.get("language"),
            segments=segs,
            duration=payload.get("duration"),
            model_used=payload.get("model_used"),
            timestamp=now,
        ),
        audio_name=audio_name,
    )


def derive_idempotency_key(
    x_idempotency_key: Optional[str],
    bucket: Optional[str],
    audio_file_name: str,
    generation: Optional[str]
) -> Optional[str]:
    if x_idempotency_key:
        return x_idempotency_key
    raw = f"{bucket or ''}/{audio_file_name}@{generation or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def transcribe_with_idempotency(
    req: TranscriptionRequest,
    correlation_id: Optional[str],
    idempotency_key: Optional[str]
) -> TranscriptionResponse:
    # Step-level cache
    cached = load_artifact(idempotency_key)
    if cached:
        jlog(event="transcribe_cache_hit",
             correlation_id=correlation_id, idempotency_key=idempotency_key,
             audio=hash_preview(req.name))
        return cached

    # Download audio
    start_dl = time.time()
    try:
        local_path = download_blob_to_tmp(req.name, req.bucket)
    except FileNotFoundError as e:
        raise PermanentError(str(e))
    except Exception as e:
        raise RetryableError(f"gcs download: {e}") from e
    dl_ms = int((time.time() - start_dl) * 1000)

    # Transcribe
    start_tx = time.time()
    try:
        payload = run_transcribe_step(local_path, req.language_hint)
    finally:
        # Cleanup temp file
        try:
            from pathlib import Path
            p = Path(local_path)
            if p.exists():
                p.unlink()
        except Exception:
            pass
    tx_ms = int((time.time() - start_tx) * 1000)

    resp = build_response(payload, audio_name=req.name)
    # Persist artifact for reuse
    save_artifact(idempotency_key, resp)

    jlog(event="transcribe_ok",
         correlation_id=correlation_id,
         idempotency_key=idempotency_key,
         audio=hash_preview(req.name),
         download_ms=dl_ms, transcribe_ms=tx_ms)
    return resp
