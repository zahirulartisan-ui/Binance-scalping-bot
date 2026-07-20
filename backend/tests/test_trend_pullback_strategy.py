from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import (
    CandleTimeframe,
    ScannerDecisionType,
    ScannerRunStatus,
    StrategySetupState,
)
from app.models.market_data import ExchangeSymbol, MarketSnapshot, OhlcvCandle
from app.models.strategy import StrategySetup
from app.models.trading import ScannerDecision, ScannerRun
from app.services.trend_pullback_strategy import (
    EntryZoneCalculator,
    LiquiditySweepDetector,
    MarketStructureShiftDetector,
    PullbackDetector,
    RejectionConfirmationDetector,
    StopLossCalculator,
    TakeProfitCalculator,
    TrendPullbackStrategyService,
    VolumeConfirmationService,
    safe_div,
)


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
    run = ScannerRun(status=ScannerRunStatus.COMPLETED, idempotency_key="scan-1")
    db.add(run)
    db.flush()
    db.add(
        ScannerDecision(
            scanner_run_id=run.id,
            symbol=symbol,
            decision=ScannerDecisionType.SIGNAL_CANDIDATE,
            reason_code="fixture",
        )
    )
    db.commit()


def test_valid_bullish_strategy_ready_and_persisted(db_session: Session) -> None:
    seed_market(db_session)
    service = TrendPullbackStrategyService(strategy_settings())
    result = service.evaluate_symbol(db_session, "ETHUSDT", refresh=True)
    assert result.setup_state is StrategySetupState.READY
    assert result.eligible_for_signal is True
    assert result.reward_to_risk is not None
    assert result.reward_to_risk >= Decimal("1.5")
    assert db_session.query(StrategySetup).filter_by(setup_id=result.setup_id).count() == 1

    repeat = service.evaluate_symbol(db_session, "ETHUSDT")
    assert repeat.setup_id == result.setup_id


def test_bearish_and_short_only_rejection(db_session: Session) -> None:
    seed_market(db_session)
    db_session.query(OhlcvCandle).filter(OhlcvCandle.symbol == "ETHUSDT").delete()
    bearish = [Decimal("130") - Decimal(i) * Decimal("0.06") for i in range(220)]
    seed_candles(db_session, "ETHUSDT", CandleTimeframe.ONE_MINUTE, bearish)
    seed_candles(db_session, "ETHUSDT", CandleTimeframe.FIVE_MINUTES, bearish)
    seed_candles(db_session, "ETHUSDT", CandleTimeframe.FIFTEEN_MINUTES, bearish[-40:])
    db_session.commit()
    result = TrendPullbackStrategyService(strategy_settings()).evaluate_symbol(
        db_session,
        "ETHUSDT",
        refresh=True,
    )
    assert result.setup_state is StrategySetupState.BLOCKED_BY_REGIME
    assert "current spot trading mode does not support short execution" in result.reasons


def test_pullback_detector_depth_duration_and_structure() -> None:
    settings = strategy_settings()
    start = datetime.now(UTC) - timedelta(minutes=100)
    prices = [Decimal("100") + Decimal(i) * Decimal("0.05") for i in range(90)]
    candles = [
        candle("ETHUSDT", CandleTimeframe.ONE_MINUTE, start + timedelta(minutes=i), price)
        for i, price in enumerate(prices)
    ]
    valid = PullbackDetector(settings).detect(candles)
    assert valid.detected

    shallow = PullbackDetector(
        strategy_settings(
            strategy_minimum_pullback_percent=5,
            strategy_maximum_pullback_percent=6,
        )
    ).detect(candles)
    assert "pullback_too_shallow" in shallow.failed_conditions

    deep = PullbackDetector(
        strategy_settings(
            strategy_minimum_pullback_percent=0.001,
            strategy_maximum_pullback_percent=0.01,
        )
    ).detect(candles)
    assert "pullback_too_deep" in deep.failed_conditions


def test_rejection_volume_sweep_mss_stop_target_and_division_edges() -> None:
    settings = strategy_settings()
    start = datetime.now(UTC) - timedelta(minutes=100)
    candles = [
        candle(
            "ETHUSDT",
            CandleTimeframe.ONE_MINUTE,
            start + timedelta(minutes=i),
            Decimal("100") + Decimal(i) * Decimal("0.03"),
            Decimal("6") if 82 <= i <= 88 else Decimal("10"),
        )
        for i in range(90)
    ]
    candles[-2] = candle(
        "ETHUSDT",
        CandleTimeframe.ONE_MINUTE,
        start + timedelta(minutes=88),
        Decimal("102.30"),
        Decimal("7"),
        close=Decimal("102.40"),
        low=Decimal("101.00"),
        high=Decimal("102.45"),
    )
    candles[-1] = candle(
        "ETHUSDT",
        CandleTimeframe.ONE_MINUTE,
        start + timedelta(minutes=89),
        Decimal("102.20"),
        Decimal("18"),
        close=Decimal("103.20"),
        low=Decimal("102.00"),
        high=Decimal("103.80"),
    )
    rejection = RejectionConfirmationDetector(settings).detect(candles[-1], Decimal("102"))
    volume = VolumeConfirmationService(settings).confirm(candles)
    sweep = LiquiditySweepDetector(settings).detect(candles)
    mss = MarketStructureShiftDetector(settings).detect(candles)
    pullback = PullbackDetector(settings).detect(candles)
    stop = StopLossCalculator(settings).calculate(
        Decimal("102.50"), pullback, sweep, Decimal("0.10")
    )
    target = TakeProfitCalculator(settings).calculate(
        Decimal("102.50"),
        stop.values["stop_loss"],
        candles,
    )
    zone = EntryZoneCalculator(settings).calculate(
        candles, Decimal("102"), Decimal("101.5"), Decimal("0.1")
    )

    assert rejection.detected
    assert volume.detected
    assert sweep.detected
    assert mss.detected
    assert stop.detected
    assert target.detected
    assert zone.position in {"inside", "above"}
    assert safe_div(Decimal("1"), Decimal("0")) == Decimal("0")


def test_scanner_rejection_and_api_errors(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/api/v1/strategies")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Trend Pullback Continuation"

    invalid = client.get("/api/v1/strategies/trend-pullback/BTC-USD")
    assert invalid.status_code == 422

    missing = client.get("/api/v1/strategies/trend-pullback/ETHUSDT")
    assert missing.status_code in {404, 409}


def test_persistence_deduplicates(db_session: Session) -> None:
    seed_market(db_session)
    service = TrendPullbackStrategyService(strategy_settings())
    first = service.evaluate_symbol(db_session, "ETHUSDT", refresh=True)
    second = service.evaluate_symbol(db_session, "ETHUSDT", refresh=True)
    assert first.setup_id == second.setup_id
    assert db_session.query(StrategySetup).filter_by(setup_id=first.setup_id).count() == 1
