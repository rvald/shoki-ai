import os, json, tempfile
from pathlib import Path
from typing import Optional
from google.cloud import storage
from .schemas import TranscriptionResponse

AUDIO_BUCKET = os.environ.get("GOOGLE_CLOUD_STORAGE_BUCKET")
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

storage_client = storage.Client(project=PROJECT_ID)

def artifact_blob_path(idempotency_key: str) -> str:
    return f"artifacts/{idempotency_key}/transcript.json"

def load_artifact(idempotency_key: Optional[str]) -> Optional[TranscriptionResponse]:
    if not (ARTIFACT_BUCKET and idempotency_key):
        return None
    bucket = storage_client.bucket(ARTIFACT_BUCKET)
    blob = bucket.blob(artifact_blob_path(idempotency_key))
    if not blob.exists():
        return None
    data = json.loads(blob.download_as_text())
    return TranscriptionResponse.model_validate(data)

def save_artifact(idempotency_key: Optional[str], resp: TranscriptionResponse) -> None:
    if not (ARTIFACT_BUCKET and idempotency_key):
        return
    bucket = storage_client.bucket(ARTIFACT_BUCKET)
    blob = bucket.blob(artifact_blob_path(idempotency_key))
    blob.upload_from_string(resp.model_dump_json(indent=2), content_type="application/json")

def download_blob_to_tmp(audio_file_name: str, bucket_name: Optional[str] = None) -> str:
    """Downloads GCS object to a temp file and returns its local path."""
    bucket_name = bucket_name or AUDIO_BUCKET
    if not bucket_name:
        raise ValueError("No bucket provided and GOOGLE_CLOUD_STORAGE_BUCKET not set")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(audio_file_name)
    if not blob.exists():
        raise FileNotFoundError(f"Blob {audio_file_name} not found in bucket {bucket_name}")

    tmp_dir = Path(tempfile.gettempdir()) / "transcribe_audio"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / audio_file_name.replace("/", "_")
    blob.download_to_filename(str(tmp_path))
    return str(tmp_path)