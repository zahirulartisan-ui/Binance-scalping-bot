from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.models.enums import CandleTimeframe, SignalStatus
from app.models.market_data import ExchangeSymbol, MarketSnapshot, OhlcvCandle
from app.models.trading import Signal


def strategy_settings(**overrides: object) -> Settings:
    values: dict[str, Any] = {
        "app_env": "test",
        "database_url": "sqlite+pysqlite:///:memory:",
        "regime_minimum_candles": 60,
        "regime_trend_strength_threshold": 1,
        "regime_atr_percent_max": 10,
        "strategy_minimum_candle_history": 80,
        "strategy_minimum_impulse_percent": 0.2,
        "strategy_maximum_pullback_percent": 4,
        "strategy_maximum_stop_percent": 5,
        "strategy_maximum_price_distance_after_zone_percent": 2,
        "strategy_minimum_rejection_body_ratio": 0.1,
        "strategy_minimum_rejection_wick_ratio": 0.02,
        "strategy_pullback_volume_contraction_threshold": 1.5,
    }
    values.update(overrides)
    return Settings(**values)


def seed_symbol(db: Session, symbol: str) -> None:
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


def candle(
    symbol: str,
    timeframe: CandleTimeframe,
    open_time: datetime,
    price: Decimal,
    volume: Decimal = Decimal("10"),
    close: Decimal | None = None,
    low: Decimal | None = None,
    high: Decimal | None = None,
) -> OhlcvCandle:
    seconds = 60 if timeframe is CandleTimeframe.ONE_MINUTE else 300
    if timeframe is CandleTimeframe.FIFTEEN_MINUTES:
        seconds = 900
    close_price = close or price
    return OhlcvCandle(
        symbol=symbol,
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timedelta(seconds=seconds) - timedelta(milliseconds=1),
        open_price=price,
        high_price=high or max(price, close_price) * Decimal("1.001"),
        low_price=low or min(price, close_price) * Decimal("0.999"),
        close_price=close_price,
        volume=volume,
        quote_volume=volume * close_price,
        trade_count=10,
    )


def prices_for_ready_setup() -> list[Decimal]:
    prices = [Decimal("100") + Decimal(i) * Decimal("0.03") for i in range(190)]
    prices.extend(
        [
            Decimal("106.00"),
            Decimal("106.20"),
            Decimal("106.40"),
            Decimal("106.70"),
            Decimal("107.00"),
            Decimal("106.90"),
            Decimal("106.75"),
            Decimal("106.55"),
            Decimal("106.35"),
            Decimal("106.20"),
            Decimal("106.05"),
            Decimal("106.10"),
            Decimal("106.25"),
            Decimal("106.45"),
            Decimal("106.70"),
            Decimal("107.30"),
        ]
    )
    return prices


def seed_candles(
    db: Session,
    symbol: str,
    timeframe: CandleTimeframe,
    prices: list[Decimal],
    volume: Decimal = Decimal("10"),
) -> None:
    seconds = 60 if timeframe is CandleTimeframe.ONE_MINUTE else 300
    if timeframe is CandleTimeframe.FIFTEEN_MINUTES:
        seconds = 900
    start = datetime.now(UTC) - timedelta(seconds=seconds * len(prices))
    for index, price in enumerate(prices):
        item_volume = Decimal("18") if index == len(prices) - 1 else volume
        open_time = start + timedelta(seconds=seconds * index)
        low = price * Decimal("0.997")
        if index == len(prices) - 2:
            low = price * Decimal("0.995")
        if index == len(prices) - 1 and symbol != "BTCUSDT":
            db.add(
                candle(
                    symbol,
                    timeframe,
                    open_time,
                    price - Decimal("0.35"),
                    item_volume,
                    close=price,
                    low=price - Decimal("0.42"),
                    high=price + Decimal("2.20"),
                )
            )
        else:
            db.add(candle(symbol, timeframe, open_time, price, item_volume, low=low))


def seed_market(db: Session, symbol: str = "ETHUSDT") -> None:
    seed_symbol(db, "BTCUSDT")
    seed_symbol(db, symbol)
    btc_prices = [Decimal("100") + Decimal(i) * Decimal("0.12") for i in range(220)]
    symbol_prices = prices_for_ready_setup()
    for tf in [CandleTimeframe.ONE_MINUTE, CandleTimeframe.FIVE_MINUTES]:
        seed_candles(db, "BTCUSDT", tf, btc_prices)
        seed_candles(db, symbol, tf, symbol_prices)
    seed_candles(db, symbol, CandleTimeframe.FIFTEEN_MINUTES, symbol_prices[-40:])
    for target in ["BTCUSDT", symbol]:
        db.add(
            MarketSnapshot(
                symbol=target,
                last_price=Decimal("107"),
                bid_price=Decimal("106.99"),
                ask_price=Decimal("107.01"),
                bid_quantity=Decimal("1"),
                ask_quantity=Decimal("1"),
                spread_bps=Decimal("2"),
                snapshot_at=datetime.now(UTC),
            )
        )
    db.commit()


def test_promote_latest_signals_creates_and_reuses(client: TestClient, db_session: Session) -> None:
    seed_market(db_session)
    app = cast(Any, client.app)
    app.dependency_overrides[get_settings] = lambda: strategy_settings()
    try:
        first = client.post("/api/v1/signals/promote-latest", params={"refresh_scanner": "true"})
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["promoted_count"] >= 1
        assert first_payload["signals"]
        assert first_payload["signals"][0]["status"] == SignalStatus.NEW.value
        assert first_payload["signals"][0]["side"] == "buy"

        second = client.post("/api/v1/signals/promote-latest")
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["reused_count"] >= 1
        assert db_session.query(Signal).count() == first_payload["promoted_count"]
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_list_and_read_signal(client: TestClient, db_session: Session) -> None:
    seed_market(db_session)
    app = cast(Any, client.app)
    app.dependency_overrides[get_settings] = lambda: strategy_settings()
    try:
        promote = client.post("/api/v1/signals/promote-latest", params={"refresh_scanner": "true"})
        payload = promote.json()
        signal_id = payload["signals"][0]["signal_id"]

        listing = client.get("/api/v1/signals", params={"status": SignalStatus.NEW.value})
        assert listing.status_code == 200
        rows = listing.json()
        assert rows
        assert rows[0]["signal_grade"] in {"A", "B", "C"}

        detail = client.get(f"/api/v1/signals/{signal_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["signal_id"] == signal_id
        assert detail_payload["setup_id"] is not None
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_expired_signal_transitions_on_read(client: TestClient, db_session: Session) -> None:
    seed_market(db_session)
    app = cast(Any, client.app)
    app.dependency_overrides[get_settings] = lambda: strategy_settings(
        strategy_maximum_setup_age_seconds=60
    )
    try:
        promote = client.post("/api/v1/signals/promote-latest", params={"refresh_scanner": "true"})
        payload = promote.json()
        signal_id = payload["signals"][0]["signal_id"]
        row = db_session.query(Signal).first()
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.commit()

        detail = client.get(f"/api/v1/signals/{signal_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == SignalStatus.EXPIRED.value
    finally:
        app.dependency_overrides.pop(get_settings, None)
