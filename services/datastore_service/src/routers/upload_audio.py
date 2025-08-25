from fastapi import APIRouter, UploadFile, File, Form, status
import os
from pathlib import Path
from ..service import upload_audio_cloud_storage, upload_audio_firestore, caf_to_wav
from ..schemas import AudoFileResponse

router = APIRouter()    
TMP_DIR = Path("temp_audio")
TMP_DIR.mkdir(parents=True, exist_ok=True)

@router.post(
    "/upload_audio",
    summary="Store audio file",
    description="Store an audio file in GCP Cloud Storage and Firestore.",
    response_model=AudoFileResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_audio(
    audio_file: UploadFile = File(...), 
    audio_name: str | None = Form(None)
) -> AudoFileResponse:
    """
    Upload an audio file to GCP Cloud Storage and store its metadata in Firestore.

    Args:
        audio_file (UploadFile): The audio file to be uploaded.
        audio_name (str, optional): The name of the audio file. If not provided, it will be derived from the file name.

    Returns:
        dict: A dictionary containing the public URL and metadata of the stored audio file.
    """
    # Extract audio name and file path from the uploaded file
    if not audio_name:
        audio_name = audio_file.filename

    tmp_file_path = f"temp_audio/{audio_name}"

    try:
        # Save the uploaded file to the temporary location
        with open(tmp_file_path, "wb") as f:
            f.write(await audio_file.read())

        wav_out = caf_to_wav(tmp_file_path)

        # Store the audio file in GCP Cloud Storage
        storage_response = upload_audio_cloud_storage(audio_name, wav_out)

        # Store the audio file metadata in Firestore
        firestore_response = upload_audio_firestore(
            public_url=storage_response.get("public_url"),
            audio_file_name=storage_response.get("audio_file_name"),
        )
        
        id = firestore_response.get('id')
        public_url = firestore_response.get('public_url')
        audio_name = firestore_response.get('audio_name')
        created_at = firestore_response.get('created_at')

        # Return the response model with the stored audio file metadata
        return AudoFileResponse(
            id=id,
            public_url=public_url,
            audio_name=audio_name,
            created_at=created_at
        )
    

    except Exception as e:
        return {"error": f"Failed to save the audio file: {str(e)}"}
    
    finally:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

   
