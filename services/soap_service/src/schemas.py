from pydantic import BaseModel, Field

class SoapNoteRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Transcript text to use for generating SOAP note")

class SoapNoteRequestResponse(BaseModel):
    soap_note: str = Field(..., min_length=1, description="Generated SOAP note from the transcript")