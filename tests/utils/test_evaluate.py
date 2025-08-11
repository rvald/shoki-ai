import json
import importlib

# Helper: a dummy OpenAI client that yields pre-supplied JSON strings per call
class DummyResponse:
    def __init__(self, content):
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": content})})()]

class DummyOpenAI:
    # Contents to return for each call to create(...)
    _contents = []
    # Capture last provided API key for asserting it was passed through
    last_api_key = None

    def __init__(self, api_key=None):
        DummyOpenAI.last_api_key = api_key
        # Build a lightweight client with a chat.completions.create(...) method
        self.chat = type("Chat", (), {})()
        # completions has a create method that pops the next JSON string
        self.chat.completions = type("Completions", (), {})()

        def _create(model=None, messages=None):
            content = DummyOpenAI._contents.pop(0)
            return DummyResponse(content)

        # Bind the create function
        self.chat.completions.create = _create

# Tests
def test_evaluate_model_success_writes_results(tmp_path, monkeypatch):
    # Reasoning:
    # - Provide two inputs/responses and mock the API to return valid JSON for both.
    # - Ensure a file is written to experiments/evaluations/{experiment_name}.json
    # - Ensure the contents written match the JSON parsed from the mocked responses.
    mod = importlib.import_module("utils.evaluate")  # adjust if your module has a different name

    # Prepare two valid JSON results as strings (one per input)
    json1 = json.dumps({"input": "Hello", "expected_output": "Hi",
                        "model_response": "Hello there", "score": 5,
                        "explanation": "matches expected"})
    json2 = json.dumps({"input": "What is 2+2?", "expected_output": "4",
                        "model_response": "4", "score": 5,
                        "explanation": "correct"})

    DummyOpenAI._contents = [json1, json2]

    # Patch: replace OpenAI with our dummy and set a real API key
    monkeypatch.setattr(mod, "OpenAI", DummyOpenAI)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    # Run in a clean tmp directory
    monkeypatch.chdir(tmp_path)

    inputs = ["Hello", "What is 2+2?"]
    outputs = ["Hi", "4"]
    model_responses = ["Hello there", "4"]

    # Call the function
    mod.evaluate_model(inputs, outputs, model_responses, model="gpt-4", experiment_name="test_exp")

    # Assertions:
    # - The API key passed to OpenAI.__init__ should be the env var value
    assert DummyOpenAI.last_api_key == "test-key"

    # - The results file should exist and contain the parsed JSON results
    expected_results = [json.loads(json1), json.loads(json2)]
    output_path = tmp_path / "experiments" / "evaluations" / "test_exp.json"
    assert output_path.exists()

    with open(output_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    assert results == expected_results


def test_evaluate_model_handles_invalid_json(tmp_path, monkeypatch, capsys):
    # Reasoning:
    # - The second response yields invalid JSON; the function should skip it
    # - Only valid JSON responses should be included in the written file
    mod = importlib.import_module("utils.evaluate")  # adjust if your module has a different name

    # First valid JSON, second invalid
    json_valid = json.dumps({"input": "A", "expected_output": "A", "model_response": "A", "score": 4, "explanation": "ok"})
    invalid_json = "Not JSON"

    DummyOpenAI._contents = [json_valid, invalid_json]

    monkeypatch.setattr(mod, "OpenAI", DummyOpenAI)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-2")
    monkeypatch.chdir(tmp_path)

    inputs = ["A", "B"]
    outputs = ["A", "B"]
    model_responses = ["A", "B"]

    mod.evaluate_model(inputs, outputs, model_responses, model="gpt-4", experiment_name="invalid_json_exp")

    # The second response is invalid; only the first result should be stored
    output_path = tmp_path / "experiments" / "evaluations" / "invalid_json_exp.json"
    assert output_path.exists()

    with open(output_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    expected_results = [json.loads(json_valid)]
    assert results == expected_results

    # Also verify that a JSON parsing error did occur (printed to stdout)
    captured = capsys.readouterr()
    # We don't require a particular message text, just that something about "Failed to parse JSON" is printed
    assert "Failed to parse JSON" in captured.out


def test_default_experiment_name_and_directory_creation(tmp_path, monkeypatch):
    # Reasoning:
    # - When experiment_name is not provided, default to "default_experiment"
    # - Ensure the directory is created and a single result is written
    mod = importlib.import_module("utils.evaluate")  # adjust if your module has a different name

    json_one = json.dumps({"input": "X", "expected_output": "X", "model_response": "X", "score": 5, "explanation": "ok"})
    DummyOpenAI._contents = [json_one]

    monkeypatch.setattr(mod, "OpenAI", DummyOpenAI)
    monkeypatch.setenv("OPENAI_API_KEY", "def_key")
    monkeypatch.chdir(tmp_path)

    inputs = ["X"]
    outputs = ["X"]
    model_responses = ["X"]

    mod.evaluate_model(inputs, outputs, model_responses, model="gpt-4")

    # Default experiment name should be used
    output_path = tmp_path / "experiments" / "evaluations" / "default_experiment.json"
    assert output_path.exists()

    with open(output_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    expected_results = [json.loads(json_one)]
    assert results == expected_results