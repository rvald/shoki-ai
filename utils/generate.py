import os
import json
import time
from openai import OpenAI

def generate_response(
    prompt: str,
    inputs: list[str],
    model_name: str,
    experiment_name: str = "default_generation",
    temperature: float = 0.4,
) -> list[str]:
    """
    Generates predictions, token usage, and latency, and saves them to experiments/predictions/{experiment_name}.json.
    Returns the list of predictions.
    """
    predictions = []

    client = OpenAI(
        base_url="http://localhost:11434/v1",  
        api_key="dummy",
    )

    for user_input in inputs:

        start_time = time.time()
        
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=temperature,
        )
        elapsed = time.time() - start_time
        prediction = completion.choices[0].message.content.strip()

        # Try to extract token usage data
        usage = getattr(completion, "usage", None)
        if usage:
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
        else:
            # If your API doesn't return usage, set as None or estimate if possible
            prompt_tokens = completion_tokens = total_tokens = None

        predictions.append({
            "input": user_input,
            "prediction": prediction,
            "latency_seconds": elapsed,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        })

    # Save to ./experiments/predictions/
    os.makedirs("experiments/predictions", exist_ok=True)
    save_path = os.path.join("experiments", "predictions", f"{experiment_name}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, ensure_ascii=False)
    print(f"Predictions saved to {save_path}")

    # Just predictions (text) if you want to use for eval
    return [x["prediction"] for x in predictions]