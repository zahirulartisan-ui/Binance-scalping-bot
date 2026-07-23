from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import CandleTimeframe, MarketDataCycleStatus
from app.models.market_data import ExchangeSymbol, MarketDataCycle, MarketSnapshot, OhlcvCandle


def seed_symbol(db_session: Session) -> None:
    db_session.add(
        ExchangeSymbol(
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            trading_status="TRADING",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.00001"),
            minimum_quantity=Decimal("0.00001"),
            minimum_notional=Decimal("5"),
            price_precision=8,
            quantity_precision=8,
        )
    )


def test_market_data_empty_states(client: TestClient) -> None:
    assert client.get("/api/v1/market-data/symbols").json() == []
    assert client.get("/api/v1/market-data/candles?symbol=BTCUSDT&timeframe=1m").json() == []
    assert client.get("/api/v1/market-data/snapshot?symbol=BTCUSDT").json() is None


def test_market_data_api_returns_records(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC) - timedelta(minutes=5)
    seed_symbol(db_session)
    db_session.add(
        OhlcvCandle(
            symbol="BTCUSDT",
            timeframe=CandleTimeframe.ONE_MINUTE,
            open_time=now,
            close_time=now + timedelta(minutes=1) - timedelta(milliseconds=1),
            open_price=Decimal("10"),
            high_price=Decimal("12"),
            low_price=Decimal("9"),
            close_price=Decimal("11"),
            volume=Decimal("1"),
            quote_volume=Decimal("11"),
            trade_count=1,
        )
    )
    db_session.add(
        MarketSnapshot(
            symbol="BTCUSDT",
            last_price=Decimal("11"),
            bid_price=Decimal("10"),
            ask_price=Decimal("12"),
            bid_quantity=Decimal("1"),
            ask_quantity=Decimal("1"),
            spread_bps=Decimal("1818.18"),
            snapshot_at=now,
        )
    )
    db_session.add(MarketDataCycle(status=MarketDataCycleStatus.COMPLETED, rejection_reasons={}))
    db_session.commit()

    assert client.get("/api/v1/market-data/symbols").json()[0]["symbol"] == "BTCUSDT"
    candles = client.get("/api/v1/market-data/candles?symbol=BTCUSDT&timeframe=1m").json()
    assert candles[0]["symbol"] == "BTCUSDT"
    assert client.get("/api/v1/market-data/snapshot?symbol=BTCUSDT").json()["symbol"] == "BTCUSDT"
    assert client.get("/api/v1/market-data/status").json()["latest_cycle_status"] == "completed"


def test_market_data_api_parameter_validation(client: TestClient) -> None:
    assert client.get("/api/v1/market-data/candles?symbol=BAD&timeframe=1m").status_code == 422
    assert client.get("/api/v1/market-data/candles?symbol=BTCUSDT&timeframe=30m").status_code == 422
    assert client.get("/api/v1/market-data/symbols?limit=9999").status_code == 422


def test_candle_response_parsing_string_numeric_values() -> None:
    from app.schemas.market_data import CandleResponse

    raw_data = {
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "open_time": "2026-07-23T18:48:29.852Z",
        "close_time": "2026-07-23T18:49:29.852Z",
        "open_price": "10123.45",
        "high_price": "10150.00",
        "low_price": "10100.12",
        "close_price": "10140.50",
        "volume": "1.2345",
        "quote_volume": "12500.0",
        "trade_count": 42
    }

    response = CandleResponse.model_validate(raw_data)
    assert isinstance(response.open_price, float)
    assert response.open_price == 10123.45
    assert response.high_price == 10150.0
    assert response.low_price == 10100.12
    assert response.close_price == 10140.5
    assert response.volume == 1.2345
    assert response.quote_volume == 12500.0
