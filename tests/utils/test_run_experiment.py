import json
import importlib
import sys
import textwrap

"""
This test creates a tiny, temporary package at runtime to host
pkg.runner.run_experiment along with pkg.runner.generate and
pkg.runner.evaluate. We patch those submodules to avoid real
API calls and to deterministically verify behavior.
"""

def _setup_temp_package(tmp_path):
    base = tmp_path / "pkg"
    runner = base / "runner"
    runner.mkdir(parents=True, exist_ok=True)

    # __init__ files to make proper packages
    (base / "__init__.py").write_text("")
    (runner / "__init__ .py").write_text("")  # keep existing structure; no change

    # run_experiment.py (the subject under test)
    run_experiment_code = textwrap.dedent("""
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
        \"\"\"
        Runs a full experiment: generate, evaluate, and save results with metadata.

        Args:
            experiment_name: unique name for this run (shared by output files)
            prompt: system prompt for the test model
            inputs: list of input strings
            targets: ground-truth / expected output strings
            model_under_test: the model used for predictions
            evaluator_model: the model used for evaluating
            temperature: decoding temp for test model
        \"\"\"
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
    """)
    (runner / "run_experiment.py").write_text(run_experiment_code)

    # pkg.runner.generate module (stubbed; we'll patch its function)
    generate_code = textwrap.dedent("""
    def generate_response(prompt, inputs, model_name, experiment_name, temperature):
        # Real implementation would call an API; tests will patch this function.
        raise NotImplementedError("This is a stub for tests.")
    """)
    (runner / "generate.py").write_text(generate_code)

    # pkg.runner.evaluate module (stubbed; we'll patch its function)
    evaluate_code = textwrap.dedent("""
    def evaluate_model(inputs, outputs, model_responses, model, experiment_name):
        # Real implementation would call an evaluator; tests patch this.
        raise NotImplementedError("This is a stub for tests.")
    """)
    (runner / "evaluate.py").write_text(evaluate_code)

    return base

def test_run_experiment_integrated_flow(tmp_path, monkeypatch, capsys):
    # Set up the temporary package structure
    pkg_base = _setup_temp_package(tmp_path)

    # Add tmp_path to sys.path so we can import pkg.runner.run_experiment
    sys.path.insert(0, str(tmp_path))

    # Import the module under test
    run_exp_module = importlib.import_module("pkg.runner.run_experiment")

    # Create fake implementations to patch into the run_experiment module
    called = {}

    def fake_generate_response(prompt, inputs, model_name, experiment_name, temperature):
        called['generate'] = {
            "prompt": prompt,
            "inputs": inputs,
            "model_name": model_name,
            "experiment_name": experiment_name,
            "temperature": temperature
        }
        return ["P1", "P2"]

    def fake_evaluate_model(inputs, outputs, model_responses, model, experiment_name):
        called['evaluate'] = {
            "inputs": inputs,
            "outputs": outputs,
            "model_responses": model_responses,
            "model": model,
            "experiment_name": experiment_name
        }

    # Patch the submodules' functions
    monkeypatch.setattr(run_exp_module.generate, "generate_response", fake_generate_response)
    monkeypatch.setattr(run_exp_module.evaluate, "evaluate_model", fake_evaluate_model)

    # Patch datetime used in run_experiment to deterministic value
    class FakeDateTime:
        @classmethod
        def now(cls):
            class _Dt:
                def isoformat(self):
                    return "2024-01-01T00:00:00"
            return _Dt()

    monkeypatch.setattr(run_exp_module, "datetime", FakeDateTime)

    # Change working dir to tmp_path so the metadata file goes under tmp_path/experiments/...
    monkeypatch.chdir(tmp_path)

    # Run
    experiment_name = "test_run"
    prompt = "PROMPT"
    inputs = ["i1", "i2"]
    targets = ["t1", "t2"]
    model_under_test = "model-A"
    evaluator_model = "model-B"
    temperature = 0.7

    run_exp_module.run_experiment(
        experiment_name=experiment_name,
        prompt=prompt,
        inputs=inputs,
        targets=targets,
        model_under_test=model_under_test,
        evaluator_model=evaluator_model,
        temperature=temperature,
    )

    # Capture prints
    captured = capsys.readouterr()
    assert "Generating predictions" in captured.out
    assert "Evaluating predictions" in captured.out
    assert f"Run {experiment_name} complete!" in captured.out
    assert f"Predictions: experiments/predictions/{experiment_name}.json" in captured.out

    # Verify the patched calls were made with expected arguments
    assert called.get("generate") is not None
    g = called["generate"]
    assert g["prompt"] == prompt
    assert g["inputs"] == inputs
    assert g["model_name"] == model_under_test
    assert g["experiment_name"] == experiment_name
    assert g["temperature"] == temperature

    assert called.get("evaluate") is not None
    e = called["evaluate"]
    assert e["inputs"] == inputs
    assert e["outputs"] == targets
    assert e["model_responses"] == ["P1", "P2"]
    assert e["model"] == evaluator_model
    assert e["experiment_name"] == experiment_name

    # Metadata JSON should be written with expected fields
    meta_path = tmp_path / "experiments" / "run_metadata" / f"{experiment_name}.json"
    assert meta_path.exists()

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["experiment_name"] == experiment_name
    assert meta["prompt"] == prompt
    assert meta["num_examples"] == len(inputs)
    assert meta["model_under_test"] == model_under_test
    assert meta["evaluator_model"] == evaluator_model
    assert meta["temperature"] == temperature
    assert meta["prediction_path"] == f"experiments/predictions/{experiment_name}.json"
    assert meta["evaluation_path"] == f"experiments/evaluations/{experiment_name}.json"
    # The timestamp should be the deterministic value from FakeDateTime
    assert meta["timestamp"] == "2024-01-01T00:00:00"

def test_run_experiment_multiple_inputs_and_paths(tmp_path, monkeypatch):
    # This test ensures the function can handle another set of inputs and targets
    # and that the paths reflect the new experiment name.
    pkg_base = _setup_temp_package(tmp_path)

    sys.path.insert(0, str(tmp_path))
    run_exp_module = importlib.import_module("pkg.runner.run_experiment")

    captured_calls = {}

    def fake_generate_response(prompt, inputs, model_name, experiment_name, temperature):
        captured_calls["generate"] = {
            "prompt": prompt, "inputs": inputs, "model_name": model_name,
            "experiment_name": experiment_name, "temperature": temperature
        }
        return ["G1", "G2", "G3"]

    def fake_evaluate_model(inputs, outputs, model_responses, model, experiment_name):
        captured_calls["evaluate"] = {
            "inputs": inputs, "outputs": outputs,
            "model_responses": model_responses, "model": model,
            "experiment_name": experiment_name
        }

    class FakeDateTime:
        @classmethod
        def now(cls):
            class _Dt:
                def isoformat(self):
                    return "2024-01-01T00:00:00"  # Use deterministic timestamp here as well
            return _Dt()

    monkeypatch.setattr(run_exp_module, "datetime", FakeDateTime)
    monkeypatch.setattr(run_exp_module.generate, "generate_response", fake_generate_response)
    monkeypatch.setattr(run_exp_module.evaluate, "evaluate_model", fake_evaluate_model)
    monkeypatch.chdir(tmp_path)

    experiment_name = "second_run"
    prompt = "PROMPT-2"
    inputs = ["in-a", "in-b"]
    targets = ["out-a", "out-b"]
    model_under_test = "model-2"
    evaluator_model = "evaluator-2"
    temperature = 0.25

    run_exp_module.run_experiment(
        experiment_name=experiment_name,
        prompt=prompt,
        inputs=inputs,
        targets=targets,
        model_under_test=model_under_test,
        evaluator_model=evaluator_model,
        temperature=temperature,
    )

    # Assertions on calls
    assert "generate" in captured_calls
    assert captured_calls["generate"]["experiment_name"] == experiment_name
    assert captured_calls["generate"]["prompt"] == prompt
    assert captured_calls["generate"]["model_name"] == model_under_test
    assert captured_calls["generate"]["inputs"] == inputs
    assert captured_calls["generate"]["temperature"] == temperature

    assert "evaluate" in captured_calls
    assert captured_calls["evaluate"]["inputs"] == inputs
    assert captured_calls["evaluate"]["outputs"] == targets
    assert captured_calls["evaluate"]["model"] == evaluator_model
    assert captured_calls["evaluate"]["experiment_name"] == experiment_name

    # Metadata file content
    meta_path = tmp_path / "experiments" / "run_metadata" / f"{experiment_name}.json"
    assert meta_path.exists()
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["experiment_name"] == experiment_name
    assert meta["prompt"] == prompt
    assert meta["num_examples"] == len(inputs)
    assert meta["model_under_test"] == model_under_test
    assert meta["evaluator_model"] == evaluator_model
    assert meta["temperature"] == temperature
    assert meta["prediction_path"] == f"experiments/predictions/{experiment_name}.json"
    assert meta["evaluation_path"] == f"experiments/evaluations/{experiment_name}.json"
    assert meta["timestamp"] == "2024-01-01T00:00:00"