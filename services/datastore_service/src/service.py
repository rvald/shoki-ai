from google.cloud import storage, firestore
from .schemas import AudioFile, RedactedTranscript,SOAPNote
import os

GOOCLE_CLOUD_STORAGE_BUCKET = os.environ.get("GOOCLE_CLOUD_STORAGE_BUCKET")
GOOGLE_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
FIRESTORE_AUDIO_COLLECTION = os.environ.get("FIRESTORE_AUDIO_COLLECTION")

# store the audio file in gcp cloud storage
 # grab the public url of the file, and store a reference to in firestore
 # cloud store object will have:
    # 'file_path': path of the audio file 
    # 'audio_name': name of the audio file
def upload_audio_cloud_storage(
        audio_name: str,
        file_path: str
) -> dict:
    """
    Store the audio file in GCP Cloud Storage and return the public URL.

    Arguments:
        audio_name: Name of the audio file.
        file_path: Path of the audio file 

    Returns:
        Dictionary containing the public URL and metadata of the stored audio file.
    """

    storage_client = storage.Client()
    bucket = storage_client.bucket(GOOCLE_CLOUD_STORAGE_BUCKET)
    blob = bucket.blob(audio_name)

    try:
        blob.upload_from_filename(file_path)

        return {
            "public_url": blob.public_url,
            "audio_file_name": audio_name,
        }
    
    except Exception as e:
        print(f"Error uploading file {audio_name}: {e}")
        return {}
    
    
# firestore object will have:
    # 'public_url': public URL of the stored audio file
    # 'audio_file_name': name of the audio file
def upload_audio_firestore(
        public_url: str,
        audio_file_name: str
) -> dict:
    """
    Store the audio file metadata in Firestore.

    Arguments:
        public_url: Public URL of the stored audio file.
        audio_file_name: Name of the audio file.

    Returns:
        Dictionary containing the metadata of the stored audio file.
    """
    
    db = firestore.Client(project=GOOGLE_PROJECT_ID)
    audio_ref = db.collection(FIRESTORE_AUDIO_COLLECTION)
    audio_ref.document(audio_file_name).set(
        AudioFile(
            public_url=public_url,
            audio_name=audio_file_name
        ).model_dump()
    )

    doc_ref = audio_ref.document(audio_file_name)
    doc = doc_ref.get()
    result = doc.to_dict() if doc.exists else {}

    return result


# store the anonymized  transcript in firestore
 # firestore object will have:
    # 'id': unique identifier for the trancription
    # 'redacted_text': the redacted transcribed text
    # 'audio_id': unique identifier for the audio file
    # 'created_at': timestamp of when the object was created

def upload_redacted_transcript_firestore(
        redacted_text: str,
) -> dict:
    """
    Store the redacted transcript in Firestore.

    Arguments:
        redacted_text: The redacted transcribed text.
        audio_id: Unique identifier for the audio file in Firestore.
    """

    db = firestore.Client(project=GOOGLE_PROJECT_ID)
    audio_ref = db.collection("redacted_transcripts")
    audio_ref.document(audio_file_name).set(
        RedactedTranscript(
            redacted_text=redacted_text,
            audio_file_name=audio_file_name,
            audio_id=audio_id
        ).model_dump()
    )

    doc_ref = audio_ref.document(audio_file_name)
    doc = doc_ref.get()
    result = doc.to_dict() if doc.exists else {}

    return result

# store the generated soap_note in firestore
 # firestore object will have:
    # 'id': unique identifier for the soap note
    # 'soap_note': the generated SOAP note text
    # 'redacted_id': unique identifier for the redacted transcript
    # 'created_at': timestamp of when the object was created

def upload_soap_note_firestore(
        soap_note: str,
        redacted_id: str,
        audio_file_name: str
) -> dict:
    """
    Store the generated SOAP note in Firestore.

    Arguments:
        soap_note: The generated SOAP note text.
        redacted_id: Unique identifier for the redacted transcript.
    """

    db = firestore.Client(project=GOOGLE_PROJECT_ID)
    soap_ref = db.collection("soap_notes")
    soap_ref.document(audio_file_name).set(
        SOAPNote(
            soap_note=soap_note,
            redacted_id=redacted_id
        ).model_dump()
    )

    doc_ref = soap_ref.document(audio_file_name)
    doc = doc_ref.get()
    result = doc.to_dict() if doc.exists else {}

    return result


