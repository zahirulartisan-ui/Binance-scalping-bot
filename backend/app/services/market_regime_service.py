from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import AppEnvironment, Settings
from app.models.enums import CandleTimeframe, EntryPermission, MarketRegime, TrendDirection
from app.models.market_data import ExchangeSymbol, MarketSnapshot, OhlcvCandle
from app.models.regime import MarketRegimeSnapshot
from app.services.indicators import atr, ema, realized_volatility_percent, trend_strength_proxy


class RegimeUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class RegimeEvaluation:
    symbol: str
    evaluated_at: datetime
    primary_regime: MarketRegime
    entry_permission: EntryPermission
    confidence_score: Decimal
    trend_direction: TrendDirection
    trend_strength_value: Decimal
    volatility_value: Decimal
    spread_value: Decimal | None
    data_fresh: bool
    btc_regime: MarketRegime
    market_wide_block: bool
    reasons: list[str]
    safety_conditions: list[str]
    indicator_snapshot: dict[str, Any]


class MarketRegimeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, tuple[datetime, RegimeEvaluation]] = {}

    def evaluate_symbol(self, db: Session, symbol: str) -> RegimeEvaluation:
        normalized = symbol.upper()
        now = datetime.now(UTC)
        cached = self._cache.get(normalized)
        if cached and (now - cached[0]).total_seconds() <= self.settings.regime_cache_seconds:
            return cached[1]

        btc = self._evaluate_one(db, "BTCUSDT", MarketRegime.NO_TRADE)
        if normalized == "BTCUSDT":
            result = btc
        else:
            result = self._evaluate_one(db, normalized, btc.primary_regime)
        if normalized != "BTCUSDT":
            result = self._apply_btc_filter(result, btc)
        self._cache[normalized] = (now, result)
        self._persist_latest(db, result)
        return result

    def annotate_scanner_candidates(
        self,
        db: Session,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        annotated: list[dict[str, Any]] = []
        for original in candidates:
            candidate = dict(original)
            result = self.evaluate_symbol(db, str(candidate["symbol"]))
            tradeable = result.entry_permission is not EntryPermission.BLOCK_NEW_ENTRIES
            candidate["regime_result"] = result
            candidate["final_tradeable"] = tradeable
            candidate["rejection_reasons"] = [] if tradeable else result.reasons
            annotated.append(candidate)
        return annotated

    def _evaluate_one(
        self,
        db: Session,
        symbol: str,
        btc_regime: MarketRegime,
    ) -> RegimeEvaluation:
        exists = db.scalar(select(ExchangeSymbol.id).where(ExchangeSymbol.symbol == symbol))
        if exists is None:
            if (
                self.settings.app_env is AppEnvironment.TEST
                and self._is_locally_supported_symbol(symbol)
            ):
                return self._make_result(
                    symbol,
                    datetime.now(UTC),
                    MarketRegime.INSUFFICIENT_DATA,
                    EntryPermission.BLOCK_NEW_ENTRIES,
                    TrendDirection.FLAT,
                    Decimal("0"),
                    Decimal("0"),
                    None,
                    False,
                    btc_regime,
                    False,
                    ["local test database has no seeded market data yet"],
                    ["insufficient_data", "local_seed_missing"],
                    {},
                )
            raise RegimeUnavailableError("unsupported symbol")
        candles = list(
            db.scalars(
                select(OhlcvCandle)
                .where(
                    OhlcvCandle.symbol == symbol,
                    OhlcvCandle.timeframe == CandleTimeframe.ONE_MINUTE,
                )
                .order_by(OhlcvCandle.open_time.desc())
                .limit(max(self.settings.regime_minimum_candles, 220))
            )
        )
        candles.reverse()
        snapshot = db.scalars(
            select(MarketSnapshot)
            .where(MarketSnapshot.symbol == symbol)
            .order_by(MarketSnapshot.snapshot_at.desc())
            .limit(1)
        ).first()
        return self._classify(symbol, candles, snapshot, btc_regime)

    def _classify(
        self,
        symbol: str,
        candles: list[OhlcvCandle],
        snapshot: MarketSnapshot | None,
        btc_regime: MarketRegime,
    ) -> RegimeEvaluation:
        now = datetime.now(UTC)
        if len(candles) < self.settings.regime_minimum_candles:
            return self._make_result(
                symbol,
                now,
                MarketRegime.INSUFFICIENT_DATA,
                EntryPermission.BLOCK_NEW_ENTRIES,
                TrendDirection.FLAT,
                Decimal("0"),
                Decimal("0"),
                None,
                False,
                btc_regime,
                False,
                ["required candle history is unavailable"],
                ["insufficient_data"],
                {},
            )

        indicators = self._indicators(candles, snapshot, now)
        reasons: list[str] = []
        safety: list[str] = []
        spread = indicators["spread"]
        atr_percent = indicators["atr_percent"]
        rv = indicators["realized_volatility"]

        if not indicators["data_fresh"]:
            safety.append("stale_market_data")
            reasons.append("latest market snapshot is missing or stale")
        if spread is not None and spread > Decimal(str(self.settings.regime_max_spread_bps)):
            safety.append("extreme_spread")
            reasons.append("spread is above configured safe threshold")
        abnormal_candle_threshold = Decimal(str(self.settings.regime_abnormal_candle_percent))
        if indicators["last_displacement"] > abnormal_candle_threshold:
            safety.append("abnormal_candle")
            reasons.append("latest candle displacement is abnormal")
        if indicators["volume_ratio"] > Decimal(str(self.settings.regime_volume_spike_multiplier)):
            safety.append("abnormal_volume")
            reasons.append("latest volume is an abnormal spike")
        if safety:
            return self._blocked(
                symbol,
                now,
                MarketRegime.ABNORMAL_MARKET,
                indicators,
                btc_regime,
                reasons,
                safety,
            )

        max_volatility = max(atr_percent, rv)
        if atr_percent > Decimal(str(self.settings.regime_atr_percent_max)) or rv > Decimal(
            str(self.settings.regime_realized_volatility_max)
        ):
            return self._blocked(
                symbol,
                now,
                MarketRegime.HIGH_VOLATILITY,
                indicators,
                btc_regime,
                ["volatility is above configured usable range"],
                ["high_volatility"],
            )

        ema20 = indicators["ema20"]
        ema50 = indicators["ema50"]
        ema200 = indicators["ema200"]
        if ema20 is None or ema50 is None:
            return self._blocked(
                symbol,
                now,
                MarketRegime.INSUFFICIENT_DATA,
                indicators,
                btc_regime,
                ["EMA inputs are unavailable"],
                ["insufficient_data"],
            )

        trend_strength = indicators["trend_strength"]
        trend_threshold = Decimal(str(self.settings.regime_trend_strength_threshold))
        slope = indicators["slope"]
        slope_threshold = Decimal(str(self.settings.regime_ema_slope_threshold))
        close = indicators["close"]
        bullish = ema20 > ema50 and (ema200 is None or ema50 > ema200)
        bullish = bullish and close > ema20 and slope > slope_threshold
        bearish = ema20 < ema50 and (ema200 is None or ema50 < ema200)
        bearish = bearish and close < ema20 and slope < -slope_threshold

        if bullish and trend_strength >= trend_threshold:
            return self._make_result(
                symbol,
                now,
                MarketRegime.TRENDING_BULLISH,
                EntryPermission.ALLOW_LONG,
                TrendDirection.BULLISH,
                trend_strength,
                max_volatility,
                spread,
                bool(indicators["data_fresh"]),
                btc_regime,
                False,
                ["EMA stack and slope support bullish trend"],
                [],
                self._snapshot(indicators),
            )
        if bearish and trend_strength >= trend_threshold:
            return self._make_result(
                symbol,
                now,
                MarketRegime.TRENDING_BEARISH,
                EntryPermission.ALLOW_SHORT,
                TrendDirection.BEARISH,
                trend_strength,
                max_volatility,
                spread,
                bool(indicators["data_fresh"]),
                btc_regime,
                False,
                ["EMA stack and slope support bearish trend"],
                [],
                self._snapshot(indicators),
            )

        if trend_strength < trend_threshold and indicators["recent_range"] <= Decimal(
            str(self.settings.regime_range_compression_threshold)
        ):
            return self._blocked(
                symbol,
                now,
                MarketRegime.RANGING,
                indicators,
                btc_regime,
                ["trend strength is weak and recent range is compressed"],
                ["ranging_market"],
            )
        return self._blocked(
            symbol,
            now,
            MarketRegime.NO_TRADE,
            indicators,
            btc_regime,
            ["trend, volatility, and confirmation evidence are conflicting"],
            ["conflicting_evidence"],
        )

    def _indicators(
        self,
        candles: list[OhlcvCandle],
        snapshot: MarketSnapshot | None,
        now: datetime,
    ) -> dict[str, Any]:
        closes = [candle.close_price for candle in candles]
        highs = [candle.high_price for candle in candles]
        lows = [candle.low_price for candle in candles]
        volumes = [candle.volume for candle in candles]
        ema20 = ema(closes, 20)
        previous_ema20 = ema(closes[:-5], 20) if len(closes) >= 25 else None
        ema50 = ema(closes, 50)
        ema200 = ema(closes, 200) if len(closes) >= 200 else None
        atr_value = atr(highs, lows, closes) or Decimal("0")
        close = closes[-1]
        atr_percent = (atr_value / close) * Decimal("100") if close > 0 else Decimal("0")
        recent_range = ((max(highs[-20:]) - min(lows[-20:])) / close) * Decimal("100")
        average_volume = sum(volumes[-20:]) / Decimal(20)
        volume_ratio = volumes[-1] / average_volume if average_volume > 0 else Decimal("0")
        displacement = abs(
            (candles[-1].close_price - candles[-1].open_price) / candles[-1].open_price
        )
        slope = Decimal("0")
        if ema20 is not None and previous_ema20 is not None and previous_ema20 > 0:
            slope = ((ema20 - previous_ema20) / previous_ema20) * Decimal("100")
        return {
            "close": close,
            "ema20": ema20,
            "ema50": ema50,
            "ema200": ema200,
            "atr_percent": atr_percent,
            "realized_volatility": realized_volatility_percent(closes) or Decimal("0"),
            "trend_strength": trend_strength_proxy(closes),
            "recent_range": recent_range,
            "volume_ratio": volume_ratio,
            "last_displacement": displacement * Decimal("100"),
            "spread": snapshot.spread_bps if snapshot else None,
            "data_fresh": bool(snapshot and (now - snapshot.snapshot_at).total_seconds() <= 60),
            "slope": slope,
        }

    def _blocked(
        self,
        symbol: str,
        now: datetime,
        regime: MarketRegime,
        indicators: dict[str, Any],
        btc_regime: MarketRegime,
        reasons: list[str],
        safety: list[str],
    ) -> RegimeEvaluation:
        return self._make_result(
            symbol,
            now,
            regime,
            EntryPermission.BLOCK_NEW_ENTRIES,
            TrendDirection.FLAT,
            indicators["trend_strength"],
            max(indicators["atr_percent"], indicators["realized_volatility"]),
            indicators["spread"],
            bool(indicators["data_fresh"]),
            btc_regime,
            False,
            reasons,
            safety,
            self._snapshot(indicators),
        )

    def _apply_btc_filter(
        self,
        result: RegimeEvaluation,
        btc: RegimeEvaluation,
    ) -> RegimeEvaluation:
        block_regimes = {
            MarketRegime.ABNORMAL_MARKET,
            MarketRegime.HIGH_VOLATILITY,
            MarketRegime.INSUFFICIENT_DATA,
        }
        reasons = list(result.reasons)
        safety = list(result.safety_conditions)
        block = btc.primary_regime in block_regimes
        if block:
            reasons.append(f"BTC market-wide regime blocks entries: {btc.primary_regime.value}")
            safety.append("btc_market_wide_block")
        if (
            result.entry_permission is EntryPermission.ALLOW_LONG
            and btc.primary_regime is MarketRegime.TRENDING_BEARISH
        ):
            block = True
            reasons.append("BTC bearish regime conflicts with long entries")
            safety.append("btc_direction_conflict")
        if (
            result.entry_permission is EntryPermission.ALLOW_SHORT
            and btc.primary_regime is MarketRegime.TRENDING_BULLISH
        ):
            block = True
            reasons.append("BTC bullish regime conflicts with short entries")
            safety.append("btc_direction_conflict")
        if not block:
            return result
        payload = asdict(result)
        payload.update(
            entry_permission=EntryPermission.BLOCK_NEW_ENTRIES,
            btc_regime=btc.primary_regime,
            market_wide_block=True,
            reasons=reasons,
            safety_conditions=safety,
        )
        return RegimeEvaluation(**payload)

    def _make_result(
        self,
        symbol: str,
        evaluated_at: datetime,
        regime: MarketRegime,
        permission: EntryPermission,
        direction: TrendDirection,
        trend: Decimal,
        volatility: Decimal,
        spread: Decimal | None,
        fresh: bool,
        btc_regime: MarketRegime,
        market_block: bool,
        reasons: list[str],
        safety: list[str],
        indicators: dict[str, Any],
    ) -> RegimeEvaluation:
        confidence = (
            Decimal("0.0") if permission is EntryPermission.BLOCK_NEW_ENTRIES else Decimal("1.0")
        )
        return RegimeEvaluation(
            symbol,
            evaluated_at,
            regime,
            permission,
            confidence,
            direction,
            trend,
            volatility,
            spread,
            fresh,
            btc_regime,
            market_block,
            reasons,
            safety,
            indicators,
        )

    def _is_locally_supported_symbol(self, symbol: str) -> bool:
        configured_symbols = {item.upper() for item in self.settings.market_data_symbols}
        configured_symbols.add("BTCUSDT")
        return symbol.upper() in configured_symbols

    def _snapshot(self, indicators: dict[str, Any]) -> dict[str, str]:
        keys = {
            "ema20",
            "ema50",
            "ema200",
            "atr_percent",
            "realized_volatility",
            "recent_range",
            "volume_ratio",
            "last_displacement",
            "slope",
        }
        return {key: str(value) for key, value in indicators.items() if key in keys}

    def _persist_latest(self, db: Session, result: RegimeEvaluation) -> None:
        row = db.scalar(
            select(MarketRegimeSnapshot).where(MarketRegimeSnapshot.symbol == result.symbol)
        )
        if row is None:
            row = MarketRegimeSnapshot(symbol=result.symbol)
            db.add(row)
        row.evaluated_at = result.evaluated_at
        row.regime = result.primary_regime
        row.entry_permission = result.entry_permission
        row.confidence_score = result.confidence_score
        row.trend_direction = result.trend_direction
        row.trend_strength = result.trend_strength_value
        row.volatility_value = result.volatility_value
        row.spread_bps = result.spread_value
        row.data_fresh = result.data_fresh
        row.btc_regime = result.btc_regime
        row.market_wide_block = result.market_wide_block
        row.reasons = result.reasons
        row.safety_conditions = result.safety_conditions
        row.indicator_snapshot = result.indicator_snapshot
        db.flush()
