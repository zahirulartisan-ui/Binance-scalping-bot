from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from app.services.binance_trading_client import BinanceTradingClient


def test_create_order_signs_payload_and_sets_api_key_header() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["query"] = parse_qs(urlparse(str(request.url)).query)
        captured["api_key"] = request.headers.get("X-MBX-APIKEY")
        return httpx.Response(200, json={"orderId": 1, "clientOrderId": "abc", "status": "NEW"})

    transport = httpx.MockTransport(handler)
    client = BinanceTradingClient(
        api_key="test-key",
        api_secret="test-secret",
        base_url="https://example.test",
        timeout_seconds=1,
        max_retries=0,
        backoff_seconds=0,
        client_factory=lambda: httpx.Client(transport=transport, base_url="https://example.test"),
        timestamp_factory=lambda: 1234567890,
    )

    payload = client.create_order(
        symbol="BTCUSDT",
        side="buy",
        order_type="limit",
        quantity="1.25",
        client_order_id="cid-1",
        price="100.5",
        time_in_force="GTC",
    )

    assert payload["status"] == "NEW"
    assert captured["api_key"] == "test-key"
    query = captured["query"]
    assert query["symbol"] == ["BTCUSDT"]
    assert query["side"] == ["BUY"]
    assert query["type"] == ["LIMIT"]
    assert query["timestamp"] == ["1234567890"]
    assert "signature" in query


def test_get_my_trades_returns_trade_rows() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=[{"id": 99, "price": "100", "qty": "1", "commission": "0.1"}],
        )
    )
    client = BinanceTradingClient(
        api_key="test-key",
        api_secret="test-secret",
        base_url="https://example.test",
        timeout_seconds=1,
        max_retries=0,
        backoff_seconds=0,
        client_factory=lambda: httpx.Client(transport=transport, base_url="https://example.test"),
    )

    rows = client.get_my_trades("BTCUSDT", order_id="123")

    assert rows == [{"id": 99, "price": "100", "qty": "1", "commission": "0.1"}]
