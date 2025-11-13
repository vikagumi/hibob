from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_work_ok():
    response = client.get("/work")
    assert response.status_code == 200
    data = response.json()
    assert "result" in data


def test_work_fail():
    response = client.get("/work?fail=true")
    assert response.status_code == 500