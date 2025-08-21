from fastapi import APIRouter, status, Body
from ..service import upload_redacted_transcript_firestore

router = APIRouter()

@router.post(
    "/transcript",
    summary="Store Transcript",
    description="Store a transcript in the datastore.",
    status_code=status.HTTP_201_CREATED
)
async def upload_transcript(
    redacted_text: str = Body(...),
    audio_id: str = Body(...),
    audio_file_name: str = Body(...)
):
    """
    Upload a transcript to Firestore.

    Args:
        redacted_text (str): The redacted transcribed text.
        audio_id (str): Unique identifier for the audio file in Firestore.
        audio_file_name (str): Name of the audio file.

    Returns:
        dict: A dictionary containing the metadata of the stored transcript.
    """
    try:    
        # Store the redacted transcript in Firestore
        firestore_response = upload_redacted_transcript_firestore(
            redacted_text=redacted_text,
            audio_id=audio_id,
            audio_file_name=audio_file_name
        )
        print("Transcript stored successfully:", firestore_response)

    except Exception as e:
        return {"error": f"Failed to save the transcript: {str(e)}"}