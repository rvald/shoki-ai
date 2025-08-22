from fastapi import APIRouter, status
from ..service import transcribe_audio, download_blob
from ..schemas import TranscriptionRequest

router = APIRouter()

@router.post(  
    "/transcribe_audio",
    summary="Transcribe audio file",
    description="Transcribe an audio file stored in GCP Cloud Storage.",
    status_code=status.HTTP_200_OK
)
async def transcribe_audio_endpoint(
    payload: TranscriptionRequest,
) -> dict:
    """
    Transcribe an audio file stored in GCP Cloud Storage.

    Args:
        audio_file_name (str): The name of the audio file in GCP Cloud Storage.
    Returns:
        dict: A dictionary containing the transcription result, including text, language, segments, duration, model used, and timestamp.
    """
    try:
        # Download the audio file from GCP Cloud Storage
        tmp_file_path = download_blob(payload.audio_file_name)

        # Transcribe the audio file
        transcription_result = transcribe_audio(tmp_file_path, payload.audio_file_name)

        return transcription_result
    
    except Exception as e:
        print(f"Transcription failed: {str(e)}")
        return {"error": str(e)}
