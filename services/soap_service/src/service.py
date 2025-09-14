import hashlib
import json
import time
from typing import Any, Dict, Optional

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential
import logging

from .exceptions import PermanentError, RetryableError
from .logging import jlog
from .schemas import SoapNoteRequest, SoapNoteResponse
from .config import settings
from .storage import load_artifact, save_artifact
from .prompt import system_prompt

retry_logger = logging.getLogger("tenacity")

SOAP_MODEL = settings.soap_model
BASE_URL = settings.ollama_gcs_url
SOAP_TIMEOUT_S = settings.soap_timeout_s
SOAP_JSON_MODE = settings.soap_json_mode

def _hash_preview(text: str) -> str:
    import hashlib as _h
    return f"sha256={_h.sha256(text.encode('utf-8')).hexdigest()[:12]},len={len(text)}"

def _make_client() -> OpenAI:
    if not BASE_URL:
        raise PermanentError("Missing OLLAMA_GCS_URL for SOAP service")
    return OpenAI(base_url=f"{BASE_URL}/v1", api_key="dummy")

# Small, bounded retries on network/server errors; permanent errors stop immediately.
@retry(
    wait=wait_exponential(multiplier=0.5, min=1, max=8),
    stop=stop_after_attempt(2),
    retry=retry_if_exception_type(RetryableError),
    before_sleep=before_sleep_log(retry_logger, logging.WARNING),
)
def _generate_soap_backend(
    redacted_text: str,
    language: Optional[str],
    correlation_id: Optional[str],
) -> Dict[str, Any]:
    client = _make_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": redacted_text},
    ]

    try:
        kwargs: Dict[str, Any] = dict(model=SOAP_MODEL, messages=messages, temperature=0.4, timeout=SOAP_TIMEOUT_S)
        if SOAP_JSON_MODE:
            kwargs["response_format"] = {"type": "json_object"}  # backend-dependent support
        start = time.time()
        completion = client.chat.completions.create(**kwargs)  # type: ignore
        elapsed = time.time() - start
    except (APITimeoutError, APIConnectionError) as e:
        raise RetryableError(f"LLM timeout/conn: {e}") from e
    except RateLimitError as e:
        raise RetryableError(f"LLM rate limit: {e}") from e
    except APIError as e:
        if getattr(e, "status_code", 500) >= 500:
            raise RetryableError(f"LLM server error: {e}") from e
        raise PermanentError(f"LLM API error: {e}") from e
    except Exception as e:
        raise RetryableError(f"LLM unknown error: {e}") from e

    content = completion.choices[0].message.content.strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        # Treat non-JSON as permanent after small retry budget
        raise PermanentError(f"Non-JSON response from SOAP model: {e}") from e

    if not isinstance(data, dict) or "soap_note" not in data or not isinstance(data["soap_note"], str):
        raise PermanentError("SOAP response missing required key 'soap_note'")

    usage = getattr(completion, "usage", None)
    jlog(
        event="soap_llm_ok",
        step="soap",
        correlation_id=correlation_id,
        model_name=SOAP_MODEL,
        latency_ms=int(elapsed * 1000),
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    )
    return data

def generate_soap_with_idempotency(
    req: SoapNoteRequest,
    correlation_id: Optional[str],
    idempotency_key: Optional[str],
    simulate_mode: Optional[str] = None,
) -> SoapNoteResponse:
    if not req.text or not req.text.strip():
        raise PermanentError("Empty text")

    cached = load_artifact(idempotency_key)
    if cached:
        jlog(
            event="soap_cache_hit",
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            text_hash=_hash_preview(req.text),
        )
        return cached

    # Optional simulation controls for testing retryability
    if simulate_mode == "retryable-once":
        raise RetryableError("SIM: retryable-once")
    if simulate_mode == "retryable-always":
        raise RetryableError("SIM: retryable-always")
    if simulate_mode == "permanent":
        raise PermanentError("SIM: permanent")

    data = _generate_soap_backend(req.text, req.language, correlation_id)
    resp = SoapNoteResponse(soap_note=data["soap_note"])
    save_artifact(idempotency_key, resp)
    jlog(
        event="soap_ok",
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        text_hash=_hash_preview(req.text),
    )
    return resp