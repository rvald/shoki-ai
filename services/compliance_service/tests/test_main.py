from fastapi.testclient import TestClient
from services.compliance_service.main import app

client = TestClient(app)

def test_dummy_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert 1 == 1