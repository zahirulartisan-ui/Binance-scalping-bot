from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import CandleTimeframe
from app.models.market_data import ExchangeSymbol, MarketSnapshot, OhlcvCandle


def seed(db: Session, symbol: str) -> None:
    db.add(
        ExchangeSymbol(
            symbol=symbol,
            base_asset=symbol.replace("USDT", ""),
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
    start = datetime.now(UTC) - timedelta(minutes=222)
    for index in range(220):
        price = Decimal("100") + Decimal(index) / Decimal("10")
        open_time = start + timedelta(minutes=index)
        db.add(
            OhlcvCandle(
                symbol=symbol,
                timeframe=CandleTimeframe.ONE_MINUTE,
                open_time=open_time,
                close_time=open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
                open_price=price,
                high_price=price * Decimal("1.001"),
                low_price=price * Decimal("0.999"),
                close_price=price,
                volume=Decimal("10"),
                quote_volume=price * Decimal("10"),
                trade_count=10,
            )
        )
    db.add(
        MarketSnapshot(
            symbol=symbol,
            last_price=Decimal("120"),
            bid_price=Decimal("119.99"),
            ask_price=Decimal("120.01"),
            bid_quantity=Decimal("1"),
            ask_quantity=Decimal("1"),
            spread_bps=Decimal("2"),
            snapshot_at=datetime.now(UTC),
        )
    )


def test_regime_api_validation_and_output(client: TestClient, db_session: Session) -> None:
    seed(db_session, "BTCUSDT")
    seed(db_session, "ETHUSDT")
    db_session.commit()

    response = client.get("/api/v1/regime/ETHUSDT")
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "ETHUSDT"
    assert "indicator_snapshot" in payload
    assert payload["entry_permission"] in {"ALLOW_LONG", "BLOCK_NEW_ENTRIES"}
    assert client.get("/api/v1/regime/BAD").status_code == 422
    assert client.get("/api/v1/regime/DOGEUSDT").status_code == 404
