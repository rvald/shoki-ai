import os
import json
import time
from openai import OpenAI
from opentelemetry import trace
from datetime import datetime
from prompts.hippa_compliance_prompts import system_prompt_v2
# Acquire a tracer
tracer = trace.get_tracer("generate_audit.tracer")


def generate_audit(
    transcript: str,
    model_name: str,
    prompt: str = system_prompt_v2,
    temperature: float = 0.4,
) -> str:
    
    BASE_URL = os.environ.get("OLLAMA_GCS_URL")
    
    client = OpenAI(
        base_url = f"{BASE_URL}/v1",
        api_key="dummy",
    )

    with tracer.start_as_current_span("AuditGeneration") as span:
        span.set_attribute("model_name", model_name)
        span.set_attribute("operation", "audit_generation")
        span.set_attribute("prompt", prompt)
        span.set_attribute("transcript", transcript)
        span.set_attribute("temperature", temperature)

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
            span.set_attribute("prompt_tokens", usage.prompt_tokens)
            span.set_attribute("completion_tokens", usage.completion_tokens)
            span.set_attribute("total_tokens", usage.total_tokens)

        span.set_attribute("latency_seconds", elapsed)
        span.set_attribute("response", response)

        # Optionally log the trace info as before
        audit_trace = {
            "input": transcript,
            "response": response,
            "latency_seconds": elapsed,
            "prompt_tokens": getattr(usage, 'prompt_tokens', None),
            "completion_tokens": getattr(usage, 'completion_tokens', None),
            "total_tokens": getattr(usage, 'total_tokens', None),
            "model_name": model_name,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "operation": "audit_generation",
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

        print(f"Predictions saved to {save_path}")

        return response