from pydantic import BaseModel
from typing import Optional, Dict

class PubSubMessage(BaseModel):
    messageId: str
    data: str
    publishTime: Optional[str] = None  # RFC3339
    attributes: Optional[Dict[str, str]] = None

class PubSubEnvelope(BaseModel):
    message: PubSubMessage
    subscription: Optional[str] = None