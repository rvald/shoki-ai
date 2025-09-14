from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# -----------------------
# Settings and constants
# -----------------------

class Settings(BaseSettings):
    project_id: str
    firestore_collection: str 
    orch_timeout_s: float = 120
    orch_max_retries: int = 2 # short client-side retries
    orch_backoff_base_ms: int = 200
    orch_backoff_cap_ms: int = 3000
    orch_concurrency: int = 64
    orch_retry_budget_s: float
    require_pubsub_auth: bool
    pubsub_push_audience: Optional[str] = None
    idem_ttl_days: int = 14
    include_session_in_idem: bool

    # Local dev defaults
    service_name: str

    # Pub/Sub topics
    transcribe_requested_topic: str
    transcribe_completed_topic: str
    
    redact_requested_topic: str 
    redact_completed_topic: str

    audit_requested_topic: str 
    audit_completed_topic: str 

    soap_requested_topic: str 
    soap_completed_topic: str 

    # Global settings configuration (Pydantic v2)
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


settings = Settings() # type: ignore