import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError
from opentelemetry import trace

from .exceptions import PermanentError, RetryableError
from .logging import jlog
from .prompt import system_prompt
from .schemas import AuditRequest, AuditResponse
from .config import settings
from .storage import load_artifact, save_artifact

tracer = trace.get_tracer("compliance.audit")
retry_logger = logging.getLogger("tenacity")

AUDIT_MODEL = settings.audit_model
BASE_URL = settings.ollama_gcs_url
AUDIT_TIMEOUT_S = settings.audit_timeout_s

def _hash_preview(txt: str) -> str:
    return f"sha256={hashlib.sha256(txt.encode('utf-8')).hexdigest()[:12]},len={len(txt)}"

def _make_client() -> OpenAI:
    if not BASE_URL:
        raise PermanentError("Missing OLLAMA_GCS_URL for Compliance service")
    return OpenAI(base_url=f"{BASE_URL}/v1", api_key="dummy")

def _call_llm_with_guardrails(redacted_text: str, correlation_id: Optional[str]) -> Dict[str, Any]:
    """
    Require JSON:
      { "hipaa_compliant": bool, "fail_identifiers": [{ "type": str, "text": str, "position": str }], "comments": str }
    """

    client = _make_client()
   
    try:
        start = time.time()
        completion = client.chat.completions.create(
            model=AUDIT_MODEL,
            messages=[
                { "role": "system", "content": system_prompt},
                { "role": "user", "content": redacted_text}
            ],
            temperature=0.4,
            timeout=AUDIT_TIMEOUT_S,
        )  # type: ignore
        elapsed = time.time() - start
        jlog(
            event="audit_model_response",
            model_name=settings.audit_model,
            latency_ms=int(elapsed * 1000),
            model_response=completion.choices[0].message.content
        )
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

    content = completion.choices[0].message.content.strip() # type: ignore

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise PermanentError(f"Non-JSON audit response: {e}") from e

    # Minimal validation
    if not isinstance(data, dict):
        raise PermanentError("Audit response must be a JSON object")
    for key in ("hipaa_compliant", "fail_identifiers", "comments"):
        if key not in data:
            raise PermanentError(f"Audit response missing key: {key}")
    if not isinstance(data["hipaa_compliant"], bool):
        raise PermanentError("hipaa_compliant must be boolean")
    if not isinstance(data["fail_identifiers"], list):
        raise PermanentError("fail_identifiers must be an array")
    for item in data["fail_identifiers"]:
        if not isinstance(item, dict) or not all(k in item for k in ("type", "text", "position")):
            raise PermanentError("fail_identifiers items must include type, text, position")

    usage = getattr(completion, "usage", None)
    jlog(
        event="audit_llm_ok",
        step="audit",
        correlation_id=correlation_id,
        model_name=AUDIT_MODEL,
        latency_ms=int(elapsed * 1000),
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    )
    return data

def generate_audit_with_idempotency(
    req: AuditRequest,
    correlation_id: Optional[str],
    idempotency_key: Optional[str],
) -> AuditResponse:
    if not req.transcript or not req.transcript.strip():
        raise PermanentError("Empty transcript")

    cached = load_artifact(idempotency_key)
    if cached:
        jlog(
            event="audit_cache_hit",
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            transcript_hash=_hash_preview(req.transcript),
        )
        return cached

    with tracer.start_as_current_span("AuditGeneration") as span:
        span.set_attribute("operation", "audit_generation")
        span.set_attribute("model_name", AUDIT_MODEL)
        span.set_attribute("transcript_preview", _hash_preview(req.transcript))
        span.set_attribute("correlation_id", correlation_id or "")

        data = _call_llm_with_guardrails(req.transcript, correlation_id)
        resp = AuditResponse(**data)
        save_artifact(idempotency_key, resp)

        jlog(
            event="audit_ok",
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            hipaa_compliant=resp.hipaa_compliant,
            fails=len(resp.fail_identifiers),
        )
        return resp

