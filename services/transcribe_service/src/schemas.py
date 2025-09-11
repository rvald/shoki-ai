from typing import List, Optional
from pydantic import BaseModel, Field

class Segment(BaseModel):
    start: float
    end: float
    text: str

class Transcription(BaseModel):
    text: str
    language: Optional[str] = None
    segments: List[Segment] = []
    duration: Optional[float] = None
    model_used: Optional[str] = None
    timestamp: str

class TranscriptionRequest(BaseModel):
    # Required; your orchestrator will pass the same fields it received
    name: str
    bucket: Optional[str] = None           # if you prefer env bucket, leave None
    generation: Optional[str] = None       # helps idempotency; include if known
    language_hint: Optional[str] = None

class TranscriptionResponse(BaseModel):
    transcription: Transcription
    audio_name: str
    version: str = "v1"