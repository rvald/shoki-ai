from fastapi import FastAPI, Request, HTTPException
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from .src.logging import jlog
from .common.context import set_context

from .src.schemas import RunCreate

from google.cloud import firestore, pubsub_v1

import os, json, hashlib, base64
from .otel import init_tracing

app = FastAPI(title="Orchestrator API", version="1.0.0")

os.environ.setdefault("SERVICE_NAME", "orchestrator-service")
tracer = init_tracing(app, service_name="orchestrator-service", service_version="v1")

# Firestore and Pub/Sub clients
db = firestore.Client()
publisher_options = pubsub_v1.types.PublisherOptions(enable_message_ordering=True)
publisher = pubsub_v1.PublisherClient(publisher_options=publisher_options)

# Environment
TRABSCRIBE_TOPIC = "transcribe-requested" #os.getenv("TRANSCRIBE_REQUESTED_TOPIC")
REDACT_TOPIC = "redact-requested" #os.getenv("REDACT_REQUESTED_TOPIC")
AUDIT_TOPIC = "audit-requested" #os.getenv("AUDIT_REQUESTED_TOPIC")
SOAP_TOPIC = os.getenv("SOAP_REQUESTED_TOPIC")

PROJECT_ID = os.getenv("PROJECT_ID")

TOPICS = {
    "transcribe": publisher.topic_path(PROJECT_ID, TRABSCRIBE_TOPIC), # type: ignore
    "redact": publisher.topic_path(PROJECT_ID, REDACT_TOPIC), # type: ignore
    "audit": publisher.topic_path(PROJECT_ID, AUDIT_TOPIC), # type: ignore
    "soap": publisher.topic_path(PROJECT_ID, SOAP_TOPIC), # type: ignore
}

def idempotency_key_for(
    bucket: str, 
    name: str, 
    generation: Optional[str], 
    session_id: Optional[str]
) -> str:
    raw = f"{bucket}/{name}@{generation or ''}|{session_id or ''}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"  

def publish(
    topic_key: str, 
    event: Dict[str, Any], 
    ordering_key: str
) -> None:
    data = json.dumps(event).encode("utf-8")
    # add event_type attribute for easier filtering/inspection
    jlog(event="publish_event", topic=topic_key, ordering_key=ordering_key, event_type=event["event_type"], data=data.decode("utf-8"))
    future = publisher.publish(TOPICS[topic_key], data=data, ordering_key=ordering_key, event_type=event["event_type"])
    future.result(timeout=30)

@app.post("/run")    
async def create_run(
    run: RunCreate,    
):
    jlog(event="create_run", run=run.model_dump())

    run_id = idempotency_key_for(run.bucket, run.name, run.generation, run.session_id)
    run_ref = db.collection("runs").document(run_id)
    steps_ref = run_ref.collection("steps").document("transcribe")

    @firestore.transactional
    def tx_create(tx: firestore.Transaction) -> bool:
        snap = run_ref.get(transaction=tx)
        if not snap.exists:
            tx.set(run_ref, {
                "status": "RUNNING",
                "input": {"bucket": run.bucket, "name": run.name, "generation": run.generation},
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "correlation_id": run.correlation_id or "",
            })
            tx.set(steps_ref, {"status": "PENDING", "updated_at": firestore.SERVER_TIMESTAMP})
            return True
        return False
    
    created = tx_create(db.transaction())

    if created:
        event = {
            "version": "1",
            "event_type": "transcribe.requested",
            "run_id": run_id,
            "step": "transcribe",
            "input": run.model_dump(),
            "idempotency_key": run_id,
            "ts": utcnow(),
        }
        
        publish("transcribe", event, ordering_key=run_id)

    return {"run_id": run_id, "created": created}


@app.post("/events/pubsub")
async def handle_pubsub(request: Request):
    envelope = await request.json()
    if "message" not in envelope:
        raise HTTPException(status_code=400, detail="Bad Pub/Sub message")

    msg = envelope["message"]
    try:
        data = json.loads(base64.b64decode(msg["data"]).decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"decode error: {e}")

    event_type = data.get("event_type", "")
    run_id = data.get("run_id")
    if not run_id:
        raise HTTPException(status_code=400, detail="missing run_id")

    if event_type == "transcribe.completed":
        await on_transcribe_completed(run_id, data)
    elif event_type == "redact.completed":
        await on_redact_completed(run_id, data)
    elif event_type == "audit.completed":
        await on_audit_completed(run_id, data, "audit")
    elif event_type == "soap.completed":
        print("SOAP NEEDS TO BE IMPLEMENTED")
    elif event_type.endswith(".failed"):
        await on_step_failed(run_id, data)
    else:
        # Unknown or ignored event types are OK
        return {"ignored": event_type}

    return {"ok": True}

# --------- Handlers ---------
async def on_transcribe_completed(
    run_id: str, 
    evt: Dict[str, Any]
):
    run_ref = db.collection("runs").document(run_id)
    step_ref = run_ref.collection("steps").document("transcribe")

    @firestore.transactional
    def tx(tx: firestore.Transaction) -> Optional[Dict[str, Any]]:
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
            "ts": utcnow(),
        }

    redact_evt = tx(db.transaction())
    if redact_evt:
        publish("redact", redact_evt, ordering_key=run_id)

async def on_redact_completed(
    run_id: str, 
    evt: Dict[str, Any]
):
    run_ref = db.collection("runs").document(run_id)
    step_ref = run_ref.collection("steps").document("redact")

    @firestore.transactional
    def tx(tx: firestore.Transaction) ->  Optional[Dict[str, Any]]:
        step = step_ref.get(transaction=tx)
        if step.exists and step.get("status") == "COMPLETED":
            return None
        tx.set(step_ref, {"status": "COMPLETED", "artifacts": evt.get("artifacts", {}), "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)

        base = {"version": "1", "run_id": run_id, "input": evt.get("input", {}), "artifacts": evt.get("artifacts", {}), "ts": utcnow()}
        return dict(base, event_type="audit.requested", step="audit")

    audit_evt = tx(db.transaction())
    if audit_evt:
        publish("audit", audit_evt, ordering_key=run_id)
    

async def on_audit_completed(
    run_id: str, 
    evt: Dict[str, Any], 
    step_name: str
):
    run_ref = db.collection("runs").document(run_id)
    step_ref = run_ref.collection("steps").document(step_name)

    @firestore.transactional
    def tx(tx: firestore.Transaction) -> None:
        step = step_ref.get(transaction=tx)
        if not (step.exists and step.get("status") == "COMPLETED"):
            tx.set(step_ref, {"status": "COMPLETED", "artifacts": evt.get("artifacts", {}), "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)

        # Check if both audit and soap are completed
        audit = run_ref.collection("steps").document("audit").get(transaction=tx).to_dict() or {}
        
        if audit.get("status") == "COMPLETED":
            hipaa_pass = (audit.get("artifacts", {}) or {}).get("hipaa_pass", True)
            tx.set(run_ref, {
                "status": "COMPLETED",
                "outcome": "PASS" if hipaa_pass else "FAIL",
                "updated_at": firestore.SERVER_TIMESTAMP
            }, merge=True)

    tx(db.transaction())

async def on_step_failed(
    run_id: str, 
    evt: Dict[str, Any]
):
    step = evt.get("step", "unknown")
    run_ref = db.collection("runs").document(run_id)
    run_ref.collection("steps").document(step).set(
        {"status": "FAILED", "error": evt.get("error"), "updated_at": firestore.SERVER_TIMESTAMP},
        merge=True
    )
    run_ref.set({"status": "FAILED", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)

@app.get("/health")
def health():
    return {"status": "ok"}