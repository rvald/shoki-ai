from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    
    model_config = SettingsConfigDict(env_file=".env",extra="ignore")

    # Core
    project_id: str 
    google_cloud_location: str 
    service_name: str 
    artifact_bucket: str 

    # Pub/Sub
    pubsub_enabled: bool
    audit_completed_topic: str 
    pubsub_publish_timeout_s: float
    pubsub_max_retries: int 
    pubsub_retry_budget_s: float
    pubsub_backoff_base_ms: int
    pubsub_backoff_cap_ms: int
    pubsub_require_auth: bool
    pubsub_push_audience: Optional[str]
    pubsub_enable_ordering: bool

    # Cloud Tasks
    task_queue_name: str
    task_queue_location:str
    tasks_service_url: str
    tasks_caller_sa: Optional[str] 
    tasks_audience: Optional[str] 

     # LLM/audit engine config
    audit_model: str 
    ollama_gcs_url: str
    audit_timeout_s: float

    # Local dev (no Pub/Sub)
    orchestrator_pubsub_url: Optional[str] = None

settings = Settings() # type: ignore