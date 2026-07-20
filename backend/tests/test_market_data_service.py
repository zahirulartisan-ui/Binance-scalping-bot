from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import CandleTimeframe
from app.models.market_data import ExchangeSymbol, MarketSnapshot
from app.services.market_data_service import (
    MarketDataValidationError,
    ensure_symbol,
    parse_closed_candle,
    parse_snapshot,
    parse_symbol,
    persist_candle,
    persist_snapshot,
    refresh_symbols,
    to_decimal,
)


def symbol_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "symbol": "BTCUSDT",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "status": "TRADING",
        "isSpotTradingAllowed": True,
        "permissions": ["SPOT"],
        "quotePrecision": 8,
        "baseAssetPrecision": 8,
        "filters": [
            {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
            {"filterType": "LOT_SIZE", "stepSize": "0.00001000", "minQty": "0.00001000"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "5.00000000"},
        ],
    }
    payload.update(overrides)
    return payload


def closed_kline(open_time: datetime) -> list[object]:
    open_ms = int(open_time.timestamp() * 1000)
    close_time = open_time + timedelta(minutes=1) - timedelta(milliseconds=1)
    close_ms = int(close_time.timestamp() * 1000)
    return [open_ms, "10", "12", "9", "11", "2", close_ms, "22", 4, "1", "11", "0"]


def test_symbol_filtering_and_decimal_conversion() -> None:
    parsed = parse_symbol(symbol_payload())

    assert parsed.symbol == "BTCUSDT"
    assert parsed.tick_size == Decimal("0.01000000")
    assert to_decimal("1.23", "price") == Decimal("1.23")

    with pytest.raises(MarketDataValidationError):
        parse_symbol(symbol_payload(symbol="BTCUPUSDT"))


def test_refresh_symbols_is_idempotent(db_session: Session) -> None:
    count = refresh_symbols(db_session, {"symbols": [symbol_payload()]})
    count_again = refresh_symbols(db_session, {"symbols": [symbol_payload()]})

    assert count == 1
    assert count_again == 1
    assert len(db_session.query(ExchangeSymbol).all()) == 1


def test_closed_candle_enforcement_and_idempotency(db_session: Session) -> None:
    open_time = datetime.now(UTC) - timedelta(minutes=5)
    candle = parse_closed_candle(closed_kline(open_time), "BTCUSDT", CandleTimeframe.ONE_MINUTE)

    assert persist_candle(db_session, candle) is True
    assert persist_candle(db_session, candle) is False

    with pytest.raises(MarketDataValidationError):
        parse_closed_candle(closed_kline(datetime.now(UTC)), "BTCUSDT", CandleTimeframe.ONE_MINUTE)


def test_out_of_order_candle_rejection(db_session: Session) -> None:
    first = parse_closed_candle(
        closed_kline(datetime.now(UTC) - timedelta(minutes=5)),
        "BTCUSDT",
        CandleTimeframe.ONE_MINUTE,
    )
    older = parse_closed_candle(
        closed_kline(datetime.now(UTC) - timedelta(minutes=10)),
        "BTCUSDT",
        CandleTimeframe.ONE_MINUTE,
    )

    persist_candle(db_session, first)
    with pytest.raises(MarketDataValidationError):
        persist_candle(db_session, older)


def test_snapshot_validation_spread_and_staleness(db_session: Session) -> None:
    snapshot = parse_snapshot(
        "BTCUSDT",
        {"price": "101"},
        {"bidPrice": "100", "askPrice": "102", "bidQty": "1", "askQty": "2"},
    )

    assert snapshot.spread_bps == Decimal("198.0198019801980198019801980")
    assert persist_snapshot(db_session, snapshot) is True
    assert persist_snapshot(db_session, snapshot) is False

    with pytest.raises(MarketDataValidationError):
        parse_snapshot(
            "BTCUSDT",
            {"price": "101"},
            {"bidPrice": "103", "askPrice": "102", "bidQty": "1", "askQty": "2"},
        )
    with pytest.raises(MarketDataValidationError):
        parse_snapshot(
            "BTCUSDT",
            {"price": "101"},
            {"bidPrice": "100", "askPrice": "102", "bidQty": "1", "askQty": "2"},
            snapshot_at=datetime.now(UTC) - timedelta(minutes=2),
        )


def test_database_constraints(db_session: Session) -> None:
    db_session.add(
        MarketSnapshot(
            symbol="BTCUSDT",
            last_price=Decimal("1"),
            bid_price=Decimal("2"),
            ask_price=Decimal("1"),
            bid_quantity=Decimal("1"),
            ask_quantity=Decimal("1"),
            spread_bps=Decimal("0"),
            snapshot_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_ensure_symbol_rejects_missing_symbol(db_session: Session) -> None:
    with pytest.raises(MarketDataValidationError):
        ensure_symbol(db_session, "BTCUSDT")
