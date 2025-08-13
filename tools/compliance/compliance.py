import requests
import json


def create_audit(
    transcript: str
) -> dict:
    """
    Create a compliance audit for the given transcript.

    Args:
        transcript (str): The transcript to audit.
    
    Returns:
        dict: The response from the compliance audit API.
    
    Raises:
        requests.exceptions.RequestException: If the request to the API fails.
        json.JSONDecodeError: If the response cannot be parsed as JSON.
    """
    url = "http://0.0.0.0:8001/api/v1/audit"
    headers = {"Content-Type": "application/json"}
    payload = {"transcript": transcript}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an error for bad responses
        return response.json()  # Return the JSON response from the API
    except requests.exceptions.RequestException as e:
        print(f"Error creating audit: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON response from {url}. Response text: {response.text}")
        return None

    