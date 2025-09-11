from fastapi.testclient import TestClient
from services.compliance_service.main import app

client = TestClient(app)

def test_dummy_ok():
    assert 1 == 1