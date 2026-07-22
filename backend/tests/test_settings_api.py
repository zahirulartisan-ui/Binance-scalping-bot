from fastapi.testclient import TestClient


def test_settings_api_returns_public_non_secret_settings(client: TestClient) -> None:
    response = client.get("/api/v1/settings")

    assert response.status_code == 200
    payload = response.json()
    assert "binance_demo_api_key" not in payload
    assert "binance_demo_api_secret" not in payload
    assert "database_url" not in payload
    assert payload["execution_enabled"] is False
    assert payload["position_monitoring_enabled"] is True


def test_settings_api_validates_and_persists_runtime_updates(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/settings",
        json={
            "scanner_interval_seconds": 120,
            "risk_per_trade": 0.02,
            "maximum_open_trades": 4,
            "emergency_stop": True,
            "execution_enabled": False,
            "position_monitoring_enabled": False,
            "position_monitoring_interval_seconds": 30,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scanner_interval_seconds"] == 120
    assert payload["risk_per_trade"] == 0.02
    assert payload["maximum_open_trades"] == 4
    assert payload["emergency_stop"] is True
    assert payload["execution_enabled"] is False
    assert payload["position_monitoring_enabled"] is False
    assert payload["position_monitoring_interval_seconds"] == 30


def test_settings_api_rejects_unsafe_execution_update(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/settings",
        json={"emergency_stop": True, "execution_enabled": True},
    )

    assert response.status_code == 422
