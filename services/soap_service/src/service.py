import os
import json
import time
from openai import OpenAI
from datetime import datetime
from .prompt import system_prompt


def generate_soap_note(
    transcript: str,
    model_name: str,
    prompt: str = system_prompt,
    temperature: float = 0.4,
) -> str:
    
    BASE_URL = os.environ.get("OLLAMA_GCS_URL")
    
    client = OpenAI(
        base_url = f"{BASE_URL}/v1",
        api_key="dummy",
    )

    start_time = time.time()
    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
        temperature=temperature,
    )
    elapsed = time.time() - start_time

    response = completion.choices[0].message.content.strip()
    usage = getattr(completion, "usage", None)

    if usage:
        # Optionally log the trace info as before
        prompt_tokens = getattr(usage, 'prompt_tokens', None)
        completion_tokens = getattr(usage, 'completion_tokens', None)
        total_tokens = getattr(usage, 'total_tokens', None)
    
    audit_trace = {
        "input": transcript,
        "response": response,
        "latency_seconds": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "model_name": model_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "operation": "soap_note_generation",
    }

    # Get parent of current working directory
    parent_dir = os.path.dirname(os.getcwd())

    # Full path for traces directory inside the parent directory
    trace_dir = os.path.join(parent_dir, "observability", "traces")

    # Make the directory if it doesn't exist
    os.makedirs(trace_dir, exist_ok=True)

    # Use full path when saving the file (join with trace_dir)
    filename = f"audit_generation_{datetime.now().isoformat()}.json"
    save_path = os.path.join(trace_dir, filename)
    
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(audit_trace, f, indent=2, ensure_ascii=False)

    return response