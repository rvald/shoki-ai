import os, json, time, hashlib, logging
from typing import Optional, Dict, Any
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_sleep_log
from openai import OpenAI
from openai import APIError, RateLimitError, APITimeoutError, APIConnectionError, BadRequestError
from opentelemetry import trace

from .exceptions import RetryableError, PermanentError
from .logging import jlog

from .schemas import AuditRequest, AuditResponse
from .storage import load_artifact, save_artifact
from .prompt import system_prompt  

tracer = trace.get_tracer("compliance.audit")
retry_logger = logging.getLogger("tenacity")

AUDIT_MODEL = os.getenv("AUDIT_MODEL", "gpt-oss")
BASE_URL = os.getenv("OLLAMA_GCS_URL")
AUDIT_TIMEOUT_S = float(os.getenv("AUDIT_TIMEOUT_S", "60"))
AUDIT_JSON_MODE = os.getenv("AUDIT_JSON_MODE", "false").lower() == "true"

def _hash_preview(txt: str) -> str:
    return f"sha256={hashlib.sha256(txt.encode('utf-8')).hexdigest()[:12]},len={len(txt)}"

def _make_client() -> OpenAI:
    if not BASE_URL:
        raise PermanentError("Missing OLLAMA_GCS_URL for Compliance service")
    return OpenAI(base_url=f"{BASE_URL}/v1", api_key="dummy")

@retry(wait=wait_exponential(multiplier=0.5, min=1, max=8),
       stop=stop_after_attempt(2),
       retry=retry_if_exception_type(RetryableError),
       before_sleep=before_sleep_log(retry_logger, logging.WARNING))
def _call_llm_with_guardrails(
    redacted_text: str,
    correlation_id: Optional[str],
) -> Dict[str, Any]:
    """
    Require JSON:
      { "hipaa_compliant": bool, "fail_identifiers": [{ "type": str, "text": str, "position": str }], "comments": str }
    """
    client = _make_client()

    # Strengthen your prompt file to explicitly demand ONLY valid JSON with the schema above.
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": redacted_text},
    ]

    try:
        kwargs = dict(model=AUDIT_MODEL, messages=messages, temperature=0.4, timeout=AUDIT_TIMEOUT_S)
        if AUDIT_JSON_MODE:
            kwargs["response_format"] = {"type": "json_object"}  # if supported by your backend
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
    # Each fail identifier should have type/text/position
    for item in data["fail_identifiers"]:
        if not isinstance(item, dict) or not all(k in item for k in ("type", "text", "position")):
            raise PermanentError("fail_identifiers items must include type, text, position")

    usage = getattr(completion, "usage", None)
    jlog(event="audit_llm_ok",
         step="audit",
         correlation_id=correlation_id,
         model_name=AUDIT_MODEL,
         latency_ms=int(elapsed * 1000),
         prompt_tokens=getattr(usage, "prompt_tokens", None),
         completion_tokens=getattr(usage, "completion_tokens", None),
         total_tokens=getattr(usage, "total_tokens", None))
    return data

def generate_audit_with_idempotency(
    req: AuditRequest,
    correlation_id: Optional[str],
    idempotency_key: Optional[str],
    simulate_mode: Optional[str] = None,
) -> AuditResponse:
    if not req.transcript or not req.transcript.strip():
        raise PermanentError("Empty transcript")
    # Cache
    cached = load_artifact(idempotency_key)
    if cached:
        jlog(event="audit_cache_hit",
             correlation_id=correlation_id, idempotency_key=idempotency_key,
             transcript_hash=_hash_preview(req.transcript))
        return cached

    # Simulated failures (test-only)
    if simulate_mode == "retryable-always":
        raise RetryableError("SIM: retryable-always")
    if simulate_mode == "permanent":
        raise PermanentError("SIM: permanent")

    with tracer.start_as_current_span("AuditGeneration") as span:
        # Privacy-safe span attrs
        span.set_attribute("operation", "audit_generation")
        span.set_attribute("model_name", AUDIT_MODEL)
        span.set_attribute("transcript_preview", _hash_preview(req.transcript))
        span.set_attribute("correlation_id", correlation_id or "")

        data = _call_llm_with_guardrails(req.transcript, correlation_id)
        resp = AuditResponse(**data)
        save_artifact(idempotency_key, resp)

        jlog(event="audit_ok",
             correlation_id=correlation_id, idempotency_key=idempotency_key,
             hipaa_compliant=resp.hipaa_compliant,
             fails=len(resp.fail_identifiers))
        return resp

def generate_audit(
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

    with tracer.start_as_current_span("AuditGeneration") as span:
        span.set_attribute("model_name", model_name)
        span.set_attribute("operation", "audit_generation")
        span.set_attribute("prompt", prompt)
        span.set_attribute("transcript", transcript)
        span.set_attribute("temperature", temperature)

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
            span.set_attribute("prompt_tokens", usage.prompt_tokens)
            span.set_attribute("completion_tokens", usage.completion_tokens)
            span.set_attribute("total_tokens", usage.total_tokens)

        span.set_attribute("latency_seconds", elapsed)
        span.set_attribute("response", response)

        # Optionally log the trace info as before
        audit_trace = {
            "input": transcript,
            "response": response,
            "latency_seconds": elapsed,
            "prompt_tokens": getattr(usage, 'prompt_tokens', None),
            "completion_tokens": getattr(usage, 'completion_tokens', None),
            "total_tokens": getattr(usage, 'total_tokens', None),
            "model_name": model_name,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "operation": "audit_generation",
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