from fastapi.testclient import TestClient


def test_health_reports_disabled_execution(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["application"]["status"] == "ok"
    assert payload["database"]["status"] == "ok"
    assert payload["environment"]["status"] == "test"
    assert payload["demo_trading"]["status"] == "enabled"
    assert payload["execution"]["status"] == "disabled"
    assert payload["emergency_stop"]["status"] == "inactive"
    assert payload["migrations"]["status"] == "ready"
