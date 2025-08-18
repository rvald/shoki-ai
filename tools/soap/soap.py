import requests
import json, os

SOAP_SERVICE_API_BASE_URL = os.environ.get("SOAP_SERVICE_API_URL")

def generate_soap_note(
    text: str
) -> dict:
    """
    Generate soap note for transcript.

    Args:
        text (str): The transcript for the soap note.
    
    Returns:
        dict: The response from the soap service API.
    
    Raises:
        requests.exceptions.RequestException: If the request to the API fails.
        json.JSONDecodeError: If the response cannot be parsed as JSON.
    """
    url = f"{SOAP_SERVICE_API_BASE_URL }/api/v1/soap_note"
    headers = {"Content-Type": "application/json"}
    payload = {"text": text}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an error for bad responses
        return response.json()  # Return the JSON response from the API
    except requests.exceptions.RequestException as e:
        print(f"Error redacting text: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON response from {url}. Response text: {response.text}")
        return None