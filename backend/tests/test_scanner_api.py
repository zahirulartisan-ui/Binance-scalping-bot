from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.models.enums import CandleTimeframe, ScannerDecisionType, ScannerRunStatus
from app.models.market_data import ExchangeSymbol, MarketSnapshot, OhlcvCandle
from app.models.trading import ScannerDecision, ScannerRun


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


def test_scanner_status_empty(client: TestClient) -> None:
    response = client.get("/api/v1/scanner/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_run_id"] is None
    assert payload["symbols_scanned"] == 0


def test_scanner_run_and_candidates(client: TestClient, db_session: Session) -> None:
    seed_market(db_session)
    app = cast(Any, client.app)
    app.dependency_overrides[get_settings] = lambda: strategy_settings()
    try:
        run_response = client.post("/api/v1/scanner/run")
        assert run_response.status_code == 200
        run_payload = run_response.json()
        assert run_payload["status"] == ScannerRunStatus.COMPLETED.value

        status_response = client.get("/api/v1/scanner/status")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        assert status_payload["latest_run_id"] == run_payload["run_id"]
        assert status_payload["symbols_scanned"] >= 1

        candidates_response = client.get(
            "/api/v1/scanner/candidates",
            params={"decision": ScannerDecisionType.SIGNAL_CANDIDATE.value},
        )
        assert candidates_response.status_code == 200
        candidates = candidates_response.json()
        assert candidates
        assert candidates[0]["decision"] == ScannerDecisionType.SIGNAL_CANDIDATE.value
        assert candidates[0]["signal_grade"] in {"A", "B", "C"}

        run_detail = client.get(f"/api/v1/scanner/runs/{run_payload['run_id']}")
        assert run_detail.status_code == 200
        detail_payload = run_detail.json()
        assert detail_payload["run"]["run_id"] == run_payload["run_id"]
        assert detail_payload["decisions"]
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_scanner_candidates_refresh_creates_run(client: TestClient, db_session: Session) -> None:
    seed_market(db_session)
    app = cast(Any, client.app)
    app.dependency_overrides[get_settings] = lambda: strategy_settings()
    try:
        response = client.get("/api/v1/scanner/candidates", params={"refresh": "true"})
        assert response.status_code == 200
        rows = response.json()
        assert rows
        assert db_session.query(ScannerRun).count() == 1
        assert db_session.query(ScannerDecision).count() >= 1
    finally:
        app.dependency_overrides.pop(get_settings, None)
