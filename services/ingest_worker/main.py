import asyncio
import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, stop_after_delay, wait_random_exponential

from anyio import to_thread, run
import httpx
from fastapi import FastAPI, Request, HTTPException, Response
from google.cloud import firestore
from google.cloud.firestore_v1 import Increment
from google.oauth2 import id_token
from google.auth.transport import requests as ga_requests

from .src.logging import jlog
from .src.exceptions import RetryableError, PermanentError
from .src.schemas import PubSubEnvelope
from .otel import init_tracing

from contextlib import asynccontextmanager
from typing import AsyncIterator
from .src.config import settings


os.environ.setdefault("SERVICE_NAME", settings.service_name)

# -----------------------
# Lifecycle hooks
# -----------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:

    # Global HTTPX client and concurrency guard
    httpx_limits = httpx.Limits(max_connections=200, max_keepalive_connections=100)

    # Create shared client with pooling and HTTP/2
    client = httpx.AsyncClient(
        # Explicit timeouts help control behavior under load; adjust if needed
        timeout=httpx.Timeout(
            connect=5.0,
            read=settings.orch_timeout_s,
            write=5.0,
            pool=None,
        ),
        limits=httpx_limits,
        http2=True,
    )

    # Initialize other shared resources here if applicable
    app.state.orch_semaphore = asyncio.Semaphore(settings.orch_concurrency)
    app.state.httpx_client = client

    try:
        yield
    finally:
        # Ensure cleanup even if an exception occurs
        await client.aclose()


# -----------------------
# App and clients
# -----------------------

app = FastAPI(title="Ingest Worker", lifespan=lifespan)
tracer = init_tracing(app, service_name="ingest-worker", service_version="v1")

db = firestore.Client(project=settings.project_id)

# Small per-audience ID token cache
_ID_TOKEN_CACHE: Dict[str, Dict[str, Any]] = {}  # {audience: {"exp": epoch_seconds, "token": str}}

# -----------------------
# Utility functions
# -----------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def make_idempotency_key(bucket: str, name: str, generation: str, session_id: Optional[str]) -> str:
    sid = session_id if (session_id and settings.include_session_in_idem) else ""
    raw = f"{bucket}/{name}@{generation}|{sid}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _fetch_identity_token(audience: str):
    # cache for ~5 minutes to reduce metadata calls
    now = time.time()
    cached = _ID_TOKEN_CACHE.get(audience)
    if cached and cached["exp"] - 60 > now:
        return cached["token"]
    req = ga_requests.Request()
    token = id_token.fetch_id_token(req, audience)  # uses metadata server on Cloud Run
    # ID tokens typically have 1 hour exp; we conservatively cache for 5 minutes
    _ID_TOKEN_CACHE[audience] = {"token": token, "exp": now + 300}
    return token

async def _verify_pubsub_auth(request: Request) -> None:
    if not settings.require_pubsub_auth:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth.split(" ", 1)[1]
    audience = settings.pubsub_push_audience or str(request.url)
    try:
        # Blocking verification; offload to thread
        def _verify():
            req = ga_requests.Request()
            # verify audience, expiry, issuer
            claims = id_token.verify_oauth2_token(token, req, audience=audience)
            if claims.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
                raise ValueError("Invalid issuer")
            return claims
        await to_thread.run_sync(_verify)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Pub/Sub OIDC token: {e}")

async def _firestore_tx_check_and_mark(
    doc_ref,
    bucket: str,
    name: str,
    generation: str,
    session_id: Optional[str],
    publish_time: Optional[str],
) -> str:
    # Firestore transactions are blocking; execute in thread
    def _tx_body(tx):
        snap = doc_ref.get(transaction=tx)
        now = _now_iso()
        ttl_at = (datetime.now(timezone.utc) + timedelta(days=settings.idem_ttl_days)).isoformat()
        if snap.exists:
            status = snap.get("status")
            # Treat PROCESSING, DONE, or FAILED_PERMANENT as duplicates
            if status in ("PROCESSING", "DONE", "FAILED_PERMANENT"):
                return "DUPLICATE"
            # Otherwise, mark as PROCESSING and increment attempt_count
            tx.update(doc_ref, {
                "status": "PROCESSING",
                "last_updated": now,
                "attempt_count": Increment(1),
            })
        else:
            tx.set(doc_ref, {
                "bucket": bucket,
                "name": name,
                "generation": generation,
                "session_id": session_id,
                "publish_time": publish_time,
                "status": "PROCESSING",
                "attempt_count": 1,
                "first_seen": now,
                "last_updated": now,
                "ttl_at": ttl_at,  # create TTL policy on this field in Firestore
            })
        return "PROCESS"

    @firestore.transactional
    def _run(tx):
        return _tx_body(tx)

    tx = db.transaction()
    return await to_thread.run_sync(_run, tx)

async def call_orchestrator(
    payload: dict,
    correlation_id: str,
    idempotency_key: str,
    client: httpx.AsyncClient,
):
    if not settings.orchestrator_url:
        raise PermanentError("Missing ORCHESTRATOR_URL")

    # Prepare headers once per overall call (avoid re-fetching token each attempt)
    headers = {
        "x-correlation-id": correlation_id,
        "x-idempotency-key": idempotency_key,
    }
    token = await to_thread.run_sync(_fetch_identity_token, settings.orchestrator_url)
    headers["Authorization"] = f"Bearer {token}"

    url = f"{settings.orchestrator_url}/run"

    # Build a closure for before_sleep logging (attempts and planned wait)
    def _before_sleep_log(retry_state):
        # retry_state.next_action.sleep is set in newer tenacity versions; guard if absent
        sleep_s = getattr(getattr(retry_state, "next_action", None), "sleep", None)
        err = None
        if retry_state.outcome and retry_state.outcome.failed:
            try:
                err = str(retry_state.outcome.exception())
            except Exception:
                err = "<unknown>"
        jlog(
            event="orchestrator_retry",
            attempt=retry_state.attempt_number,
            wait_s=sleep_s,
            error=err,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

    max_attempts = max(1, settings.orch_max_retries + 1)  # first try + retries
    # Convert ms to seconds for tenacity's wait policy
    backoff_base_s = max(0.01, settings.orch_backoff_base_ms / 1000.0)
    backoff_cap_s = max(backoff_base_s, settings.orch_backoff_cap_ms / 1000.0)

    # Retry conditions: RetryableError (our wrapper) and network-level httpx errors
    retry_condition = retry_if_exception_type((RetryableError, httpx.RequestError))

    # Stop conditions: attempt cap OR total time budget cap
    stop_condition = (stop_after_attempt(max_attempts) | stop_after_delay(settings.orch_retry_budget_s))

    # Full-jitter exponential backoff
    wait_policy = wait_random_exponential(multiplier=backoff_base_s, max=backoff_cap_s)

    async for attempt in AsyncRetrying(
        retry=retry_condition,
        stop=stop_condition,
        wait=wait_policy,
        reraise=True,
        before_sleep=_before_sleep_log,
    ):
        with attempt:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.NetworkError, httpx.RequestError) as e:
                # Treat network errors as retryable
                raise RetryableError(f"orchestrator network: {e}") from e

            sc = resp.status_code
            # Map status codes to our error classes
            if sc >= 500 or sc in (429, 503):
                txt = await _safe_text(resp)
                raise RetryableError(f"orchestrator {sc}: {txt}")
            if sc in (400, 422):
                txt = await _safe_text(resp)
                raise PermanentError(f"orchestrator {sc}: {txt}")

            try:
                return resp.json()
            except Exception:
                return {}

async def _safe_text(resp: httpx.Response) -> str:
    try:
        return resp.text[:2048]
    except Exception:
        return "<no-text>"

# -----------------------
# Routes
# -----------------------

@app.post("/pubsub/push")
async def pubsub_push(request: Request):
    await _verify_pubsub_auth(request)

    # Parse envelope
    try:
        envelope = PubSubEnvelope(**(await request.json()))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Pub/Sub envelope: {e}")

    msg = envelope.message
    msg_id = msg.messageId
    publish_time = msg.publishTime
    attributes = msg.attributes or {}

    # Decode message data
    try:
        payload = json.loads(base64.b64decode(msg.data).decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 data: {e}")

    bucket = payload.get("bucket")
    name = payload.get("name")
    generation = str(payload.get("generation", ""))
    metadata = payload.get("metadata") or {}
    session_id = metadata.get("session_id")

    if not bucket or not name or not generation:
        raise HTTPException(status_code=400, detail="Missing GCS fields")

    idem_key = make_idempotency_key(bucket, name, generation, session_id)
    doc_ref = db.collection(settings.firestore_collection).document(idem_key)

    jlog(
        event="received",
        request_id=msg_id,
        idempotency_key=idem_key,
        bucket=bucket,
        name=name,
        generation=generation,
        publish_time=publish_time,
        attributes=attributes,
    )

    action = await _firestore_tx_check_and_mark(
        doc_ref, bucket, name, generation, session_id, publish_time
    )
    if action == "DUPLICATE":
        jlog(event="duplicate_skip", request_id=msg_id, idempotency_key=idem_key)
        return Response(status_code=204)

    # Optional: handoff to Cloud Tasks instead of inline orchestrator call
    # enqueue_cloud_task_for_orchestrator(bucket, name, generation, session_id, idem_key, msg_id)
    # return Response(status_code=204)

    # Inline orchestrator call path
    start = time.time()
    try:
        orch_body = {
            "bucket": bucket,
            "name": name,
            "generation": generation,
            "metadata": {"session_id": session_id} if session_id else {},
        }

        jlog(
            event="orchestrator_call",
            request_id=msg_id,
            idempotency_key=idem_key,
            orch_body=orch_body,
        )

        async with app.state.orch_semaphore:
            client = app.state.httpx_client
            assert client is not None
            result = await call_orchestrator(orch_body, msg_id, idem_key, client)

        duration_ms = int((time.time() - start) * 1000)

        await to_thread.run_sync(
            doc_ref.set,
            {
                "status": "DONE",
                "last_updated": _now_iso(),
                "duration_ms": duration_ms,
                "final_outcome": result.get("final_outcome"), # type: ignore
                "last_error": None,
            },
            True,  # merge
        )

        jlog(
            event="done",
            request_id=msg_id,
            idempotency_key=idem_key,
            duration_ms=duration_ms,
            outcome=result.get("final_outcome"), # type: ignore
        )
        return Response(status_code=204)

    except RetryableError as e:
        await to_thread.run_sync(
            doc_ref.set,
            {
                "status": "FAILED_TRANSIENT",
                "last_updated": _now_iso(),
                "error": str(e),
                "last_error": str(e),
                "attempt_count": Increment(1),  # capture that we attempted and failed
            },
            True,
        )
        jlog(
            event="failed",
            step="orchestrator",
            retryable=True,
            error=str(e),
            request_id=msg_id,
            idempotency_key=idem_key,
        )
        # Return 5xx so Pub/Sub retries with backoff and eventually DLQs
        raise HTTPException(status_code=500, detail="Transient; retry")

    except PermanentError as e:
        await to_thread.run_sync(
            doc_ref.set,
            {
                "status": "FAILED_PERMANENT",
                "last_updated": _now_iso(),
                "error": str(e),
                "last_error": str(e),
            },
            True,
        )
        jlog(
            event="failed",
            step="orchestrator",
            retryable=False,
            error=str(e),
            request_id=msg_id,
            idempotency_key=idem_key,
        )
        # Ack (no retry); optionally notify HITL outside the worker
        return Response(status_code=204)

    except Exception as e:
        # Unknown error - prefer retry to avoid data loss
        await to_thread.run_sync(
            doc_ref.set,
            {
                "status": "FAILED_TRANSIENT",
                "last_updated": _now_iso(),
                "error": f"unexpected: {e}",
                "last_error": f"unexpected: {e}",
                "attempt_count": Increment(1),
            },
            True,
        )
        jlog(
            event="failed",
            step="unexpected",
            retryable=True,
            error=str(e),
            request_id=msg_id,
            idempotency_key=idem_key,
        )
        raise HTTPException(status_code=500, detail="Transient; retry")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "project_id": settings.project_id,
        "collection": settings.firestore_collection,
        "orchestrator_url": settings.orchestrator_url,
    }