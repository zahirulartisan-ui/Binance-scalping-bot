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

    # Verify new USD-M Futures response contract
    assert payload["exchange_scope"]["status"] == "binance"
    assert payload["product_type"]["status"] == "usd_m_futures"
    assert payload["trading_environment"]["status"] == "futures_demo_only"

    # Endpoints allowlist and safety
    assert payload["endpoints"]["trading_base_url"] == "https://demo-fapi.binance.com"
    assert payload["endpoints"]["trading_endpoint_allowlisted"] is True
    assert "demo-fapi.binance.com" in payload["endpoints"]["allowlisted_hosts"]

    # Safety
    assert payload["safety"]["enabled"] is False
    assert payload["safety"]["ready"] is False
    assert payload["safety"]["emergency_stop_active"] is False

    # Secrets are absent from health
    assert "api_key" not in payload
    assert "api_secret" not in payload
    assert "private_key" not in payload
    assert "secret" not in payload
    assert "password" not in payload
