import os
from datetime import datetime, timezone
from google.cloud import storage
from pathlib import Path
import whisper


GOOGLE_CLOUD_STORAGE_BUCKET = os.environ.get("GOOGLE_CLOUD_STORAGE_BUCKET")
GOOGLE_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
WHISPER_MODEL_SIZE  = "small" 

def download_blob(
    audio_file_name: str, 
) -> str:
    
    """Download a blob from GCS bucket"""
    try:
        TMP_DIR = Path("temp_audio")
        TMP_DIR.mkdir(parents=True, exist_ok=True)

        tmp_file_path = f"temp_audio/{audio_file_name}"

        storage_client = storage.Client(project=GOOGLE_PROJECT_ID)
        bucket = storage_client.bucket(GOOGLE_CLOUD_STORAGE_BUCKET)
        blob = bucket.blob(audio_file_name)
        
        if not blob.exists():
            raise FileNotFoundError(f"Blob {audio_file_name} not found in bucket {GOOGLE_CLOUD_STORAGE_BUCKET}")
        
        blob.download_to_filename(tmp_file_path)
        
        return tmp_file_path
        
    except Exception as e:
        print(f"Error downloading blob: {e}")

def transcribe_audio(
    file_path: str,
    audio_file_name: str
) -> dict:
    
    """Process audio transcription job"""
    try:

        whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)

        # Transcribe with options for better accuracy and speed
        result = whisper_model.transcribe(
            file_path,
            language=None,
            task="transcribe",
            verbose=False
        )

        # Process transcription results
        segments = []
        for segment in result.get("segments", []):
            segments.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip()
            })
        
        # Prepare transcription data
        transcription_data = {
            "text": result["text"].strip(),
            "language": result["language"],
            "segments": segments,
            "duration": result.get("duration", 0),
            "model_used": WHISPER_MODEL_SIZE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        return {
            "transcription": transcription_data,
            "audio_name": audio_file_name
        }
        
    except Exception as e:
        print(f"Transcription failed: {str(e)}")
    
    finally:
        # Delete only the temp file
        try:
            p = Path(file_path)
            if p.exists() and p.is_file():
                p.unlink()
        except OSError as e:
            print(f"Error deleting temp file '{file_path}': {e}")
 

