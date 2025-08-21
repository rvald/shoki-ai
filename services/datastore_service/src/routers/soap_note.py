from fastapi import APIRouter, status, Body
from ..service import upload_soap_note_firestore

router = APIRouter()

@router.post(
    "/soap_note",
    summary="Store SOAP Note",
    description="Store a SOAP note in the datastore.",
    status_code=status.HTTP_201_CREATED
)
async def upload_soap_note(
    soap_note: str = Body(...),
    redacted_id: str = Body(...),
    audio_file_name: str = Body(...)
):
    """
    Upload a SOAP note to Firestore.

    Args:
        soap_note (str): The generated SOAP note text.
        redacted_id (str): Unique identifier for the redacted transcript.

    Returns:
        dict: A dictionary containing the metadata of the stored SOAP note.
    """
    try:    
        # Store the SOAP note in Firestore
        firestore_response = upload_soap_note_firestore(
            soap_note=soap_note,
            redacted_id=redacted_id,
            audio_file_name=audio_file_name
        )
        print("SOAP Note stored successfully:", firestore_response)

    except Exception as e:
        return {"error": f"Failed to save the SOAP note: {str(e)}"}
