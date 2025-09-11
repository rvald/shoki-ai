from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class RunResponse(BaseModel):
    status: str
    idem_key: str
    details: Optional[Dict[str, Any]] = None
    version: str = "v1"

class RunCreate(BaseModel):
    bucket: str
    name: str
    generation: Optional[str] = None
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
