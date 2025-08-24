import requests
import json, os

DATASTORE_API_URL = "http://localhost:5050"         #os.environ.get("DATASTORE_API_URL")

def upload_soap_note(
    soap_note: str,
    redacted_id: str,
    audio_file_name: str
) -> dict:
    """
    Upload a SOAP note to the datastore.

    Args:
        soap_note (str): The generated SOAP note text.
        redacted_id (str): Unique identifier for the redacted transcript.
        audio_file_name (str): Name of the audio file associated with the SOAP note.
    
    Returns:
        dict: The response from the datastore API.
    
    Raises:
        requests.exceptions.RequestException: If the request to the API fails.
        json.JSONDecodeError: If the response cannot be parsed as JSON.
    """
    url = f"{DATASTORE_API_URL}/api/v1/soap_note"
    headers = {"Content-Type": "application/json"}
    payload = {"soap_note": soap_note, "redacted_id": redacted_id, "audio_file_name": audio_file_name}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status() 
        return response.json() 
    except requests.exceptions.RequestException as e:
        print(f"Error uploading SOAP note: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON response from {url}. Response text: {response.text}")
        return None
    

def upload_redacted_transcript(
        redacted_text: str,
        audio_id: str,
        audio_file_name: str
) -> dict:
    """
    Store the redacted transcript in Firestore.

    Arguments:
        redacted_text: The redacted transcribed text.
        audio_id: Unique identifier for the audio file in Firestore.
        audio_file_name: Name of the audio file associated with the transcript.     
    Returns:
        Dictionary containing the metadata of the stored redacted transcript.
    """

    url = f"{DATASTORE_API_URL}/api/v1/transcript"
    headers = {"Content-Type": "application/json"}
    payload = {"redacted_text": redacted_text, "audio_id": audio_id, "audio_file_name": audio_file_name}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status() 
        return response.json() 
    except requests.exceptions.RequestException as e:
        print(f"Error uploading SOAP note: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON response from {url}. Response text: {response.text}")
        return None