import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from anyio import to_thread

from fastapi import FastAPI, HTTPException, Request
from google.api_core import exceptions as gax_exceptions
from google.cloud import firestore, pubsub_v1
from google.oauth2 import id_token
from google.auth.transport import requests as ga_requests
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, stop_after_delay, wait_random_exponential

from .otel import init_tracing
from .src.logging import jlog
from .src.schemas import RunCreate

from .src.config import settings

os.environ.setdefault("SERVICE_NAME", settings.service_name)

# -----------------------
# App and global clients
# -----------------------

app = FastAPI(title="Orchestrator API", version="1.0.0")
tracer = init_tracing(app, service_name=settings.service_name, service_version="v1")

# Firestore client (sync; wrap in threads when used)
db = firestore.Client(project=settings.project_id)

# Pub/Sub publisher (sync API)
publisher_options = pubsub_v1.types.PublisherOptions(enable_message_ordering=True)
publisher = pubsub_v1.PublisherClient(publisher_options=publisher_options)

# Resolve topic paths 
TOPICS: Dict[str, str] = {
    "transcribe": publisher.topic_path(settings.project_id, settings.transcribe_requested_topic),
    "redact": publisher.topic_path(settings.project_id, settings.redact_requested_topic),
    "audit": publisher.topic_path(settings.project_id, settings.audit_requested_topic),
    "soap": publisher.topic_path(settings.project_id, settings.soap_requested_topic),
}

# -----------------------
# Utils
# -----------------------

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def idempotency_key_for(
    bucket: str, 
    name: str, 
    generation: Optional[str], 
    session_id: Optional[str]
) -> str:
    raw = f"{bucket}/{name}@{generation or ''}|{session_id or ''}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

async def verify_pubsub_auth(request: Request) -> None:
    if not settings.require_pubsub_auth:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth.split(" ", 1)[1]
    audience = settings.pubsub_push_audience or str(request.url)
    def _verify() -> None:
        req = ga_requests.Request()
        claims = id_token.verify_oauth2_token(token, req, audience=audience)
        iss = claims.get("iss")
        if iss not in ("https://accounts.google.com", "accounts.google.com"):
            raise ValueError("Invalid issuer")
    try:
        await to_thread.run_sync(_verify)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Pub/Sub OIDC token: {e}")
    
# Retryable exception types for Pub/Sub publish; others will bubble
RETRYABLE_PUBSUB_EXC = (
    gax_exceptions.ServiceUnavailable,
    gax_exceptions.DeadlineExceeded,
    gax_exceptions.InternalServerError,
    gax_exceptions.Aborted,
    gax_exceptions.ResourceExhausted,
    gax_exceptions.Unknown,
    gax_exceptions.Cancelled,
)

async def publish_event(
    topic_key: str, 
    event: Dict[str, Any], 
    ordering_key: str
) -> None:
    """
    Publish to Pub/Sub with ordering and small bounded retries.
    Runs blocking future.result() in a worker thread to avoid blocking the event loop.
    Raises HTTPException 503 on transient failures to let the caller retry.
    """
    if topic_key not in TOPICS:
        raise HTTPException(status_code=422, detail=f"Topic not configured: {topic_key}")

    data = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    attributes = {"event_type": event.get("event_type", "")}

    jlog(event="publish_event", topic=topic_key, ordering_key=ordering_key,
         event_type=attributes["event_type"], size=len(data))

    max_attempts = max(1, settings.orch_max_retries + 1)
    wait = wait_random_exponential(
        multiplier=max(0.01, settings.orch_backoff_base_ms / 1000.0),
        max=max(settings.orch_backoff_cap_ms / 1000.0, settings.orch_backoff_base_ms / 1000.0),
    )
    stop = (stop_after_attempt(max_attempts) | stop_after_delay(settings.orch_retry_budget_s))

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
            topic=topic_key,
            ordering_key=ordering_key,
        ),
    ):
        with attempt:
            # Execute publish and wait for result in a worker thread
            def _pub_sync() -> str:
                future = publisher.publish(
                    TOPICS[topic_key],
                    data=data,
                    ordering_key=ordering_key,
                    **attributes,
                )
                return future.result(timeout=settings.orch_timeout_s)
            try:
                message_id = await to_thread.run_sync(_pub_sync)
                jlog(event="publish_ok", topic=topic_key, ordering_key=ordering_key, message_id=message_id)
                return
            except RETRYABLE_PUBSUB_EXC as e:
                # Let tenacity retry
                raise
            except Exception as e:
                # Non-retryable publishing error
                jlog(event="publish_fail_permanent", topic=topic_key, ordering_key=ordering_key, error=str(e))
                raise HTTPException(status_code=422, detail=f"Publish failed: {e}") from e
            
# -----------------------
# Routes
# -----------------------

@app.post("/run")
async def create_run(
    request: Request, 
    run: RunCreate
):
    """
    Create a run if absent, and publish transcribe.requested.
    Return 200 with {run_id, created} on success.
    Return 503 on transient infra failures to let the caller retry.
    """
    # Correlation propagation
    corr_id = run.correlation_id or request.headers.get("x-correlation-id") or ""
    idem_header = request.headers.get("x-idempotency-key") or ""

    jlog(event="create_run", run=run.model_dump(), correlation_id=corr_id, idempotency_key=idem_header)

    run_id = idempotency_key_for(run.bucket, run.name, run.generation, run.session_id)
    run_ref = db.collection(settings.firestore_collection).document(run_id)
    step_ref = run_ref.collection("steps").document("transcribe")

    # Transaction: create run if absent
    def _tx_body(tx: firestore.Transaction) -> bool:
        snap = run_ref.get(transaction=tx)
        if not snap.exists:
            ttl_at = (datetime.now(timezone.utc) + timedelta(days=settings.idem_ttl_days)).isoformat()
            tx.set(run_ref, {
                "status": "RUNNING",
                "input": {"bucket": run.bucket, "name": run.name, "generation": run.generation, "session_id": run.session_id},
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "correlation_id": corr_id,
                "ttl_at": ttl_at,
            })
            tx.set(step_ref, {"status": "PENDING", "updated_at": firestore.SERVER_TIMESTAMP})
            return True
        return False

    @firestore.transactional
    def _tx(tx: firestore.Transaction) -> bool:
        return _tx_body(tx)

    try:
        created: bool = await to_thread.run_sync(_tx, db.transaction())
    except Exception as e:
        # Likely transient (deadline/aborted/contention), ask caller to retry
        jlog(event="create_run_tx_error", error=str(e), run_id=run_id)
        raise HTTPException(status_code=503, detail="Transient Firestore error") from e

    if created:
        event = {
            "version": "1",
            "event_type": "transcribe.requested",
            "run_id": run_id,
            "step": "transcribe",
            "input": run.model_dump(),
            "idempotency_key": run_id,
            "ts": utcnow_iso(),
            "correlation_id": corr_id,
        }
        try:
            await publish_event("transcribe", event, ordering_key=run_id)
        except HTTPException as e:
            # If publish failed permanently, surface 422; if transient, surface 503
            raise
        except Exception as e:
            jlog(event="publish_unexpected", error=str(e), run_id=run_id)
            raise HTTPException(status_code=503, detail="Unexpected publish error") from e

    return {"run_id": run_id, "created": created}

@app.post("/events/pubsub")
async def handle_pubsub(request: Request):
    # Verify authenticity of Pub/Sub push (OIDC)
    await verify_pubsub_auth(request)

    envelope = await request.json()
    if "message" not in envelope:
        raise HTTPException(status_code=400, detail="Bad Pub/Sub message")

    msg = envelope["message"]
    delivery_attempt = request.headers.get("X-Goog-Delivery-Attempt")
    try:
        data = json.loads(base64.b64decode(msg["data"]).decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"decode error: {e}")

    event_type = data.get("event_type", "")
    run_id = data.get("run_id")
    if not run_id:
        raise HTTPException(status_code=422, detail="missing run_id")

    jlog(event="event_received", event_type=event_type, run_id=run_id, delivery_attempt=delivery_attempt)

    try:
        if event_type == "transcribe.completed":
            await on_transcribe_completed(run_id, data)
        elif event_type == "redact.completed":
            await on_redact_completed(run_id, data)
        elif event_type == "audit.completed":
            await on_audit_completed(run_id, data, step_name="audit")
        elif event_type == "soap.completed" and "soap" in TOPICS:
            await on_audit_completed(run_id, data, step_name="soap")  # reuse if soap finalizes too
        elif event_type.endswith(".failed"):
            await on_step_failed(run_id, data)
        else:
            return {"ignored": event_type}
    except HTTPException:
        raise
    except Exception as e:
        # Treat handler exceptions as transient so Pub/Sub can retry and eventually DLQ
        jlog(event="event_handler_error", error=str(e), run_id=run_id, event_type=event_type)
        raise HTTPException(status_code=500, detail="Transient handler error") from e

    return {"ok": True}

# --------- Step Handlers ---------

async def on_transcribe_completed(run_id: str, evt: Dict[str, Any]):
    run_ref = db.collection(settings.firestore_collection).document(run_id)
    step_ref = run_ref.collection("steps").document("transcribe")

    def _tx_body(tx: firestore.Transaction) -> Optional[Dict[str, Any]]:
        step = step_ref.get(transaction=tx)
        if step.exists and step.get("status") == "COMPLETED":
            return None
        tx.set(step_ref, {"status": "COMPLETED", "artifacts": evt.get("artifacts", {}), "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        # Next: redact
        return {
            "version": "1",
            "event_type": "redact.requested",
            "run_id": run_id,
            "step": "redact",
            "input": evt.get("input", {}),
            "artifacts": evt.get("artifacts", {}),
            "ts": utcnow_iso(),
            "correlation_id": evt.get("correlation_id", ""),
        }

    @firestore.transactional
    def _tx(tx: firestore.Transaction) -> Optional[Dict[str, Any]]:
        return _tx_body(tx)

    redact_evt = await to_thread.run_sync(_tx, db.transaction())
    if redact_evt:
        await publish_event("redact", redact_evt, ordering_key=run_id)

async def on_redact_completed(run_id: str, evt: Dict[str, Any]):
    run_ref = db.collection(settings.firestore_collection).document(run_id)
    step_ref = run_ref.collection("steps").document("redact")

    def _tx_body(tx: firestore.Transaction) -> Optional[Dict[str, Any]]:
        step = step_ref.get(transaction=tx)
        if step.exists and step.get("status") == "COMPLETED":
            return None
        tx.set(step_ref, {"status": "COMPLETED", "artifacts": evt.get("artifacts", {}), "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        base = {
            "version": "1",
            "run_id": run_id,
            "input": evt.get("input", {}),
            "artifacts": evt.get("artifacts", {}),
            "ts": utcnow_iso(),
            "correlation_id": evt.get("correlation_id", ""),
        }
        return dict(base, event_type="audit.requested", step="audit")

    @firestore.transactional
    def _tx(tx: firestore.Transaction) -> Optional[Dict[str, Any]]:
        return _tx_body(tx)

    audit_evt = await to_thread.run_sync(_tx, db.transaction())
    if audit_evt:
        await publish_event("audit", audit_evt, ordering_key=run_id)

async def on_audit_completed(run_id: str, evt: Dict[str, Any], step_name: str):
    run_ref = db.collection(settings.firestore_collection).document(run_id)
    step_ref = run_ref.collection("steps").document(step_name)

    def _tx_body(tx: firestore.Transaction) -> None:
        step = step_ref.get(transaction=tx)
        if not (step.exists and step.get("status") == "COMPLETED"):
            tx.set(step_ref, {"status": "COMPLETED", "artifacts": evt.get("artifacts", {}), "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)

        # If audit is completed, finalize run outcome (adjust if you add more terminal steps)
        audit = run_ref.collection("steps").document("audit").get(transaction=tx).to_dict() or {}
        if audit.get("status") == "COMPLETED":
            hipaa_pass = (audit.get("artifacts", {}) or {}).get("hipaa_pass", True)
            tx.set(run_ref, {
                "status": "COMPLETED",
                "outcome": "PASS" if hipaa_pass else "FAIL",
                "updated_at": firestore.SERVER_TIMESTAMP,
            }, merge=True)

    @firestore.transactional
    def _tx(tx: firestore.Transaction) -> None:
        return _tx_body(tx)

    await to_thread.run_sync(_tx, db.transaction())

async def on_step_failed(run_id: str, evt: Dict[str, Any]):
    step = evt.get("step", "unknown")
    run_ref = db.collection(settings.firestore_collection).document(run_id)

    def _apply():
        run_ref.collection("steps").document(step).set(
            {"status": "FAILED", "error": evt.get("error"), "updated_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )
        run_ref.set({"status": "FAILED", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)

    await to_thread.run_sync(_apply)

# -----------------------
# Health
# -----------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "project_id": settings.project_id,
        "topics": list(TOPICS.keys()),
        "ordering_enabled": True
    }