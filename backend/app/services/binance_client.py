from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class BinanceClientError(Exception):
    pass


class BinanceInvalidRequestError(BinanceClientError):
    pass


class BinanceRateLimitError(BinanceClientError):
    pass


class BinanceServerError(BinanceClientError):
    pass


class BinanceMarketDataClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        backoff_seconds: float,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.client_factory = client_factory or self._default_client

    def _default_client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds)

    def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        attempts = self.max_retries + 1
        with self.client_factory() as client:
            for attempt in range(attempts):
                try:
                    response = client.get(path, params=params)
                except httpx.TimeoutException as exc:
                    if attempt >= self.max_retries:
                        raise BinanceClientError("Binance request timed out") from exc
                    self._sleep(attempt)
                    continue
                except httpx.HTTPError as exc:
                    if attempt >= self.max_retries:
                        raise BinanceClientError("Binance request failed") from exc
                    self._sleep(attempt)
                    continue

                if response.status_code in {400, 401, 403, 404}:
                    raise BinanceInvalidRequestError("Binance rejected the request")
                if response.status_code in {418, 429}:
                    if attempt >= self.max_retries:
                        raise BinanceRateLimitError("Binance rate limit reached")
                    self._sleep(attempt)
                    continue
                if 500 <= response.status_code < 600:
                    if attempt >= self.max_retries:
                        raise BinanceServerError("Binance server error")
                    self._sleep(attempt)
                    continue
                if response.status_code >= 400:
                    raise BinanceClientError("Binance HTTP error")
                return response.json()
        raise BinanceClientError("Binance request failed")

    def _sleep(self, attempt: int) -> None:
        delay = self.backoff_seconds * (2**attempt)
        if delay > 0:
            time.sleep(delay)

    def exchange_info(self) -> dict[str, Any]:
        data = self._request("/api/v3/exchangeInfo")
        if not isinstance(data, dict):
            raise BinanceClientError("Malformed exchangeInfo response")
        return data

    def book_ticker(self, symbol: str) -> dict[str, Any]:
        data = self._request("/api/v3/ticker/bookTicker", {"symbol": symbol})
        if not isinstance(data, dict):
            raise BinanceClientError("Malformed book ticker response")
        return data

    def recent_price(self, symbol: str) -> dict[str, Any]:
        data = self._request("/api/v3/ticker/price", {"symbol": symbol})
        if not isinstance(data, dict):
            raise BinanceClientError("Malformed price response")
        return data

    def klines(self, symbol: str, interval: str, limit: int = 2) -> list[Any]:
        if interval not in {"1m", "5m"}:
            raise BinanceInvalidRequestError("Unsupported kline interval")
        data = self._request(
            "/api/v3/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        if not isinstance(data, list):
            raise BinanceClientError("Malformed klines response")
        return data
