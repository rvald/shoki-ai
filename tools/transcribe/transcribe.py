import requests, os, json

TRANSCRIBE_API_URL = os.environ.get("TRANSCRIBE_API_URL")

def transcribe_audio(
    audio_file_name: str
) -> dict:
    
    """
    Transcribe audio file using the transcription service API. 

    Args:
        audio_file_name (str): Name of the audio file.

    Returns:
        dict: The transcription result from the API.

    Raises:
        requests.exceptions.RequestException: If the request to the API fails.
        json.JSONDecodeError: If the response cannot be parsed as JSON.
    """
    
    url = f"{TRANSCRIBE_API_URL}/api/v1/transcribe_audio"
    headers = {"Content-Type": "application/json"}
    payload = {"audio_file_name": audio_file_name}
    
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