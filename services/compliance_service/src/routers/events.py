import os, json, base64, logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from google.cloud import pubsub_v1, tasks_v2

import httpx

from ..schemas import AuditRequest
from ..service import generate_audit_with_idempotency
from ..storage import download_blob, ARTIFACT_BUCKET, artifact_blob_path
from ..logging import jlog

router = APIRouter()
log = logging.getLogger("compliance.events")
logging.basicConfig(level=logging.INFO)

# --------------------
# Configuration
# --------------------
PROJECT_ID = os.getenv("PROJECT_ID")
REGION = os.getenv("GOOGLE_CLOUD_LOCATION")

# Per-step topics (you chose separate topics)
AUDIT_COMPLETED_TOPIC = os.getenv("AUDIT_COMPLETED_TOPIC", "audit-completed")

# Pub/Sub toggle and local fallback to Orchestrator
PUBSUB_ENABLED = os.getenv("PUBSUB_ENABLED", "false").lower() == "true"
ORCHESTRATOR_PUBSUB_URL = "http://localhost:8089/events/pubsub"

# Cloud Tasks (async work executor)
TASKS_QUEUE = os.getenv("TASK_QUEUE_NAME")         # e.g., transcribe-queue
TASKS_LOCATION = os.getenv("TASK_QUEUE_LOCATION")
TASKS_SERVICE_URL = os.getenv("TASKS_SERVICE_URL") or "https://6511972ceeba.ngrok-free.app"

# --------------------
# Clients
# --------------------
publisher: Optional[pubsub_v1.PublisherClient] = None
if PUBSUB_ENABLED:
    publisher = pubsub_v1.PublisherClient()
    TOPIC_PATH = publisher.topic_path(PROJECT_ID, AUDIT_COMPLETED_TOPIC) if PROJECT_ID else None

tasks_client: Optional[tasks_v2.CloudTasksClient] = None
if TASKS_QUEUE:
    tasks_client = tasks_v2.CloudTasksClient()


def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _decode_pubsub_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    if "message" not in envelope:
        raise HTTPException(400, "Missing 'message'")
    msg = envelope["message"]
    data = msg.get("data")
    if not data:
        raise HTTPException(400, "Missing message.data")
    try:
        return json.loads(base64.b64decode(data).decode("utf-8"))
    except Exception as e:
        raise HTTPException(400, f"Invalid base64/json: {e}")
    

async def _publish_completed(event: Dict[str, Any]) -> None:
    # Local dev path: post directly to orchestrator
    if not PUBSUB_ENABLED:
        if ORCHESTRATOR_PUBSUB_URL:
            envelope = {
                "message": {
                    "messageId": f"local-{int(__import__('time').time())}",
                    "publishTime": _utcnow(),
                    "data": base64.b64encode(json.dumps(event).encode("utf-8")).decode("ascii"),
                }
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(ORCHESTRATOR_PUBSUB_URL, json=envelope)
                resp.raise_for_status()
            return
        log.info("[local-mode] Skipping publish; ORCHESTRATOR_PUBSUB_URL not set")
        return

    if not (publisher and PROJECT_ID and AUDIT_COMPLETED_TOPIC):
        raise RuntimeError("Pub/Sub not configured: set GOOGLE_CLOUD_PROJECT and TRANSCRIBE_COMPLETED_TOPIC")

    data = json.dumps(event).encode("utf-8")
    future = publisher.publish(
        TOPIC_PATH, data=data, # type: ignore
        event_type=event["event_type"],
        run_id=event["run_id"],
        step=event.get("step", "audit"),
        ordering_key=event["run_id"],  # maintain per-run ordering
    )
    future.result(timeout=30)

def _enqueue_task(task_payload: Dict[str, Any]) -> None:
    """
    Enqueue a Cloud Task to POST /tasks/audit with a JSON body.
    """
    if not tasks_client or not TASKS_QUEUE:
        raise RuntimeError("Cloud Tasks not configured. Set CLOUD_TASKS_QUEUE and CLOUD_TASKS_LOCATION.")

    parent = tasks_client.queue_path(PROJECT_ID, TASKS_LOCATION, TASKS_QUEUE) # type: ignore
    url = (TASKS_SERVICE_URL or "") + "/tasks/audit"  # if TASKS_SERVICE_URL empty, relative URL is fine on Cloud Run
    body = json.dumps(task_payload).encode("utf-8")

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": {"Content-Type": "application/json"},
            # Optionally add OIDC auth to call your service securely:
            # "oidc_token": {"service_account_email": os.getenv("TASKS_CALLER_SA")},
            "body": body,
        }
    }
    jlog(event="enqueue_task", queue=TASKS_QUEUE, url=url, input=task_payload.get("input", {}))
    tasks_client.create_task(request={"parent": parent, "task": task})

@router.post("/events/pubsub")
async def pubsub_push(request: Request, background: BackgroundTasks):
    """
    Pub/Sub push handler. Expects event_type=transcribe.requested.
    Must ack fast: only enqueue a task and return 2xx.
    """
    payload = _decode_pubsub_envelope(await request.json())
    event_type = payload.get("event_type")

    jlog(event="pubsub_event_received", event_type=event_type, payload=payload)

    if event_type != "audit.requested":
        # Ack unknown/irrelevant events to avoid retries
        return {}

    run_id = payload.get("run_id")
    input_obj = payload.get("input", {}) or {}
    corr = payload.get("correlation_id") or payload.get("x_correlation_id") or ""

    if not run_id:
        raise HTTPException(400, "missing run_id")
    if not input_obj.get("bucket") or not input_obj.get("name"):
        raise HTTPException(400, "input.bucket and input.name are required")

    task_payload = {
        "run_id": run_id,
        "input": input_obj,
        "correlation_id": corr,
        "ts": _utcnow(),
    }

    try:
        if tasks_client and TASKS_QUEUE:
            _enqueue_task(task_payload)
        else:
            # Dev fallback: fire-and-forget background task (not recommended in prod)
            background.add_task(_process_audit_task, task_payload)
    except Exception as e:
        log.exception("Failed to enqueue transcription task")
        # Non-2xx so Pub/Sub retries
        raise HTTPException(500, f"enqueue failed: {e}") from e

    # Ack
    return {}

@router.post("/tasks/audit")
async def tasks_transcribe(task_body: Dict[str, Any]):
    """
    Cloud Task worker. Does the actual audit and publishes *.completed.
    """
    run_id = task_body.get("run_id")

    if not run_id:
        raise HTTPException(400, "run_id required")

    try:
        await _process_audit_task(task_body)
        return {"ok": True}
    except Exception as e:
        # 5xx => Cloud Tasks will retry based on queue policy
        log.exception("Task processing failed")
        raise HTTPException(500, str(e)) from e

async def _process_audit_task(task_body: Dict[str, Any]) -> None:
    run_id = task_body["run_id"]
    input_obj = task_body.get("input") or {}
    corr = task_body.get("correlation_id")

    bucket = input_obj.get("bucket", "")
    name = input_obj.get("name")
    generation = input_obj.get("generation")

    bucket: str = input_obj.get("bucket", "")

    redacted_data = download_blob(bucket_name=bucket, blob_name=run_id)  # quick GCS client init check

    if redacted_data is None:
        raise RuntimeError(f"Failed to download redacted data for run_id {run_id} from bucket {bucket}")
    
    text = redacted_data.get("text", "")

    # Build TranscriptionRequest from event
    req = AuditRequest(
        transcript=text
    )

    # Use run_id as the step-level idempotency key
    idem_key = run_id

    jlog(event="audit_task_start", run_id=run_id, correlation_id=corr, bucket=bucket, name=name, generation=generation, idempotency_key=idem_key)

    # Execute with your existing idempotent path (downloads, tenacity, etc.)
    resp = generate_audit_with_idempotency(req, corr, idem_key)

    # Build artifacts for downstream. Prefer a GCS URI; also include cache_key for consumers that use load_artifact(idem_key).
    artifacts: Dict[str, Any] = {"cache_key": idem_key, "transcription": resp.model_dump() if hasattr(resp, "model_dump") else resp.model_dump()}

    # If you keep artifacts in a deterministic GCS path, expose it (align with your storage.save_artifact implementation)
    artifacts["audit_uri"] = artifact_blob_path(idem_key)

    event = {
        "version": "1",
        "event_type": "audit.completed",
        "run_id": run_id,
        "step": "transcribe",
        "input": {"bucket": ARTIFACT_BUCKET, "name": name, "generation": generation},
        "artifacts": artifacts,
        "correlation_id": corr or "",
        "ts": _utcnow(),
    }

    jlog(event="transcribe_completed_emit", run_id=run_id, correlation_id=corr, artifacts=list(artifacts.keys()))
    await _publish_completed(event)