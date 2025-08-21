from fastapi import APIRouter, status, Body
from ..service import upload_soap_note_firestore
from ..schemas import SOAPNoteRequest, SOAPNoteResponse

router = APIRouter()

@router.post(
    "/soap_note",
    summary="Store SOAP Note",
    description="Store a SOAP note in the datastore.",
    response_model=SOAPNoteResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_soap_note(
    payload: SOAPNoteRequest
) -> SOAPNoteResponse:
    """
    Upload a SOAP note to Firestore.

    Args:
        soap_note (str): The generated SOAP note text.
        redacted_id (str): Unique identifier for the redacted transcript.
        audio_file_name (str): Name of the audio file associated with the SOAP note.

    Returns:
        dict: A dictionary containing the metadata of the stored SOAP note.
    """
    try:    
        # Store the SOAP note in Firestore
        response = upload_soap_note_firestore(
            soap_note=payload.soap_note,
            redacted_id=payload.redacted_id,
            audio_file_name=payload.audio_file_name
        )

        id = response.get('id')
        soap_note = response.get('soap_note')
        redacted_id = response.get('redacted_id')
        created_at = response.get('created_at')
        
        return SOAPNoteResponse(
            id=id,
            soap_note=soap_note,
            redacted_id=redacted_id,
            created_at=created_at
        )

    except Exception as e:
        return {"error": f"Failed to save the SOAP note: {str(e)}"}
