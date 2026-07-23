from fastapi.testclient import TestClient


def test_health_reports_disabled_execution(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["application"]["status"] == "ok"
    assert payload["database"]["status"] == "ok"
    assert payload["environment"]["status"] == "test"
    assert payload["demo_trading"]["status"] == "disabled"
    assert payload["execution"]["status"] == "disabled"
    assert payload["emergency_stop"]["status"] == "inactive"
    assert payload["migrations"]["status"] == "ready"

    # Verify new USD-M Futures response contract (12. Secrets are absent from health)
    assert payload["exchange_scope"] == "Binance"
    assert payload["product_type"] == "USD-M Futures"
    assert payload["endpoint_allowlist_status"] in {"verified", "invalid"}
    assert "api_key" not in payload
    assert "api_secret" not in payload
    assert "private_key" not in payload
    assert "secret" not in payload
    assert "password" not in payload
