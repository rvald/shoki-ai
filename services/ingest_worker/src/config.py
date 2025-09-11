from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional 

# -----------------------
# Settings and constants
# -----------------------

class Settings(BaseSettings):
    
    # Prefer explicit env mappings to keep compatibility with existing env var names
    project_id: str 
    firestore_collection: str 
    orchestrator_url: str 
    orch_timeout_s: float = 120

    # Orchestrator retry tuning (client-side; keep small if Pub/Sub/Tasks do the heavy lifting)
    orch_max_retries: int 
    orch_backoff_base_ms: int
    orch_backoff_cap_ms: int
    orch_retry_budget_s: float

    # Concurrency and auth
    orch_concurrency: int = 64
    require_pubsub_auth: bool
    pubsub_push_audience: Optional[str]

    # Idempotency/TTL
    idem_ttl_days: int
    include_session_in_idem: bool

    # Local dev defaults
    service_name: str 

    # Global settings configuration (Pydantic v2)
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

settings = Settings() # type: ignore