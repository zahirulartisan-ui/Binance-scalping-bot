from fastapi.testclient import TestClient


def test_health_reports_disabled_execution(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["application"]["status"] == "ok"
    assert payload["database"]["status"] == "ok"
    assert payload["execution"]["status"] == "disabled"
