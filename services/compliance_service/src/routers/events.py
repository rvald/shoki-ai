import base64
import json
from typing import Any, Dict, Optional

from anyio import to_thread, run
import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from google.api_core import exceptions as gax_exceptions
from google.cloud import pubsub_v1, tasks_v2
from google.oauth2 import id_token
from google.auth.transport import requests as ga_requests

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_random_exponential,
)

from ..exceptions import PermanentError, RetryableError
from ..logging import jlog
from ..schemas import AuditRequest
from ..config import settings
from ..storage import artifact_blob_path, download_blob

router = APIRouter()

# Lazy GCP clients
_publisher: Optional[pubsub_v1.PublisherClient] = None
_topics: Dict[str, str] = {}
_tasks_client: Optional[tasks_v2.CloudTasksClient] = None

def _ensure_pubsub():
    global _publisher, _topics
    if not settings.pubsub_enabled:
        return
    if _publisher is None:
        publisher_options = pubsub_v1.types.PublisherOptions(
            enable_message_ordering=settings.pubsub_enable_ordering
        )
        _publisher = pubsub_v1.PublisherClient(publisher_options=publisher_options)
        _topics["audit_completed"] = _publisher.topic_path(
            settings.project_id, settings.audit_completed_topic
        )

def _ensure_tasks():
    global _tasks_client
    if settings.task_queue_name and settings.task_queue_location and _tasks_client is None:
        _tasks_client = tasks_v2.CloudTasksClient()

def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

def _decode_pubsub_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    if "message" not in envelope:
        raise HTTPException(status_code=400, detail="Missing 'message'")
    msg = envelope["message"]
    data = msg.get("data")
    if not data:
        raise HTTPException(status_code=400, detail="Missing message.data")
    try:
        return json.loads(base64.b64decode(data).decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64/json: {e}")

async def _verify_pubsub_auth(request: Request) -> None:
    if not settings.pubsub_require_auth:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth.split(" ", 1)[1]
    audience = settings.pubsub_push_audience or str(request.url)

    def _verify():
        req = ga_requests.Request()
        claims = id_token.verify_oauth2_token(token, req, audience=audience)
        iss = claims.get("iss")
        if iss not in ("https://accounts.google.com", "accounts.google.com"):
            raise ValueError("Invalid issuer")

    try:
        await to_thread.run_sync(_verify)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Pub/Sub OIDC token: {e}")

RETRYABLE_PUBSUB_EXC = (
    gax_exceptions.ServiceUnavailable,
    gax_exceptions.DeadlineExceeded,
    gax_exceptions.InternalServerError,
    gax_exceptions.Aborted,
    gax_exceptions.ResourceExhausted,
    gax_exceptions.Unknown,
    gax_exceptions.Cancelled,
)

async def _publish_completed(event: Dict[str, Any], ordering_key: str) -> None:
    _ensure_pubsub()
    if _publisher is None:
        raise RuntimeError("Pub/Sub is disabled or not configured")

    topic_path = _topics["audit_completed"]
    data = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    attrs = {
        "event_type": event.get("event_type", ""),
        "run_id": event.get("run_id", ""),
        "step": event.get("step", "audit"),
    }

    jlog(
        event="publish_event",
        topic="audit_completed",
        ordering_key=ordering_key,
        size=len(data),
        attrs=attrs,
    )

    max_attempts = max(1, settings.pubsub_max_retries + 1)
    wait = wait_random_exponential(
        multiplier=max(0.01, settings.pubsub_backoff_base_ms / 1000.0),
        max=max(
            settings.pubsub_backoff_cap_ms / 1000.0,
            settings.pubsub_backoff_base_ms / 1000.0,
        ),
    )
    stop = (stop_after_attempt(max_attempts) | stop_after_delay(settings.pubsub_retry_budget_s))

    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(RETRYABLE_PUBSUB_EXC),
        wait=wait,
        stop=stop,
        reraise=True,
        before_sleep=lambda rs: jlog(
            event="publish_retry",
            attempt=rs.attempt_number,
            wait_s=getattr(getattr(rs, "next_action", None), "sleep", None),
            error=str(rs.outcome.exception()) if rs.outcome and rs.outcome.failed else None,
            topic="audit_completed",
            ordering_key=ordering_key,
        ),
    ):
        with attempt:
            def _pub_sync() -> str:
                kwargs = {"data": data, **attrs}
                if settings.pubsub_enable_ordering:
                    kwargs["ordering_key"] = ordering_key
                future = _publisher.publish(topic_path, **kwargs) # type: ignore
                return future.result(timeout=settings.pubsub_publish_timeout_s)

            msg_id = await to_thread.run_sync(_pub_sync)
            jlog(event="publish_ok", message_id=msg_id, ordering_key=ordering_key)
            return

def _enqueue_task(task_payload: Dict[str, Any]) -> None:
    """
    Enqueue a Cloud Task to POST /tasks/audit with JSON body.
    Deterministic task name for idempotency (per run_id).
    """
    _ensure_tasks()
    if not (_tasks_client and settings.task_queue_name and settings.task_queue_location and settings.tasks_service_url):
        raise RuntimeError(
            "Cloud Tasks not configured properly (TASK_QUEUE_NAME, TASK_QUEUE_LOCATION, TASKS_SERVICE_URL)"
        )

    parent = _tasks_client.queue_path(settings.project_id, settings.task_queue_location, settings.task_queue_name)
    url = settings.tasks_service_url

    
    body = json.dumps(task_payload).encode("utf-8")

    http_request: Dict[str, Any] = {
        "http_method": tasks_v2.HttpMethod.POST,
        "url": url,
        "headers": {"Content-Type": "application/json"},
        "body": body,
    }
    # Secure target with OIDC
    if settings.tasks_caller_sa:
        http_request["oidc_token"] = {
            "service_account_email": settings.tasks_caller_sa,
            **({"audience": settings.tasks_audience} if settings.tasks_audience else {}),
        }

    # Deterministic task name for dedup
    task_name = f"audit-{task_payload['run_id']}"
    task = {
        "name": _tasks_client.task_path(
            settings.project_id, settings.task_queue_location, settings.task_queue_name, task_name
        ),
        "http_request": http_request,
    }

    jlog(event="enqueue_task", queue=settings.task_queue_name, url=url, run_id=task_payload.get("run_id"))
    try:
        _tasks_client.create_task(request={"parent": parent, "task": task})
    except gax_exceptions.AlreadyExists:
        jlog(event="enqueue_task_exists", run_id=task_payload.get("run_id"))

@router.post("/events/pubsub")
async def pubsub_push(request: Request, background: BackgroundTasks) -> Dict[str, Any]:
    """
    Pub/Sub push handler. Expects event_type=audit.requested.
    Ack fast: enqueue a Cloud Task and return 2xx.
    """
    await _verify_pubsub_auth(request)
    delivery_attempt = request.headers.get("X-Goog-Delivery-Attempt")
    payload = _decode_pubsub_envelope(await request.json())
    event_type = payload.get("event_type")

    jlog(
        event="pubsub_event_received",
        event_type=event_type,
        payload_summary=list(payload.keys()),
        delivery_attempt=delivery_attempt,
    )

    if event_type != "audit.requested":
        return {}

    run_id = payload.get("run_id")
    input_obj = payload.get("input", {}) or {}
    corr = payload.get("correlation_id") or ""

    if not run_id:
        raise HTTPException(status_code=400, detail="missing run_id")
    if not input_obj.get("bucket") or not input_obj.get("name"):
        raise HTTPException(status_code=400, detail="input.bucket and input.name are required")

    task_payload = {
        "run_id": run_id,
        "input": input_obj,
        "correlation_id": corr,
        "ts": _utcnow(),
    }

    try:
        if settings.task_queue_name and settings.task_queue_location:
            _enqueue_task(task_payload)
        else:
            # Dev fallback: fire-and-forget (not for prod)
            background.add_task(_process_audit_task, request, task_payload)
    except Exception as e:
        jlog(event="enqueue_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"enqueue failed: {e}") from e

    return {}

@router.post("/tasks/audit")
async def tasks_audit(request: Request, task_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cloud Task worker. Does the audit and publishes *.completed.
    PermanentError -> 422 (stop retries), RetryableError/unknown -> 503 (retry).
    """
    retry_count = request.headers.get("X-Cloud-Tasks-TaskRetryCount")
    jlog(event="task_received", retry_count=retry_count, body_keys=list(task_body.keys()))

    try:
        await _process_audit_task(request, task_body)
        return {"ok": True}
    except PermanentError as e:
        jlog(event="task_failed_permanent", error=str(e))
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RetryableError as e:
        jlog(event="task_failed_retryable", error=str(e))
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        jlog(event="task_failed_unexpected", error=str(e))
        raise HTTPException(status_code=503, detail="unexpected error") from e

async def _process_audit_task(request: Request, task_body: Dict[str, Any]) -> None:
    """
    Orchestrates loading the redacted artifact, auditing via LLM, and publishing the result.
    """
    run_id = task_body["run_id"]
    input_obj = task_body.get("input") or {}
    corr = task_body.get("correlation_id")

    src_bucket = input_obj.get("bucket")
    name = input_obj.get("name")
    generation = input_obj.get("generation")

    # Read the redacted artifact produced by privacy service from the artifact bucket using idem_key = run_id
    redacted_obj = await to_thread.run_sync(download_blob, src_bucket, run_id) # type: ignore
    if not redacted_obj:
        raise PermanentError(f"Missing redacted artifact for run_id={run_id} in bucket={src_bucket}")

    redacted_text = redacted_obj.get("text", "")
    if not redacted_text:
        raise PermanentError("Empty redacted text")

    areq = AuditRequest(transcript=redacted_text)
    idem_key = run_id

    jlog(
        event="audit_task_start",
        run_id=run_id,
        correlation_id=corr,
        bucket=src_bucket,
        name=name,
        generation=generation,
        idempotency_key=idem_key,
    )

    # Execute audit in worker thread (LLM calls + artifact cache)
    from ..service import generate_audit_with_idempotency as _svc_audit
    resp = await to_thread.run_sync(_svc_audit, areq, corr, idem_key)

    # Build artifacts for downstream. Include a convenience hipaa_pass flag for the orchestrator.
    audit_uri = artifact_blob_path(idem_key)
    out_artifacts: Dict[str, Any] = {
        "cache_key": idem_key,
        #"audit": resp.model_dump(),
        "audit_uri": audit_uri,
        #"hipaa_pass": resp.hipaa_compliant,
    }

    event = {
        "version": "1",
        "event_type": "audit_completed",
        "run_id": run_id,
        "step": "audit",
        "input": {"bucket": src_bucket, "name": name, "generation": generation},
        "artifacts": out_artifacts,
        "correlation_id": corr or "",
        "ts": _utcnow(),
    }

    jlog(event="audit_completed_emit", run_id=run_id, correlation_id=corr, artifacts=list(out_artifacts.keys()))

    # Publish to Pub/Sub or to orchestrator in local mode
    if settings.pubsub_enabled:
        await _publish_completed(event, ordering_key=run_id)
    else:
        # local dev: post envelope to orchestrator
        url = settings.orchestrator_pubsub_url
        if not url:
            jlog(event="local_publish_skipped", reason="no_url")
            return
        envelope = {
            "message": {
                "messageId": f"local-{int(__import__('time').time())}",
                "publishTime": _utcnow(),
                "data": base64.b64encode(json.dumps(event).encode("utf-8")).decode("ascii"),
            }
        }
        client: httpx.AsyncClient = request.app.state.httpx_client
        resp = await client.post(url, json=envelope)
        if resp.status_code >= 300:
            raise RetryableError(f"local publish failed: {resp.status_code} {resp.text}")