import json
import importlib
import pytest

# Helper dummy classes to simulate the OpenAI client and responses
class _Usage:
    def __init__(self, prompt_tokens, completion_tokens, total_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens

class _DummyChoiceMsg:
    def __init__(self, content):
        self.content = content

class _DummyChoice:
    def __init__(self, content):
        self.message = _DummyChoiceMsg(content)

class _DummyResponse:
    def __init__(self, content, usage=None):
        self.choices = [_DummyChoice(content)]
        if usage is not None:
            self.usage = usage

class _DummyOpenAI:
    last_api_key = None
    # These will be supplied per test
    _predictions = []
    _usages = None  # None means "no usage attribute"; a list means per-call usage

    def __init__(self, base_url=None, api_key=None):
        _DummyOpenAI.last_api_key = api_key
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()

        def _create(model=None, messages=None, temperature=None, **kwargs):
            content = _DummyOpenAI._predictions.pop(0)
            usage = None
            if _DummyOpenAI._usages is not None and _DummyOpenAI._usages:
                usage = _DummyOpenAI._usages.pop(0)
            return _DummyResponse(content, usage)

        self.chat.completions.create = _create

# They will patch the module that defines generate_response
MODULE_NAME = "utils.generate"  # Replace with your actual module name

# Test 1: Successful generation returns predictions and writes file with tokens
def test_generate_response_success_writes_and_returns(tmp_path, monkeypatch):
    mod = importlib.import_module(MODULE_NAME)

    # Prepare two predictions and corresponding usages
    _DummyOpenAI._predictions = ["First prediction", "Second prediction"]
    _DummyOpenAI._usages = [
        _Usage(1, 2, 3),
        _Usage(4, 5, 6),
    ]

    monkeypatch.setattr(mod, "OpenAI", _DummyOpenAI)
    # Ensure deterministic latency values: start, end for each of two iterations
    class FakeTime:
        def __init__(self, values):
            self._vals = iter(values)
        def time(self):
            return next(self._vals)
    # Two iterations: (start1, end1, start2, end2)
    monkeypatch.setattr(mod, "time", FakeTime([0.0, 0.2, 1.0, 1.3]))
    # Use a temporary CWD to isolate filesystem
    monkeypatch.chdir(tmp_path)

    prompt = "PROMPT"
    inputs = ["Question 1", "Question 2"]
    outputs = ["Answer 1", "Answer 2"]  # not used by mock, but kept for signature
    model_name = "test-model"

    results = mod.generate_response(prompt, inputs, model_name, experiment_name="test_gen", temperature=0.5)

    # API key should have been passed through as "dummy" (as in code)
    assert _DummyOpenAI.last_api_key == "dummy"
    # Predictions should match mocked content
    assert results == ["First prediction", "Second prediction"]

    # File should exist with the expected path and content
    expected_path = tmp_path / "experiments" / "predictions" / "test_gen.json"
    assert expected_path.exists()

    with open(expected_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list) and len(data) == 2
    assert data[0]["input"] == inputs[0]
    assert data[0]["prediction"] == "First prediction"
    assert pytest.approx(data[0]["latency_seconds"], rel=1e-6) == 0.2
    assert data[0]["prompt_tokens"] == 1
    assert data[0]["completion_tokens"] == 2
    assert data[0]["total_tokens"] == 3

    assert data[1]["input"] == inputs[1]
    assert data[1]["prediction"] == "Second prediction"
    assert pytest.approx(data[1]["latency_seconds"], rel=1e-6) == 0.3
    assert data[1]["prompt_tokens"] == 4
    assert data[1]["completion_tokens"] == 5
    assert data[1]["total_tokens"] == 6

# Test 2: When usage is missing, tokens fields should be None
def test_generate_response_missing_usage(tmp_path, monkeypatch, capsys):
    mod = importlib.import_module(MODULE_NAME)

    _DummyOpenAI._predictions = ["Only one response"]
    _DummyOpenAI._usages = None  # No usage attribute

    monkeypatch.setattr(mod, "OpenAI", _DummyOpenAI)
    class FakeTime:
        def __init__(self, values):
            self._vals = iter(values)
        def time(self):
            return next(self._vals)
    monkeypatch.setattr(mod, "time", FakeTime([0.0, 0.15]))
    monkeypatch.chdir(tmp_path)

    prompt = "PROMPT"
    inputs = ["Sample input"]
    model_name = "model-x"

    preds = mod.generate_response(prompt, inputs, model_name, experiment_name="no_usage_exp", temperature=0.4)

    assert preds == ["Only one response"]
    assert _DummyOpenAI.last_api_key == "dummy"

    expected_path = tmp_path / "experiments" / "predictions" / "no_usage_exp.json"
    assert expected_path.exists()

    with open(expected_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["input"] == inputs[0]
    assert data[0]["prediction"] == "Only one response"
    assert data[0]["latency_seconds"] >= 0.0  # sanity
    # Tokens should be None when usage is not provided
    assert data[0]["prompt_tokens"] is None
    assert data[0]["completion_tokens"] is None
    assert data[0]["total_tokens"] is None

    captured = capsys.readouterr()
    assert "Predictions saved to" in captured.out

# Test 3: Default experiment name (no explicit experiment_name)
def test_default_experiment_name_writes(tmp_path, monkeypatch):
    mod = importlib.import_module(MODULE_NAME)

    _DummyOpenAI._predictions = ["P1"]
    _DummyOpenAI._usages = [_Usage(2, 3, 5)]
    monkeypatch.setattr(mod, "OpenAI", _DummyOpenAI)

    class FakeTime:
        def __init__(self, values):
            self._vals = iter(values)
        def time(self):
            return next(self._vals)
    monkeypatch.setattr(mod, "time", FakeTime([0.0, 0.25]))

    monkeypatch.chdir(tmp_path)

    prompt = "PROMPT"
    inputs = ["U1"]
    model_name = "model-Y"

    preds = mod.generate_response(prompt, inputs, model_name)  # no experiment_name provided

    assert preds == ["P1"]

    # Default path should be created
    expected_path = tmp_path / "experiments" / "predictions" / "default_generation.json"
    assert expected_path.exists()

    with open(expected_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["input"] == "U1"
    assert data[0]["prediction"] == "P1"