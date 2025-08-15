from pydantic import BaseModel, Field

class RedactRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to redact")

class RedactResponse(BaseModel):
    text: str = Field(..., min_length=1, description="Redacted text after processing")