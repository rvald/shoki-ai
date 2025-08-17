import requests
import json, os

PRIVACY_API_BASE_URL = os.environ.get("PRIVACY_API_URL")

def redact_text(
    text: str
) -> dict:
    """
    Redact sensitive information from the given transcript.

    Args:
        text (str): The text to redact.
    
    Returns:
        dict: The response from the redaction API.
    
    Raises:
        requests.exceptions.RequestException: If the request to the API fails.
        json.JSONDecodeError: If the response cannot be parsed as JSON.
    """
    url = f"{PRIVACY_API_BASE_URL}/api/v1/redact"
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