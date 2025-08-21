import uuid
from datetime import datetime, timezone

class AudioFile:
    def __init__(
            self, 
            public_url: str,
            audio_name: str
    ):
        self.id = str(uuid.uuid4())
        self.public_url = public_url
        self.audio_name = audio_name
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """
        Convert the AudioFile object to a dictionary representation.

        Returns:
            Dictionary containing the file path and audio name.
        """
        return {
            "id": self.id,
            "public_url": self.public_url,
            "created_at": self.created_at.isoformat(),
            "audio_name": self.audio_name
        }
    
class RedactedTranscript:
    def __init__(
            self, 
            redacted_text: str,
            audio_id: str,
            audio_file_name: str
    ):
        self.id = str(uuid.uuid4())
        self.redacted_text = redacted_text
        self.audio_id = audio_id
        self.audio_file_name = audio_file_name
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """
        Convert the RedactedTranscript object to a dictionary representation.

        Returns:
            Dictionary containing the redacted text, audio ID, and creation timestamp.
        """
        return {
            "id": self.id,
            "redacted_text": self.redacted_text,
            "audio_id": self.audio_id,
            "audio_file_name": self.audio_file_name,
            "created_at": self.created_at.isoformat()
        }   
    
class SOAPNote:
    def __init__(
            self, 
            soap_note: str,
            redacted_id: str
    ):
        self.id = str(uuid.uuid4())
        self.soap_note = soap_note
        self.redacted_id = redacted_id
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """
        Convert the SOAPNote object to a dictionary representation.

        Returns:
            Dictionary containing the SOAP note text, redacted ID, and creation timestamp.
        """
        return {
            "id": self.id,
            "soap_note": self.soap_note,
            "redacted_id": self.redacted_id,
            "created_at": self.created_at.isoformat()
        }