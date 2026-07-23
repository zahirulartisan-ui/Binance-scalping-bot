from __future__ import annotations

import httpx
import pytest

from app.services.binance_client import (
    BinanceInvalidRequestError,
    BinanceMarketDataClient,
    BinanceRateLimitError,
)


def client_with_statuses(statuses: list[int]) -> BinanceMarketDataClient:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        status = statuses[min(calls["count"], len(statuses) - 1)]
        calls["count"] += 1
        return httpx.Response(status, json={"ok": True})

    transport = httpx.MockTransport(handler)
    return BinanceMarketDataClient(
        "https://example.test",
        timeout_seconds=1,
        max_retries=2,
        backoff_seconds=0,
        client_factory=lambda: httpx.Client(transport=transport, base_url="https://example.test"),
    )


def test_retry_then_success() -> None:
    client = client_with_statuses([500, 200])

    assert client.exchange_info() == {"ok": True}


def test_rate_limit_error_after_bounded_retries() -> None:
    client = client_with_statuses([429, 429, 429])

    with pytest.raises(BinanceRateLimitError):
        client.exchange_info()


def test_invalid_request_is_not_retried_indefinitely() -> None:
    client = client_with_statuses([400])

    with pytest.raises(BinanceInvalidRequestError):
        client.exchange_info()


def test_klines_rejects_unsupported_interval() -> None:
    client = client_with_statuses([200])

    with pytest.raises(BinanceInvalidRequestError):
        client.klines("BTCUSDT", "30m")
