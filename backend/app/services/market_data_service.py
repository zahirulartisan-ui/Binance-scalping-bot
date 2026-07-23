from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CandleTimeframe, MarketDataCycleStatus
from app.models.market_data import ExchangeSymbol, MarketDataCycle, MarketSnapshot, OhlcvCandle

LEVERAGED_TOKEN_SUFFIXES = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
TIMEFRAME_SECONDS = {
    CandleTimeframe.ONE_MINUTE: 60,
    CandleTimeframe.FIVE_MINUTES: 300,
    CandleTimeframe.FIFTEEN_MINUTES: 900,
}


class MarketDataValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedSymbol:
    symbol: str
    base_asset: str
    quote_asset: str
    trading_status: str
    tick_size: Decimal
    step_size: Decimal
    minimum_quantity: Decimal
    minimum_notional: Decimal
    price_precision: int
    quantity_precision: int


def to_decimal(value: Any, field_name: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MarketDataValidationError(f"{field_name} is not decimal-compatible") from exc
    return decimal_value


def millisecond_to_utc(value: Any, field_name: str) -> datetime:
    try:
        timestamp_ms = int(value)
    except (TypeError, ValueError) as exc:
        raise MarketDataValidationError(f"{field_name} is invalid") from exc
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC)


def is_eligible_symbol(raw: dict[str, Any]) -> bool:
    symbol = str(raw.get("symbol", "")).upper()
    return (
        symbol.endswith("USDT")
        and not symbol.endswith(LEVERAGED_TOKEN_SUFFIXES)
        and raw.get("status") == "TRADING"
        and raw.get("quoteAsset") == "USDT"
    )


def parse_symbol(raw: dict[str, Any]) -> ParsedSymbol:
    if not is_eligible_symbol(raw):
        raise MarketDataValidationError("symbol is not eligible")
    filters = {item.get("filterType"): item for item in raw.get("filters", [])}
    lot_size = filters.get("LOT_SIZE") or {}
    price_filter = filters.get("PRICE_FILTER") or {}
    min_notional = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL") or {}
    return ParsedSymbol(
        symbol=str(raw["symbol"]).upper(),
        base_asset=str(raw["baseAsset"]).upper(),
        quote_asset=str(raw["quoteAsset"]).upper(),
        trading_status=str(raw["status"]),
        tick_size=to_decimal(price_filter.get("tickSize"), "tickSize"),
        step_size=to_decimal(lot_size.get("stepSize"), "stepSize"),
        minimum_quantity=to_decimal(lot_size.get("minQty"), "minQty"),
        minimum_notional=to_decimal(min_notional.get("minNotional", "0"), "minNotional"),
        price_precision=int(raw["quotePrecision"]),
        quantity_precision=int(raw["baseAssetPrecision"]),
    )


def refresh_symbols(db: Session, exchange_info: dict[str, Any]) -> int:
    count = 0
    for raw in exchange_info.get("symbols", []):
        if not isinstance(raw, dict) or not is_eligible_symbol(raw):
            continue
        parsed = parse_symbol(raw)
        symbol = db.scalar(select(ExchangeSymbol).where(ExchangeSymbol.symbol == parsed.symbol))
        if symbol is None:
            symbol = ExchangeSymbol(symbol=parsed.symbol)
            db.add(symbol)
        symbol.base_asset = parsed.base_asset
        symbol.quote_asset = parsed.quote_asset
        symbol.trading_status = parsed.trading_status
        symbol.tick_size = parsed.tick_size
        symbol.step_size = parsed.step_size
        symbol.minimum_quantity = parsed.minimum_quantity
        symbol.minimum_notional = parsed.minimum_notional
        symbol.price_precision = parsed.price_precision
        symbol.quantity_precision = parsed.quantity_precision
        symbol.refreshed_at = datetime.now(UTC)
        symbol.metadata_json = {}
        count += 1
    db.flush()
    return count


def ensure_symbol(db: Session, symbol: str) -> ExchangeSymbol:
    normalized = symbol.upper()
    row = db.scalar(select(ExchangeSymbol).where(ExchangeSymbol.symbol == normalized))
    if row is None or row.trading_status != "TRADING":
        raise MarketDataValidationError("symbol is not active")
    return row


def parse_closed_candle(
    raw: list[Any],
    symbol: str,
    timeframe: CandleTimeframe,
    now: datetime | None = None,
) -> OhlcvCandle:
    if len(raw) < 11:
        raise MarketDataValidationError("kline response is incomplete")
    now = now or datetime.now(UTC)
    open_time = millisecond_to_utc(raw[0], "open_time")
    close_time = millisecond_to_utc(raw[6], "close_time")
    expected_seconds = TIMEFRAME_SECONDS[timeframe]
    if close_time <= open_time:
        raise MarketDataValidationError("candle close_time must be after open_time")
    if (close_time - open_time).total_seconds() + 1 < expected_seconds:
        raise MarketDataValidationError("candle interval is incomplete")
    if close_time >= now:
        raise MarketDataValidationError("currently open candle cannot be stored")

    open_price = to_decimal(raw[1], "open")
    high_price = to_decimal(raw[2], "high")
    low_price = to_decimal(raw[3], "low")
    close_price = to_decimal(raw[4], "close")
    volume = to_decimal(raw[5], "volume")
    quote_volume = to_decimal(raw[7], "quote_volume")
    trade_count = int(raw[8])
    values = [open_price, high_price, low_price, close_price]
    if any(value <= 0 for value in values):
        raise MarketDataValidationError("prices must be positive")
    if high_price < max(open_price, close_price) or low_price > min(open_price, close_price):
        raise MarketDataValidationError("OHLC values are impossible")
    if volume < 0 or quote_volume < 0 or trade_count < 0:
        raise MarketDataValidationError("activity values cannot be negative")
    return OhlcvCandle(
        symbol=symbol.upper(),
        timeframe=timeframe,
        open_time=open_time,
        close_time=close_time,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
        quote_volume=quote_volume,
        trade_count=trade_count,
    )


def persist_candle(db: Session, candle: OhlcvCandle) -> bool:
    existing = db.scalar(
        select(OhlcvCandle).where(
            OhlcvCandle.symbol == candle.symbol,
            OhlcvCandle.timeframe == candle.timeframe,
            OhlcvCandle.open_time == candle.open_time,
        )
    )
    if existing is not None:
        return False
    previous = db.scalar(
        select(OhlcvCandle)
        .where(OhlcvCandle.symbol == candle.symbol, OhlcvCandle.timeframe == candle.timeframe)
        .order_by(OhlcvCandle.open_time.desc())
        .limit(1)
    )
    if previous is not None and candle.open_time <= previous.open_time:
        raise MarketDataValidationError("candle is out of order")
    db.add(candle)
    db.flush()
    return True


def parse_snapshot(
    symbol: str,
    price_payload: dict[str, Any],
    book_payload: dict[str, Any],
    snapshot_at: datetime | None = None,
) -> MarketSnapshot:
    snapshot_at = snapshot_at or datetime.now(UTC)
    last_price = to_decimal(price_payload.get("price"), "last_price")
    bid_price = to_decimal(book_payload.get("bidPrice"), "bid_price")
    ask_price = to_decimal(book_payload.get("askPrice"), "ask_price")
    bid_quantity = to_decimal(book_payload.get("bidQty"), "bid_quantity")
    ask_quantity = to_decimal(book_payload.get("askQty"), "ask_quantity")
    if min(last_price, bid_price, ask_price, bid_quantity, ask_quantity) <= 0:
        raise MarketDataValidationError("snapshot values must be positive")
    if bid_price > ask_price:
        raise MarketDataValidationError("book is crossed")
    if (datetime.now(UTC) - snapshot_at).total_seconds() > 60:
        raise MarketDataValidationError("snapshot timestamp is stale")
    mid_price = (bid_price + ask_price) / Decimal("2")
    spread_bps = ((ask_price - bid_price) / mid_price) * Decimal("10000")
    return MarketSnapshot(
        symbol=symbol.upper(),
        last_price=last_price,
        bid_price=bid_price,
        ask_price=ask_price,
        bid_quantity=bid_quantity,
        ask_quantity=ask_quantity,
        spread_bps=spread_bps,
        snapshot_at=snapshot_at,
    )


def persist_snapshot(db: Session, snapshot: MarketSnapshot) -> bool:
    existing = db.scalar(
        select(MarketSnapshot).where(
            MarketSnapshot.symbol == snapshot.symbol,
            MarketSnapshot.snapshot_at == snapshot.snapshot_at,
        )
    )
    if existing is not None:
        return False
    db.add(snapshot)
    db.flush()
    return True


def create_cycle(db: Session, symbols_requested: int) -> MarketDataCycle:
    cycle = MarketDataCycle(
        status=MarketDataCycleStatus.STARTED,
        symbols_requested=symbols_requested,
        rejection_reasons={},
    )
    db.add(cycle)
    db.flush()
    return cycle


def finish_cycle(
    cycle: MarketDataCycle,
    *,
    succeeded: int,
    failed: int,
    candles_stored: int,
    snapshots_stored: int,
    rejection_reasons: dict[str, str],
) -> None:
    finished_at = datetime.now(UTC)
    cycle.finished_at = finished_at
    cycle.duration_ms = int((finished_at - cycle.started_at).total_seconds() * 1000)
    cycle.symbols_succeeded = succeeded
    cycle.symbols_failed = failed
    cycle.candles_stored = candles_stored
    cycle.snapshots_stored = snapshots_stored
    cycle.rejection_reasons = rejection_reasons
    if failed and succeeded:
        cycle.status = MarketDataCycleStatus.PARTIAL_FAILURE
    elif failed:
        cycle.status = MarketDataCycleStatus.FAILED
    else:
        cycle.status = MarketDataCycleStatus.COMPLETED
