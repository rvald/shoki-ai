from fastapi.testclient import TestClient
from services.compliance_service.main import app

client = TestClient(app)

def test_audit_request(monkeypatch):
    # Fake implementation to avoid real work
    def fake_generate_audit(transcript, model_name="deepseek-r1:7b"):
        fake_generate_audit.called_with = {
            "transcript": transcript,
            "model_name": model_name,
        }
        return "mocked-audit"

    # Patch the dependency used by the endpoint
    monkeypatch.setattr("services.compliance_service.src.service.generate_audit", fake_generate_audit)

    resp = client.post(
        "/api/v1/audit",
        json={"transcript": "This is a test transcript for compliance audit."}
    )

    assert resp.status_code == 200

def test_audit_missing_field():
    resp = client.post("/api/v1/audit", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data

def test_audit_null_transcript():
    resp = client.post("/api/v1/audit", json={"transcript": None})
    assert resp.status_code == 422

def test_audit_wrong_type():
    resp = client.post("/api/v1/audit", json={"transcript": 123})
    assert resp.status_code == 422

def test_audit_empty_string():
    resp = client.post("/api/v1/audit", json={"transcript": ""})
    assert resp.status_code == 422

def test_audit_extra_fields_ignored(monkeypatch):
    def fake_generate_audit(transcript, model_name="deepseek-r1:7b"):
        return "mocked-audit"

    monkeypatch.setattr("services.compliance_service.src.service.generate_audit", fake_generate_audit)

    resp = client.post("/api/v1/audit", json={"transcript": "ok", "foo": "bar"})

    assert resp.status_code == 200

def test_audit_method_not_allowed():
    resp = client.get("/api/v1/audit")
    assert resp.status_code == 405