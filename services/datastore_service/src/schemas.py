from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

# Schema for audio files in Firestore document and API request/responses
class AudioFile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    public_url: str
    audio_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "json_encoders": { datetime: lambda v: v.isoformat() }
    }

class AudoFileResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the audio file.")
    public_url: str = Field(..., description="Public URL of the stored audio file.")
    audio_name: str = Field(..., description="Name of the audio file.")
    created_at: datetime = Field(..., description="Timestamp of when the audio file was created.")
    
    model_config = {
        "json_encoders": { datetime: lambda v: v.isoformat() }
    }   

# Schema for redacted transcripts in Firestore document and API request/responses
class RedactedTranscript(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    redacted_text: str
    audio_id: str
    audio_file_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "json_encoders": { datetime: lambda v: v.isoformat() }
    }


class RedactedTranscriptRequest(BaseModel):
    redacted_text: str = Field(..., description="The redacted transcribed text.")
    audio_id: str = Field(..., description="Unique identifier for the audio file in FireStore.")
    audio_file_name: str = Field(..., description="Name of the audio file associated with the transcript.")


class RedactedTranscriptResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the redacted transcript.")
    redacted_text: str = Field(..., description="The redacted transcribed text.")
    audio_id: str = Field(..., description="Unique identifier for the audio file in FireStore.")
    audio_file_name: str = Field(..., description="Name of the audio file associated")
    created_at: datetime = Field(..., description="Timestamp of when the redacted transcript was created.")
    
    model_config = {
        "json_encoders": { datetime: lambda v: v.isoformat() }
    }

# Schema for soap notes in Firestore document and API request/responses
class SOAPNote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    soap_note: str
    redacted_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "json_encoders": { datetime: lambda v: v.isoformat() }
    }


class SOAPNoteRequest(BaseModel):
    soap_note: str = Field(..., description="The generated SOAP note text.")
    redacted_id: str = Field(..., description="Unique identifier for the redacted transcript in FireStore.")
    audio_file_name: str = Field(..., description="Name of the audio file associated with the SOAP note.")


class SOAPNoteResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the SOAP note.")
    soap_note: str = Field(..., description="The generated SOAP note text.")
    redacted_id: str = Field(..., description="Unique identifier for the redacted transcript in FireStore.")
    created_at: datetime = Field(..., description="Timestamp of when the SOAP note was created.")
    
    model_config = {
        "json_encoders": { datetime: lambda v: v.isoformat() }
    }