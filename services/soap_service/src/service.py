import os, json, time, hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from openai import OpenAI
from openai import APIError, RateLimitError, APITimeoutError, APIConnectionError, BadRequestError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_sleep_log
import logging

# Use your common package; swap to local modules if needed
from .exceptions import RetryableError, PermanentError
from .logging import jlog

from .schemas import SoapNoteRequest, SoapNoteResponse
from .storage import load_artifact, save_artifact  # artifact cache helpers you’ll add below

from .prompt import system_prompt

retry_logger = logging.getLogger("tenacity")

SOAP_MODEL = os.getenv("SOAP_MODEL", "gpt-oss")
BASE_URL = os.getenv("OLLAMA_GCS_URL")  # OpenAI-compatible base
SOAP_TIMEOUT_S = float(os.getenv("SOAP_TIMEOUT_S", "60"))
SOAP_JSON_MODE = os.getenv("SOAP_JSON_MODE", "false").lower() == "true" 


def _hash_preview(text: str) -> str:
    return f"sha256={hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]},len={len(text)}"

def _make_client() -> OpenAI:
    if not BASE_URL:
        raise PermanentError("Missing OLLAMA_GCS_URL for SOAP service")
    return OpenAI(base_url=f"{BASE_URL}/v1", api_key="dummy")

# The orchestrator requires exact JSON: { "soap_note": "<soap_note> ... </soap_note>" }
# We validate strictly and treat non-JSON outputs as permanent failures after a small retry budget.
@retry(wait=wait_exponential(multiplier=0.5, min=1, max=8),
       stop=stop_after_attempt(2),
       retry=retry_if_exception_type(RetryableError),
       before_sleep=before_sleep_log(retry_logger, logging.WARNING))
def _generate_soap_backend(
    redacted_text: str, 
    language: Optional[str], 
    correlation_id: Optional[str]
) -> Dict[str, Any]:
    
    client = _make_client()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": redacted_text},
    ]

    try:
        kwargs = dict(model=SOAP_MODEL, messages=messages, temperature=0.4, timeout=SOAP_TIMEOUT_S)
        if SOAP_JSON_MODE:
            kwargs["response_format"] = {"type": "json_object"}  # if supported by your server
        start = time.time()
        completion = client.chat.completions.create(**kwargs)
        elapsed = time.time() - start
    except (APITimeoutError, APIConnectionError) as e:
        raise RetryableError(f"LLM timeout/conn: {e}") from e
    except RateLimitError as e:
        raise RetryableError(f"LLM rate limit: {e}") from e
    except APIError as e:
        if getattr(e, "status_code", 500) >= 500:
            raise RetryableError(f"LLM server error: {e}") from e
        raise PermanentError(f"LLM API error: {e}") from e
    except BadRequestError as e:
        raise PermanentError(f"LLM bad request: {e}") from e
    except Exception as e:
        raise RetryableError(f"LLM unknown error: {e}") from e

    content = completion.choices[0].message.content.strip()
    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        # Treat non-JSON as permanent after our tiny retry budget
        raise PermanentError(f"Non-JSON response from SOAP model: {e}") from e

    # Validate schema minimally (has soap_note)
    if not isinstance(data, dict) or "soap_note" not in data or not isinstance(data["soap_note"], str):
        raise PermanentError("SOAP response missing required key 'soap_note'")

    usage = getattr(completion, "usage", None)
    jlog(event="soap_llm_ok",
         step="soap",
         correlation_id=correlation_id,
         model_name=SOAP_MODEL,
         latency_ms=int(elapsed * 1000),
         prompt_tokens=getattr(usage, "prompt_tokens", None),
         completion_tokens=getattr(usage, "completion_tokens", None),
         total_tokens=getattr(usage, "total_tokens", None))
    return data

def generate_soap_with_idempotency(
    req: SoapNoteRequest,
    correlation_id: Optional[str],
    idempotency_key: Optional[str],
    simulate_mode: Optional[str] = None
) -> SoapNoteResponse:
    if not req.text or not req.text.strip():
        raise PermanentError("Empty text")
    # Cache
    cached = load_artifact(idempotency_key)
    if cached:
        jlog(event="soap_cache_hit",
             correlation_id=correlation_id, idempotency_key=idempotency_key,
             text_hash=_hash_preview(req.text))
        return cached

    # Simulate failures inside retried path by raising before making the call (we'll bubble as RetryableError/PermanentError)
    if simulate_mode == "retryable-once":
        # You can maintain a small in-memory attempt map if you want first-attempt-only behavior
        raise RetryableError("SIM: retryable-once")
    if simulate_mode == "retryable-always":
        raise RetryableError("SIM: retryable-always")
    if simulate_mode == "permanent":
        raise PermanentError("SIM: permanent")

    data = _generate_soap_backend(req.text, req.language, correlation_id)
    resp = SoapNoteResponse(soap_note=data["soap_note"])
    save_artifact(idempotency_key, resp)
    jlog(event="soap_ok",
         correlation_id=correlation_id, idempotency_key=idempotency_key,
         text_hash=_hash_preview(req.text))
    return resp


def generate_soap_note(
    transcript: str,
    model_name: str,
    prompt: str = system_prompt,
    temperature: float = 0.4,
) -> str:
    
    BASE_URL = os.environ.get("OLLAMA_GCS_URL")
    
    client = OpenAI(
        base_url = f"{BASE_URL}/v1",
        api_key="dummy",
    )

    start_time = time.time()
    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
        temperature=temperature,
    )
    elapsed = time.time() - start_time

    response = completion.choices[0].message.content.strip()
    usage = getattr(completion, "usage", None)

    if usage:
        # Optionally log the trace info as before
        prompt_tokens = getattr(usage, 'prompt_tokens', None)
        completion_tokens = getattr(usage, 'completion_tokens', None)
        total_tokens = getattr(usage, 'total_tokens', None)
    
    audit_trace = {
        "input": transcript,
        "response": response,
        "latency_seconds": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "model_name": model_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "operation": "soap_note_generation",
    }

    # Get parent of current working directory
    parent_dir = os.path.dirname(os.getcwd())

    # Full path for traces directory inside the parent directory
    trace_dir = os.path.join(parent_dir, "observability", "traces")

    # Make the directory if it doesn't exist
    os.makedirs(trace_dir, exist_ok=True)

    # Use full path when saving the file (join with trace_dir)
    filename = f"audit_generation_{datetime.now().isoformat()}.json"
    save_path = os.path.join(trace_dir, filename)
    
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(audit_trace, f, indent=2, ensure_ascii=False)

    return response