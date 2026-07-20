from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import CandleTimeframe, EntryPermission, MarketRegime
from app.models.market_data import ExchangeSymbol, MarketSnapshot, OhlcvCandle
from app.services.indicators import ema, realized_volatility_percent
from app.services.market_regime_service import MarketRegimeService


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


def seed_candles(
    db: Session,
    symbol: str,
    prices: list[Decimal],
    volume: Decimal = Decimal("10"),
) -> None:
    start = datetime.now(UTC) - timedelta(minutes=len(prices) + 2)
    for index, price in enumerate(prices):
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
                volume=volume,
                quote_volume=volume * price,
                trade_count=10,
            )
        )
    db.add(
        MarketSnapshot(
            symbol=symbol,
            last_price=prices[-1],
            bid_price=prices[-1] * Decimal("0.9999"),
            ask_price=prices[-1] * Decimal("1.0001"),
            bid_quantity=Decimal("1"),
            ask_quantity=Decimal("1"),
            spread_bps=Decimal("2"),
            snapshot_at=datetime.now(UTC),
        )
    )


def service() -> MarketRegimeService:
    return MarketRegimeService(
        Settings(
            app_env="test",
            database_url="sqlite+pysqlite:///:memory:",
            regime_minimum_candles=60,
            regime_trend_strength_threshold=Decimal("1"),
            regime_range_compression_threshold=Decimal("0.3"),
            regime_atr_percent_max=Decimal("10"),
        )
    )


def prepare(db: Session, symbol: str, prices: list[Decimal]) -> None:
    seed_symbol(db, "BTCUSDT")
    seed_candles(db, "BTCUSDT", [Decimal("100") + Decimal(i) / Decimal("100") for i in range(220)])
    if symbol != "BTCUSDT":
        seed_symbol(db, symbol)
        seed_candles(db, symbol, prices)
    db.commit()


def test_bullish_and_bearish_trending_fixtures(db_session: Session) -> None:
    bullish_prices = [Decimal("100") + Decimal(i) / Decimal("10") for i in range(220)]
    prepare(db_session, "ETHUSDT", bullish_prices)
    bullish = service().evaluate_symbol(db_session, "ETHUSDT")
    assert bullish.primary_regime is MarketRegime.TRENDING_BULLISH
    assert bullish.entry_permission is EntryPermission.ALLOW_LONG

    db_session.query(OhlcvCandle).filter(OhlcvCandle.symbol == "ETHUSDT").delete()
    bearish_prices = [Decimal("130") - Decimal(i) / Decimal("10") for i in range(220)]
    seed_candles(db_session, "ETHUSDT", bearish_prices)
    db_session.commit()
    bearish = service().evaluate_symbol(db_session, "ETHUSDT")
    assert bearish.primary_regime is MarketRegime.TRENDING_BEARISH


def test_ranging_high_volatility_abnormal_and_spread(db_session: Session) -> None:
    ranging_prices = [Decimal("100") + (Decimal(i % 2) / Decimal("100")) for i in range(220)]
    prepare(db_session, "ADAUSDT", ranging_prices)
    ranging = service().evaluate_symbol(db_session, "ADAUSDT")
    assert ranging.primary_regime in {MarketRegime.RANGING, MarketRegime.NO_TRADE}

    latest = db_session.query(MarketSnapshot).filter(MarketSnapshot.symbol == "ADAUSDT").one()
    latest.spread_bps = Decimal("100")
    db_session.commit()
    abnormal = service().evaluate_symbol(db_session, "ADAUSDT")
    assert abnormal.primary_regime is MarketRegime.ABNORMAL_MARKET
    assert "extreme_spread" in abnormal.safety_conditions


def test_insufficient_stale_btc_block_cache_and_api_shape(db_session: Session) -> None:
    seed_symbol(db_session, "BTCUSDT")
    seed_candles(db_session, "BTCUSDT", [Decimal("100") for _ in range(20)])
    seed_symbol(db_session, "SOLUSDT")
    sol_prices = [Decimal("10") + Decimal(i) / Decimal("10") for i in range(220)]
    seed_candles(db_session, "SOLUSDT", sol_prices)
    db_session.commit()
    svc = service()
    result = svc.evaluate_symbol(db_session, "SOLUSDT")
    assert result.entry_permission is EntryPermission.BLOCK_NEW_ENTRIES
    assert result.market_wide_block is True
    assert svc.evaluate_symbol(db_session, "SOLUSDT") == result


def test_indicator_edge_cases_no_nan_or_infinite() -> None:
    assert ema([Decimal("1")], 20) is None
    assert realized_volatility_percent([Decimal("0"), Decimal("1")], 1) is None
