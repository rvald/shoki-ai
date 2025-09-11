import os, json
from typing import Optional
from google.cloud import storage
from .schemas import RedactResponse

PROJECT_ID = os.getenv("PROJECT_ID")
ARTIFACT_BUCKET = os.getenv("PRIVACY_ARTIFACT_BUCKET") or "shoki-ai-privacy-service"

_storage = storage.Client(project=PROJECT_ID) if PROJECT_ID else storage.Client()

def artifact_blob_path(idempotency_key: str) -> str:
    return f"artifacts/{idempotency_key}/redacted.json"

# load data from GCS given a bucket uri 
def download_blob(
    bucket_name: str,
    blob_name: str   
) -> dict:
    if not bucket_name or not blob_name:
        raise ValueError("Invalid bucket or blob name")
    
    path = f"artifacts/{blob_name}/transcript.json"
    bucket = _storage.bucket(bucket_name)
    blob = bucket.blob(path)
    data = json.loads(blob.download_as_text())
    return data

def load_artifact(idempotency_key: Optional[str]) -> Optional[RedactResponse]:
    if not (ARTIFACT_BUCKET and idempotency_key):
        return None
    bucket = _storage.bucket(ARTIFACT_BUCKET)
    blob = bucket.blob(artifact_blob_path(idempotency_key))
    if not blob.exists():
        return None
    data = json.loads(blob.download_as_text())
    return RedactResponse.model_validate(data)

def save_artifact(idempotency_key: Optional[str], resp: RedactResponse) -> None:
    if not (ARTIFACT_BUCKET and idempotency_key):
        return
    bucket = _storage.bucket(ARTIFACT_BUCKET)
    blob = bucket.blob(artifact_blob_path(idempotency_key))
    blob.upload_from_string(resp.model_dump_json(indent=2), content_type="application/json")