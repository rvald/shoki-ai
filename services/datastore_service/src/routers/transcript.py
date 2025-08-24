from fastapi import APIRouter, status, Body
from ..service import upload_redacted_transcript_firestore
from ..schemas import RedactedTranscriptRequest, RedactedTranscriptResponse

router = APIRouter()

@router.post(
    "/transcript",
    summary="Store Transcript",
    response_model=RedactedTranscriptResponse,
    description="Store a transcript in the datastore.",
    status_code=status.HTTP_201_CREATED
)
async def upload_transcript(
    payload: RedactedTranscriptRequest
) -> RedactedTranscriptResponse:
    """
    Upload a transcript to Firestore.

    Args:
        redacted_text (str): The redacted transcribed text.

    Returns:
        dict: A dictionary containing the metadata of the stored transcript.
    """
    try:    
        # Store the redacted transcript in Firestore
        firestore_response = upload_redacted_transcript_firestore(
            redacted_text=payload.redacted_text
        )
        
        id = firestore_response.get('id')
        redacted_text = firestore_response.get('redacted_text')
        audio_id = firestore_response.get('audio_id')
        audio_file_name = firestore_response.get('audio_file_name')
        created_at = firestore_response.get('created_at')

        return RedactedTranscriptResponse(
            id=id,
            redacted_text=redacted_text,
            audio_id=audio_id,
            audio_file_name=audio_file_name,
            created_at=created_at
        )

    except Exception as e:
        return {"error": f"Failed to save the transcript: {str(e)}"}