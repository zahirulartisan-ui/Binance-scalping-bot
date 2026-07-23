from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

import httpx

from app.services.binance_client import (
    BinanceClientError,
    BinanceInvalidRequestError,
    BinanceRateLimitError,
    BinanceServerError,
)


class BinanceTradingClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        backoff_seconds: float,
        client_factory: Callable[[], httpx.Client] | None = None,
        timestamp_factory: Callable[[], int] | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.client_factory = client_factory or self._default_client
        self.timestamp_factory = timestamp_factory or (lambda: int(time.time() * 1000))

    def _default_client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        payload = dict(params or {})
        if signed:
            payload["timestamp"] = self.timestamp_factory()
            query = urlencode(payload, doseq=True)
            signature = hmac.new(
                self.api_secret.encode("utf-8"),
                query.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            payload["signature"] = signature

        headers = {"X-MBX-APIKEY": self.api_key}
        attempts = self.max_retries + 1
        with self.client_factory() as client:
            for attempt in range(attempts):
                try:
                    response = client.request(method, path, params=payload, headers=headers)
                except httpx.TimeoutException as exc:
                    if attempt >= self.max_retries:
                        raise BinanceClientError("Binance trading request timed out") from exc
                    self._sleep(attempt)
                    continue
                except httpx.HTTPError as exc:
                    if attempt >= self.max_retries:
                        raise BinanceClientError("Binance trading request failed") from exc
                    self._sleep(attempt)
                    continue

                if response.status_code in {400, 401, 403, 404}:
                    raise BinanceInvalidRequestError("Binance rejected the trading request")
                if response.status_code in {418, 429}:
                    if attempt >= self.max_retries:
                        raise BinanceRateLimitError("Binance trading rate limit reached")
                    self._sleep(attempt)
                    continue
                if 500 <= response.status_code < 600:
                    if attempt >= self.max_retries:
                        raise BinanceServerError("Binance trading server error")
                    self._sleep(attempt)
                    continue
                if response.status_code >= 400:
                    raise BinanceClientError("Binance trading HTTP error")
                return response.json()
        raise BinanceClientError("Binance trading request failed")

    def _sleep(self, attempt: int) -> None:
        delay = self.backoff_seconds * (2**attempt)
        if delay > 0:
            time.sleep(delay)

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        client_order_id: str,
        price: str | None = None,
        time_in_force: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
            "newClientOrderId": client_order_id,
            "newOrderRespType": "FULL",
        }
        if price is not None:
            params["price"] = price
        if time_in_force is not None:
            params["timeInForce"] = time_in_force
        data = self._request("POST", "/api/v3/order", params=params, signed=True)
        if not isinstance(data, dict):
            raise BinanceClientError("Malformed create order response")
        return data

    def get_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if client_order_id is not None:
            params["origClientOrderId"] = client_order_id
        data = self._request("GET", "/api/v3/order", params=params, signed=True)
        if not isinstance(data, dict):
            raise BinanceClientError("Malformed get order response")
        return data

    def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if symbol is not None:
            params["symbol"] = symbol
        data = self._request("GET", "/api/v3/openOrders", params=params, signed=True)
        if not isinstance(data, list):
            raise BinanceClientError("Malformed open orders response")
        return [row for row in data if isinstance(row, dict)]

    def get_account(self) -> dict[str, Any]:
        data = self._request(
            "GET",
            "/api/v3/account",
            params={"omitZeroBalances": "true"},
            signed=True,
        )
        if not isinstance(data, dict):
            raise BinanceClientError("Malformed account response")
        return data

    def get_my_trades(
        self,
        symbol: str,
        order_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if order_id is not None:
            params["orderId"] = order_id
        data = self._request("GET", "/api/v3/myTrades", params=params, signed=True)
        if not isinstance(data, list):
            raise BinanceClientError("Malformed trades response")
        return [row for row in data if isinstance(row, dict)]
