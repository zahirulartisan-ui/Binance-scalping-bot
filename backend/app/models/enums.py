from __future__ import annotations

from enum import StrEnum


class AppSettingValueType(StrEnum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    DECIMAL = "decimal"
    STRING = "string"
    JSON = "json"


class ScannerRunStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class ScannerDecisionType(StrEnum):
    WATCH = "watch"
    IGNORE = "ignore"
    SIGNAL_CANDIDATE = "signal_candidate"


class SignalStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderStatus(StrEnum):
    CREATED = "created"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    FAILED = "failed"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LIMIT = "stop_limit"


class PositionStatus(StrEnum):
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


class PositionEventType(StrEnum):
    OPENED = "opened"
    INCREASED = "increased"
    REDUCED = "reduced"
    CLOSED = "closed"
    STOP_UPDATED = "stop_updated"


class RiskDecisionStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class JournalEntryType(StrEnum):
    NOTE = "note"
    REVIEW = "review"
    INCIDENT = "incident"


class SystemEventLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CandleTimeframe(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"


class MarketDataCycleStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    SKIPPED = "skipped"


class MarketRegime(StrEnum):
    TRENDING_BULLISH = "TRENDING_BULLISH"
    TRENDING_BEARISH = "TRENDING_BEARISH"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    ABNORMAL_MARKET = "ABNORMAL_MARKET"
    NO_TRADE = "NO_TRADE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class EntryPermission(StrEnum):
    ALLOW_LONG = "ALLOW_LONG"
    ALLOW_SHORT = "ALLOW_SHORT"
    ALLOW_BOTH = "ALLOW_BOTH"
    BLOCK_NEW_ENTRIES = "BLOCK_NEW_ENTRIES"


class TrendDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    FLAT = "flat"
