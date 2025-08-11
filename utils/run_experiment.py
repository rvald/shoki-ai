import os
import json
from datetime import datetime

from . import generate
from . import evaluate

def run_experiment(
    experiment_name: str,
    prompt: str,
    inputs: list[str],
    targets: list[str],
    model_under_test: str,
    evaluator_model: str,
    temperature: float = 0.4
):
    """
    Runs a full experiment: generate, evaluate, and save results with metadata.

    Args:
        experiment_name: unique name for this run (shared by output files)
        prompt: system prompt for the test model
        inputs: list of input strings
        targets: list of ground-truth / expected output strings
        model_under_test: the model used for predictions
        evaluator_model: the model used for evaluating
        temperature: decoding temp for test model
    """
    # --- STEP 1: GENERATE (calls your upgraded 'generate' function) ---
    print(f"[{datetime.now().isoformat()}] [{experiment_name}] Generating predictions...")
    predictions = generate.generate_response(
        prompt=prompt,
        inputs=inputs,
        model_name=model_under_test,
        experiment_name=experiment_name,
        temperature=temperature
    )  # returns a list[str] for evaluation

    # --- STEP 2: EVALUATE (calls your 'evaluate_model' function) ---
    print(f"[{datetime.now().isoformat()}] [{experiment_name}] Evaluating predictions...")
    evaluate.evaluate_model(
        inputs=inputs,
        outputs=targets,
        model_responses=predictions,
        model=evaluator_model,
        experiment_name=experiment_name
    )

    # --- STEP 3: LOG RUN METADATA ---
    os.makedirs("experiments/run_metadata", exist_ok=True)
    run_meta = {
        "experiment_name": experiment_name,
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "num_examples": len(inputs),
        "model_under_test": model_under_test,
        "evaluator_model": evaluator_model,
        "temperature": temperature,
        "prediction_path": f"experiments/predictions/{experiment_name}.json",
        "evaluation_path": f"experiments/evaluations/{experiment_name}.json"
    }
    meta_path = os.path.join("experiments", "run_metadata", f"{experiment_name}.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(run_meta, f, indent=2, ensure_ascii=False)

    # --- STEP 4: PRINT SUMMARY ---
    print(f"Run {experiment_name} complete!")
    print(f"Predictions: {run_meta['prediction_path']}")
    print(f"Evaluations: {run_meta['evaluation_path']}")
    print(f"Metadata:    {meta_path}")
   