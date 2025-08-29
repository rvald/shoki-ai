import os, json
from typing import Optional
from google.cloud import storage
from .schemas import AuditResponse

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
ARTIFACT_BUCKET = os.getenv("COMPLIANCE_ARTIFACT_BUCKET")
_storage = storage.Client(project=PROJECT_ID) if PROJECT_ID else storage.Client()

def artifact_blob_path(idempotency_key: str) -> str:
    return f"artifacts/{idempotency_key}/audit.json"

def load_artifact(idempotency_key: Optional[str]) -> Optional[AuditResponse]:
    if not (ARTIFACT_BUCKET and idempotency_key):
        return None
    bucket = _storage.bucket(ARTIFACT_BUCKET)
    blob = bucket.blob(artifact_blob_path(idempotency_key))
    if not blob.exists():
        return None
    data = json.loads(blob.download_as_text())
    return AuditResponse.model_validate(data)

def save_artifact(idempotency_key: Optional[str], resp: AuditResponse) -> None:
    if not (ARTIFACT_BUCKET and idempotency_key):
        return
    bucket = _storage.bucket(ARTIFACT_BUCKET)
    blob = bucket.blob(artifact_blob_path(idempotency_key))
    blob.upload_from_string(resp.model_dump_json(indent=2), content_type="application/json")