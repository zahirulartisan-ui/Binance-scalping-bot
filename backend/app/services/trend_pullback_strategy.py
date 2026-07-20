from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import EvidenceMode, Settings
from app.models.enums import (
    CandleTimeframe,
    EntryPermission,
    MarketRegime,
    ScannerDecisionType,
    StrategyDirection,
    StrategySetupState,
)
from app.models.market_data import ExchangeSymbol, MarketSnapshot, OhlcvCandle
from app.models.strategy import StrategySetup
from app.models.trading import ScannerDecision
from app.services.indicators import atr, ema, trend_strength_proxy
from app.services.market_regime_service import MarketRegimeService, RegimeEvaluation

logger = logging.getLogger(__name__)
STRATEGY_NAME = "Trend Pullback Continuation"


class StrategyEvaluationError(ValueError):
    pass


@dataclass(frozen=True)
class EntryZone:
    lower: Decimal | None
    upper: Decimal | None
    preferred: Decimal | None
    distance: Decimal | None
    position: str
    method: str


@dataclass(frozen=True)
class EvidenceResult:
    detected: bool
    values: dict[str, Any]
    reasons: list[str]
    failed_conditions: list[str]


@dataclass(frozen=True)
class StrategyEvaluation:
    setup_id: str
    symbol: str
    strategy_name: str
    strategy_version: str
    evaluated_at: datetime
    setup_created_at: datetime
    setup_expires_at: datetime
    direction: StrategyDirection
    setup_state: StrategySetupState
    eligible_for_signal: bool
    regime: MarketRegime
    regime_permission: EntryPermission
    btc_regime: MarketRegime
    market_wide_block: bool
    one_minute_trend_summary: dict[str, Any]
    five_minute_trend_summary: dict[str, Any]
    fifteen_minute_context_summary: dict[str, Any]
    ema_snapshot: dict[str, Any]
    pullback_detected: bool
    pullback_depth: Decimal | None
    pullback_duration: int | None
    preceding_impulse_size: Decimal | None
    entry_zone_lower: Decimal | None
    entry_zone_upper: Decimal | None
    preferred_entry: Decimal | None
    current_price: Decimal | None
    distance_from_entry: Decimal | None
    entry_zone_position: str
    entry_zone_method: str
    volume_ratio: Decimal | None
    rejection_confirmation: dict[str, Any]
    liquidity_sweep: dict[str, Any]
    market_structure_shift: dict[str, Any]
    stop_loss: Decimal | None
    stop_calculation_method: str | None
    take_profit: Decimal | None
    target_calculation_method: str | None
    risk_amount: Decimal | None
    reward_amount: Decimal | None
    reward_to_risk: Decimal | None
    setup_age_seconds: int
    data_freshness: dict[str, Any]
    reasons: list[str]
    failed_conditions: list[str]
    triggered_safety_conditions: list[str]
    indicator_snapshot: dict[str, Any]


class StrategyCache:
    def __init__(self) -> None:
        self._items: dict[str, tuple[datetime, StrategyEvaluation]] = {}

    def get(self, key: str, ttl_seconds: int) -> StrategyEvaluation | None:
        item = self._items.get(key)
        if item is None:
            return None
        stored_at, result = item
        if (datetime.now(UTC) - stored_at).total_seconds() > ttl_seconds:
            self._items.pop(key, None)
            logger.info("strategy cache expired", extra={"symbol": result.symbol})
            return None
        logger.info("strategy cache hit", extra={"symbol": result.symbol})
        return result

    def set(self, key: str, value: StrategyEvaluation) -> None:
        self._items[key] = (datetime.now(UTC), value)


class StrategySetupRepository:
    def upsert(self, db: Session, result: StrategyEvaluation) -> StrategySetup:
        row = db.scalar(select(StrategySetup).where(StrategySetup.setup_id == result.setup_id))
        if row is None:
            row = StrategySetup(setup_id=result.setup_id)
            db.add(row)
        row.symbol = result.symbol
        row.strategy_name = result.strategy_name
        row.strategy_version = result.strategy_version
        row.direction = result.direction
        row.setup_state = result.setup_state
        row.evaluated_at = result.evaluated_at
        row.expires_at = result.setup_expires_at
        row.regime = result.regime.value
        row.entry_zone_low = result.entry_zone_lower
        row.entry_zone_high = result.entry_zone_upper
        row.preferred_entry = result.preferred_entry
        row.stop_loss = result.stop_loss
        row.take_profit = result.take_profit
        row.reward_to_risk = result.reward_to_risk
        row.pullback_depth = result.pullback_depth
        row.volume_ratio = result.volume_ratio
        row.liquidity_sweep_detected = bool(result.liquidity_sweep.get("detected"))
        row.mss_detected = bool(result.market_structure_shift.get("detected"))
        row.eligible_for_signal = result.eligible_for_signal
        row.reasons = result.reasons
        row.failed_conditions = result.failed_conditions
        row.indicator_snapshot = result.indicator_snapshot
        row.invalidated_at = (
            result.evaluated_at if result.setup_state is StrategySetupState.INVALIDATED else None
        )
        row.invalidation_reason = (
            result.reasons[0] if result.setup_state is StrategySetupState.INVALIDATED else None
        )
        db.flush()
        return row

    def list_setups(
        self,
        db: Session,
        state: StrategySetupState | None = None,
        eligible_only: bool = False,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[StrategySetup]:
        statement = select(StrategySetup).order_by(StrategySetup.evaluated_at.desc()).limit(limit)
        if state is not None:
            statement = statement.where(StrategySetup.setup_state == state)
        if eligible_only:
            statement = statement.where(StrategySetup.eligible_for_signal.is_(True))
        if symbol is not None:
            statement = statement.where(StrategySetup.symbol == symbol)
        return list(db.scalars(statement))

    def get_by_setup_id(self, db: Session, setup_id: str) -> StrategySetup | None:
        return db.scalar(select(StrategySetup).where(StrategySetup.setup_id == setup_id))


class PullbackDetector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def detect(self, candles: list[OhlcvCandle]) -> EvidenceResult:
        closes = [c.close_price for c in candles]
        lookback = self.settings.strategy_impulse_lookback
        recent = candles[-self.settings.strategy_maximum_pullback_candles :]
        impulse_base = min(c.low_price for c in candles[-lookback - len(recent) : -len(recent)])
        impulse_high = max(c.high_price for c in candles[-lookback:])
        if impulse_base <= 0:
            return self._failed("impulse base is not positive", "invalid_impulse_base")
        impulse = percent(impulse_high - impulse_base, impulse_base)
        pullback_low = min(c.low_price for c in recent)
        current = closes[-1]
        depth = percent(impulse_high - pullback_low, impulse_high)
        reasons: list[str] = []
        failed: list[str] = []
        if impulse < dec(self.settings.strategy_minimum_impulse_percent):
            failed.append("insufficient_impulse")
            reasons.append(
                f"Preceding impulse was {impulse}, below required "
                f"{self.settings.strategy_minimum_impulse_percent}"
            )
        if depth < dec(self.settings.strategy_minimum_pullback_percent):
            failed.append("pullback_too_shallow")
            reasons.append(
                f"Pullback depth was {depth}, below minimum "
                f"{self.settings.strategy_minimum_pullback_percent}"
            )
        if depth > dec(self.settings.strategy_maximum_pullback_percent):
            failed.append("pullback_too_deep")
            reasons.append(f"Pullback retracement exceeded the maximum permitted depth: {depth}")
        if current <= pullback_low:
            failed.append("structure_broken")
            reasons.append("Current price is at or below pullback structural low")
        detected = not failed
        return EvidenceResult(
            detected,
            {
                "depth": depth,
                "duration": len(recent),
                "impulse": impulse,
                "swing_low": pullback_low,
                "impulse_high": impulse_high,
            },
            ["valid trend pullback detected"] if detected else reasons,
            failed,
        )

    def _failed(self, reason: str, code: str) -> EvidenceResult:
        return EvidenceResult(False, {}, [reason], [code])


class EntryZoneCalculator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def calculate(
        self,
        candles: list[OhlcvCandle],
        ema20: Decimal,
        ema50: Decimal,
        atr_value: Decimal,
    ) -> EntryZone:
        tolerance = atr_value * dec(self.settings.strategy_entry_zone_atr_tolerance)
        lower = min(ema20, ema50) - tolerance
        upper = max(ema20, ema50) + tolerance
        preferred = ema20
        price = candles[-1].close_price
        if price < lower:
            position = "below"
            distance = lower - price
        elif price > upper:
            position = "above"
            distance = price - upper
        else:
            position = "inside"
            distance = Decimal("0")
        return EntryZone(
            lower, upper, preferred, distance, position, "EMA20/EMA50 plus ATR tolerance"
        )


class RejectionConfirmationDetector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def detect(self, candle: OhlcvCandle, ema20: Decimal) -> EvidenceResult:
        candle_range = candle.high_price - candle.low_price
        body = abs(candle.close_price - candle.open_price)
        lower_wick = min(candle.open_price, candle.close_price) - candle.low_price
        body_ratio = safe_div(body, candle_range)
        wick_ratio = safe_div(lower_wick, candle_range)
        bullish = candle.close_price > candle.open_price and candle.close_price >= ema20
        passed = (
            bullish
            and body_ratio >= dec(self.settings.strategy_minimum_rejection_body_ratio)
            and wick_ratio >= dec(self.settings.strategy_minimum_rejection_wick_ratio)
        )
        values = {
            "confirmed": passed,
            "body_ratio": body_ratio,
            "lower_wick_ratio": wick_ratio,
            "close_above_ema20": candle.close_price >= ema20,
        }
        if passed:
            return EvidenceResult(True, values, ["bullish rejection candle confirmed"], [])
        return EvidenceResult(
            False,
            values,
            ["Rejection candle did not meet body, wick, and EMA20 recovery requirements"],
            ["weak_rejection"],
        )


class VolumeConfirmationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def confirm(self, candles: list[OhlcvCandle]) -> EvidenceResult:
        lookback = self.settings.strategy_volume_lookback
        volumes = [c.volume for c in candles]
        average = sum(volumes[-lookback - 1 : -1]) / Decimal(lookback)
        current = volumes[-1]
        ratio = safe_div(current, average)
        pullback_average = sum(volumes[-6:-1]) / Decimal(5)
        contraction = safe_div(pullback_average, average)
        passed = ratio >= dec(
            self.settings.strategy_minimum_recovery_volume_ratio
        ) and contraction <= dec(self.settings.strategy_pullback_volume_contraction_threshold)
        values = {
            "current_volume": current,
            "rolling_average_volume": average,
            "current_volume_ratio": ratio,
            "pullback_average_volume": pullback_average,
            "recovery_candle_volume": current,
            "pullback_contraction_ratio": contraction,
        }
        if passed:
            return EvidenceResult(True, values, ["recovery volume expansion confirmed"], [])
        return EvidenceResult(
            False,
            values,
            [
                f"Recovery volume ratio was {ratio}, below required "
                f"{self.settings.strategy_minimum_recovery_volume_ratio}"
            ],
            ["insufficient_recovery_volume"],
        )


class LiquiditySweepDetector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def detect(self, candles: list[OhlcvCandle]) -> EvidenceResult:
        if self.settings.strategy_liquidity_sweep_mode is EvidenceMode.DISABLED:
            return EvidenceResult(False, {"mode": "disabled"}, ["liquidity sweep disabled"], [])
        lookback = self.settings.strategy_liquidity_sweep_lookback
        prior = candles[-lookback - 2 : -2]
        if not prior:
            return EvidenceResult(False, {}, ["not enough candles for liquidity sweep"], [])
        level = min(c.low_price for c in prior)
        sweep = candles[-2]
        confirm = candles[-1]
        depth = percent(level - sweep.low_price, level) if sweep.low_price < level else Decimal("0")
        detected = (
            sweep.low_price < level
            and sweep.close_price > level
            and confirm.close_price > sweep.close_price
            and depth >= dec(self.settings.strategy_minimum_sweep_depth_percent)
        )
        values = {
            "detected": detected,
            "swept_level": level if detected else None,
            "sweep_depth": depth,
            "sweep_candle_timestamp": sweep.close_time if detected else None,
            "confirmation_status": detected,
        }
        if detected:
            return EvidenceResult(True, values, ["bullish liquidity sweep confirmed"], [])
        return EvidenceResult(False, values, ["bullish liquidity sweep not detected"], [])


class MarketStructureShiftDetector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def detect(self, candles: list[OhlcvCandle]) -> EvidenceResult:
        if self.settings.strategy_mss_mode is EvidenceMode.DISABLED:
            return EvidenceResult(False, {"mode": "disabled"}, ["MSS disabled"], [])
        lookback = self.settings.strategy_mss_swing_lookback
        prior = candles[-lookback - 1 : -1]
        if not prior:
            return EvidenceResult(False, {}, ["not enough candles for MSS"], [])
        level = max(c.high_price for c in prior)
        candle = candles[-1]
        distance = (
            percent(candle.close_price - level, level)
            if candle.close_price > level
            else Decimal("0")
        )
        detected = candle.close_price > level and distance >= dec(
            self.settings.strategy_minimum_mss_break_percent
        )
        values = {
            "detected": detected,
            "broken_structure_level": level if detected else None,
            "break_distance": distance,
            "mss_timestamp": candle.close_time if detected else None,
            "confirmation_candle": candle.close_time if detected else None,
        }
        if detected:
            return EvidenceResult(True, values, ["bullish MSS confirmed"], [])
        return EvidenceResult(False, values, ["bullish MSS not detected"], [])


class StopLossCalculator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def calculate(
        self,
        entry: Decimal,
        pullback: EvidenceResult,
        sweep: EvidenceResult,
        atr_value: Decimal,
    ) -> EvidenceResult:
        swing_low = pullback.values.get("swing_low")
        swept_level = sweep.values.get("swept_level")
        reference = swept_level or swing_low
        if reference is None:
            return EvidenceResult(
                False,
                {},
                ["required structural reference is unavailable"],
                ["missing_stop_reference"],
            )
        buffer = atr_value * dec(self.settings.strategy_stop_loss_atr_buffer)
        stop = Decimal(reference) - buffer
        risk = entry - stop
        stop_percent = percent(risk, entry)
        values = {
            "stop_loss": stop,
            "structural_reference_level": reference,
            "atr_buffer": buffer,
            "stop_distance": risk,
            "stop_percentage": stop_percent,
            "method": "liquidity sweep low plus ATR buffer"
            if swept_level
            else "pullback swing low plus ATR buffer",
        }
        failed: list[str] = []
        reasons: list[str] = []
        if risk <= 0:
            failed.append("invalid_stop_distance")
            reasons.append("Stop distance is zero or negative")
        if stop >= entry:
            failed.append("stop_not_below_entry")
            reasons.append("Stop-loss is above or equal to entry")
        if stop_percent > dec(self.settings.strategy_maximum_stop_percent):
            failed.append("stop_too_large")
            reasons.append(f"Stop percentage {stop_percent} exceeds configured maximum")
        if stop_percent < dec(self.settings.strategy_minimum_stop_percent):
            failed.append("stop_too_small")
            reasons.append(f"Stop percentage {stop_percent} is below configured minimum")
        return EvidenceResult(
            not failed,
            values,
            ["structural stop-loss calculated"] if not failed else reasons,
            failed,
        )


class TakeProfitCalculator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def calculate(
        self, entry: Decimal, stop: Decimal, candles: list[OhlcvCandle]
    ) -> EvidenceResult:
        risk = entry - stop
        if risk <= 0:
            return EvidenceResult(False, {}, ["risk must be positive"], ["invalid_risk"])
        structural = max(c.high_price for c in candles[-self.settings.strategy_impulse_lookback :])
        fixed = entry + risk * dec(self.settings.strategy_minimum_reward_to_risk)
        target = structural if structural >= fixed else fixed
        reward = target - entry
        rr = safe_div(reward, risk)
        values = {
            "take_profit": target,
            "secondary_target": structural if structural > fixed else None,
            "expected_reward": reward,
            "reward_percentage": percent(reward, entry),
            "reward_to_risk": rr,
            "method": "nearest structural target"
            if structural >= fixed
            else "fixed minimum RR target",
            "structural_target_level": structural,
        }
        if rr < dec(self.settings.strategy_minimum_reward_to_risk):
            return EvidenceResult(
                False,
                values,
                [
                    "Nearest target provides RR "
                    f"{rr}, below minimum {self.settings.strategy_minimum_reward_to_risk}"
                ],
                ["rr_below_minimum"],
            )
        return EvidenceResult(True, values, ["take-profit target satisfies minimum RR"], [])


class TrendPullbackStrategyService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache = StrategyCache()
        self.repository = StrategySetupRepository()

    def list_strategies(self) -> list[dict[str, Any]]:
        return [
            {
                "name": STRATEGY_NAME,
                "version": self.settings.strategy_version,
                "enabled": self.settings.strategy_enabled,
                "trading_mode": self.settings.strategy_supported_trading_mode.value,
                "entry_timeframe": "1m",
                "confirmation_timeframe": "5m",
                "context_timeframe": "15m",
            }
        ]

    def evaluate_symbol(
        self,
        db: Session,
        symbol: str,
        refresh: bool = False,
        scanner_approved: bool = False,
    ) -> StrategyEvaluation:
        normalized = symbol.upper()
        if not self._is_symbol_supported(db, normalized):
            raise StrategyEvaluationError("unsupported symbol")
        if not scanner_approved and not self._latest_scanner_approved(db, normalized):
            raise StrategyEvaluationError(
                "scanner rejection: symbol is not a scanner-approved candidate"
            )
        regime = MarketRegimeService(self.settings).evaluate_symbol(db, normalized)
        candles_1m = self._load_candles(db, normalized, CandleTimeframe.ONE_MINUTE)
        candles_5m = self._load_candles(db, normalized, CandleTimeframe.FIVE_MINUTES)
        candles_15m = self._load_candles(
            db, normalized, CandleTimeframe.FIFTEEN_MINUTES, minimum=20
        )
        snapshot = self._latest_snapshot(db, normalized)
        latest_stamp = candles_1m[-1].close_time if candles_1m else datetime.min.replace(tzinfo=UTC)
        cache_key = (
            f"{normalized}:{self.settings.strategy_version}:{latest_stamp}:{regime.primary_regime}"
        )
        if not refresh:
            cached = self.cache.get(cache_key, self.settings.strategy_cache_ttl_seconds)
            if cached is not None:
                return cached
        result = self._evaluate(normalized, regime, candles_1m, candles_5m, candles_15m, snapshot)
        self.cache.set(cache_key, result)
        if self.settings.strategy_persistence_enabled:
            self.repository.upsert(db, result)
        return result

    def attach_to_scanner_candidates(
        self,
        db: Session,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for original in candidates:
            candidate = dict(original)
            if not candidate.get("final_tradeable", False):
                candidate["strategy_result"] = None
                candidate["eligible_for_signal"] = False
                enriched.append(candidate)
                continue
            result = self.evaluate_symbol(db, str(candidate["symbol"]), scanner_approved=True)
            candidate["strategy_result"] = result
            candidate["eligible_for_signal"] = result.eligible_for_signal
            enriched.append(candidate)
        return enriched

    def _evaluate(
        self,
        symbol: str,
        regime: RegimeEvaluation,
        candles_1m: list[OhlcvCandle],
        candles_5m: list[OhlcvCandle],
        candles_15m: list[OhlcvCandle],
        snapshot: MarketSnapshot | None,
    ) -> StrategyEvaluation:
        logger.info("strategy evaluation started", extra={"symbol": symbol})
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.settings.strategy_maximum_setup_age_seconds)
        reasons: list[str] = []
        failed: list[str] = []
        safety: list[str] = []
        current_price = candles_1m[-1].close_price if candles_1m else None
        state = StrategySetupState.NO_SETUP
        direction = StrategyDirection.NONE
        eligible = False

        base = self._base_payload(
            symbol, regime, now, expires_at, candles_1m, candles_5m, candles_15m
        )
        setup_id = self._setup_id(symbol, now, candles_1m)
        if not self.settings.strategy_enabled:
            return self._result(
                base,
                setup_id,
                state,
                direction,
                False,
                ["strategy disabled"],
                ["strategy_disabled"],
            )

        regime_block = self._regime_block(regime)
        if regime_block:
            direction = (
                StrategyDirection.SHORT
                if regime.entry_permission is EntryPermission.ALLOW_SHORT
                else StrategyDirection.NONE
            )
            return self._result(
                base,
                setup_id,
                StrategySetupState.BLOCKED_BY_REGIME,
                direction,
                False,
                regime_block,
                ["regime_block"],
            )

        if (
            len(candles_1m) < self.settings.strategy_minimum_candle_history
            or len(candles_5m) < self.settings.strategy_minimum_candle_history
        ):
            return self._result(
                base,
                setup_id,
                StrategySetupState.INSUFFICIENT_DATA,
                StrategyDirection.NONE,
                False,
                ["required 1m and 5m candle history is unavailable"],
                ["insufficient_candles"],
            )
        if not candles_15m:
            return self._result(
                base,
                setup_id,
                StrategySetupState.INSUFFICIENT_DATA,
                StrategyDirection.NONE,
                False,
                ["required 15m context candles are unavailable"],
                ["missing_15m_candles"],
            )
        continuity_failures = self._continuity_failures(candles_1m, 60) + self._continuity_failures(
            candles_5m, 300
        )
        stale = self._stale(candles_1m[-1], 120)
        if continuity_failures or stale:
            safety.extend(continuity_failures)
            if stale:
                safety.append("stale_market_data")
            return self._result(
                base,
                setup_id,
                StrategySetupState.INSUFFICIENT_DATA,
                StrategyDirection.NONE,
                False,
                ["market data is stale or discontinuous"],
                safety,
            )

        trend = self._trend_confirmation(candles_5m)
        base["five_minute_trend_summary"] = trend.values
        if not trend.detected:
            return self._result(
                base,
                setup_id,
                StrategySetupState.NO_SETUP,
                StrategyDirection.NONE,
                False,
                trend.reasons,
                trend.failed_conditions,
            )

        direction = StrategyDirection.LONG
        close_1m = [c.close_price for c in candles_1m]
        highs_1m = [c.high_price for c in candles_1m]
        lows_1m = [c.low_price for c in candles_1m]
        ema20_1m = ema(close_1m, self.settings.strategy_ema_fast_period)
        ema50_1m = ema(close_1m, self.settings.strategy_ema_mid_period)
        atr_1m = atr(highs_1m, lows_1m, close_1m) or Decimal("0")
        if ema20_1m is None or ema50_1m is None:
            return self._result(
                base,
                setup_id,
                StrategySetupState.INSUFFICIENT_DATA,
                direction,
                False,
                ["EMA inputs are unavailable"],
                ["missing_ema"],
            )
        base["ema_snapshot"].update({"1m_ema20": ema20_1m, "1m_ema50": ema50_1m, "1m_atr": atr_1m})

        pullback = PullbackDetector(self.settings).detect(candles_1m)
        base["pullback_detected"] = pullback.detected
        base["pullback_depth"] = pullback.values.get("depth")
        base["pullback_duration"] = pullback.values.get("duration")
        base["preceding_impulse_size"] = pullback.values.get("impulse")
        if not pullback.detected:
            return self._result(
                base,
                setup_id,
                StrategySetupState.NO_SETUP,
                direction,
                False,
                pullback.reasons,
                pullback.failed_conditions,
            )

        zone = EntryZoneCalculator(self.settings).calculate(candles_1m, ema20_1m, ema50_1m, atr_1m)
        base.update(
            entry_zone_lower=zone.lower,
            entry_zone_upper=zone.upper,
            preferred_entry=zone.preferred,
            distance_from_entry=zone.distance,
            entry_zone_position=zone.position,
            entry_zone_method=zone.method,
        )
        logger.info("entry zone calculated", extra={"symbol": symbol, "position": zone.position})
        if zone.position == "below":
            return self._result(
                base,
                setup_id,
                StrategySetupState.FORMING,
                direction,
                False,
                ["price is below the entry zone"],
                ["price_below_entry_zone"],
            )
        if zone.position == "above" and zone.distance and current_price:
            too_far = percent(zone.distance, current_price) > dec(
                self.settings.strategy_maximum_price_distance_after_zone_percent
            )
            if too_far:
                return self._result(
                    base,
                    setup_id,
                    StrategySetupState.EXPIRED,
                    direction,
                    False,
                    ["price moved too far above the entry zone"],
                    ["price_too_far_above_zone"],
                )

        rejection = RejectionConfirmationDetector(self.settings).detect(candles_1m[-1], ema20_1m)
        volume = VolumeConfirmationService(self.settings).confirm(candles_1m)
        sweep = LiquiditySweepDetector(self.settings).detect(candles_1m)
        mss = MarketStructureShiftDetector(self.settings).detect(candles_1m)
        base["rejection_confirmation"] = rejection.values
        base["volume_ratio"] = volume.values.get("current_volume_ratio")
        base["liquidity_sweep"] = sweep.values
        base["market_structure_shift"] = mss.values
        confirmation_failures = rejection.failed_conditions + volume.failed_conditions
        confirmation_reasons = rejection.reasons + volume.reasons
        if (
            self.settings.strategy_liquidity_sweep_mode is EvidenceMode.REQUIRED
            and not sweep.detected
        ):
            confirmation_failures.append("liquidity_sweep_required")
            confirmation_reasons.extend(sweep.reasons)
        if self.settings.strategy_mss_mode is EvidenceMode.REQUIRED and not mss.detected:
            confirmation_failures.append("mss_required")
            confirmation_reasons.extend(mss.reasons)
        if confirmation_failures:
            return self._result(
                base,
                setup_id,
                StrategySetupState.FORMING,
                direction,
                False,
                confirmation_reasons,
                confirmation_failures,
            )

        entry = zone.preferred
        if entry is None:
            return self._result(
                base,
                setup_id,
                StrategySetupState.NO_SETUP,
                direction,
                False,
                ["preferred entry is unavailable"],
                ["missing_entry"],
            )
        stop = StopLossCalculator(self.settings).calculate(entry, pullback, sweep, atr_1m)
        if not stop.detected:
            return self._result(
                base,
                setup_id,
                StrategySetupState.INVALIDATED,
                direction,
                False,
                stop.reasons,
                stop.failed_conditions,
            )
        stop_price = stop.values["stop_loss"]
        target = TakeProfitCalculator(self.settings).calculate(entry, stop_price, candles_1m)
        if not target.detected:
            return self._result(
                base,
                setup_id,
                StrategySetupState.FORMING,
                direction,
                False,
                target.reasons,
                target.failed_conditions,
            )

        risk = entry - stop_price
        reward = target.values["take_profit"] - entry
        rr = safe_div(reward, risk)
        base.update(
            stop_loss=stop_price,
            stop_calculation_method=stop.values["method"],
            take_profit=target.values["take_profit"],
            target_calculation_method=target.values["method"],
            risk_amount=risk,
            reward_amount=reward,
            reward_to_risk=rr,
        )
        if rr < dec(self.settings.strategy_minimum_reward_to_risk):
            return self._result(
                base,
                setup_id,
                StrategySetupState.FORMING,
                direction,
                False,
                ["reward-to-risk is below configured minimum"],
                ["rr_below_minimum"],
            )
        eligible = True
        state = StrategySetupState.READY
        reasons = ["Trend pullback continuation setup is ready for Phase 6 scoring"]
        logger.info("setup ready", extra={"symbol": symbol, "setup_id": setup_id})
        return self._result(base, setup_id, state, direction, eligible, reasons, failed)

    def _trend_confirmation(self, candles: list[OhlcvCandle]) -> EvidenceResult:
        closes = [c.close_price for c in candles]
        ema20 = ema(closes, self.settings.strategy_ema_fast_period)
        ema50 = ema(closes, self.settings.strategy_ema_mid_period)
        ema200 = ema(closes, self.settings.strategy_ema_slow_period)
        previous = ema(
            closes[: -self.settings.strategy_ema_slope_lookback],
            self.settings.strategy_ema_fast_period,
        )
        if ema20 is None or ema50 is None:
            return EvidenceResult(False, {}, ["5m EMA inputs are unavailable"], ["missing_5m_ema"])
        slope = percent(ema20 - previous, previous) if previous else Decimal("0")
        price = closes[-1]
        values = {
            "ema20": ema20,
            "ema50": ema50,
            "ema200": ema200,
            "ema20_above_ema50": ema20 > ema50,
            "ema50_above_ema200": ema200 is None or ema50 > ema200,
            "ema20_slope": slope,
            "price_above_ema50": price > ema50,
            "trend_strength": trend_strength_proxy(closes),
        }
        failures: list[str] = []
        reasons: list[str] = []
        if ema20 <= ema50:
            failures.append("ema20_not_above_ema50")
            reasons.append("5m EMA 20 is not above EMA 50")
        if ema200 is not None and ema50 <= ema200:
            failures.append("ema50_not_above_ema200")
            reasons.append("5m EMA 50 is not above EMA 200")
        if slope <= dec(self.settings.strategy_minimum_bullish_ema_slope):
            failures.append("weak_ema_slope")
            reasons.append("5m EMA 20 slope is below the configured bullish threshold")
        if price <= ema50:
            failures.append("price_below_ema50")
            reasons.append("5m price is not above EMA 50")
        return EvidenceResult(
            not failures,
            values,
            ["5m bullish trend confirmed"] if not failures else reasons,
            failures,
        )

    def _regime_block(self, regime: RegimeEvaluation) -> list[str]:
        if (
            regime.entry_permission is EntryPermission.ALLOW_SHORT
            or regime.primary_regime is MarketRegime.TRENDING_BEARISH
        ):
            return [
                "regime permits only short trades",
                "symbol is bearish",
                "current spot trading mode does not support short execution",
            ]
        if regime.market_wide_block:
            return ["BTC market-wide block is active"]
        if regime.entry_permission is EntryPermission.BLOCK_NEW_ENTRIES:
            return [f"regime permission blocks new entries: {regime.primary_regime.value}"]
        if regime.primary_regime is not MarketRegime.TRENDING_BULLISH:
            return [f"15m context is not TRENDING_BULLISH: {regime.primary_regime.value}"]
        return []

    def _base_payload(
        self,
        symbol: str,
        regime: RegimeEvaluation,
        now: datetime,
        expires_at: datetime,
        candles_1m: list[OhlcvCandle],
        candles_5m: list[OhlcvCandle],
        candles_15m: list[OhlcvCandle],
    ) -> dict[str, Any]:
        current = candles_1m[-1].close_price if candles_1m else None
        return {
            "symbol": symbol,
            "strategy_name": STRATEGY_NAME,
            "strategy_version": self.settings.strategy_version,
            "evaluated_at": now,
            "setup_created_at": now,
            "setup_expires_at": expires_at,
            "regime": regime.primary_regime,
            "regime_permission": regime.entry_permission,
            "btc_regime": regime.btc_regime,
            "market_wide_block": regime.market_wide_block,
            "one_minute_trend_summary": {"candles": len(candles_1m)},
            "five_minute_trend_summary": {"candles": len(candles_5m)},
            "fifteen_minute_context_summary": {
                "candles": len(candles_15m),
                "source": "market_regime_service",
                "regime": regime.primary_regime.value,
            },
            "ema_snapshot": dict(regime.indicator_snapshot),
            "pullback_detected": False,
            "pullback_depth": None,
            "pullback_duration": None,
            "preceding_impulse_size": None,
            "entry_zone_lower": None,
            "entry_zone_upper": None,
            "preferred_entry": None,
            "current_price": current,
            "distance_from_entry": None,
            "entry_zone_position": "unknown",
            "entry_zone_method": "not_calculated",
            "volume_ratio": None,
            "rejection_confirmation": {},
            "liquidity_sweep": {},
            "market_structure_shift": {},
            "stop_loss": None,
            "stop_calculation_method": None,
            "take_profit": None,
            "target_calculation_method": None,
            "risk_amount": None,
            "reward_amount": None,
            "reward_to_risk": None,
            "setup_age_seconds": 0,
            "data_freshness": {
                "latest_1m_close": candles_1m[-1].close_time if candles_1m else None,
                "latest_5m_close": candles_5m[-1].close_time if candles_5m else None,
                "latest_15m_close": candles_15m[-1].close_time if candles_15m else None,
                "regime_data_fresh": regime.data_fresh,
            },
            "triggered_safety_conditions": list(regime.safety_conditions),
            "indicator_snapshot": dict(regime.indicator_snapshot),
        }

    def _result(
        self,
        base: dict[str, Any],
        setup_id: str,
        state: StrategySetupState,
        direction: StrategyDirection,
        eligible: bool,
        reasons: list[str],
        failed: list[str],
    ) -> StrategyEvaluation:
        payload = dict(base)
        payload.update(
            setup_id=setup_id,
            direction=direction,
            setup_state=state,
            eligible_for_signal=eligible and state is StrategySetupState.READY,
            reasons=reasons,
            failed_conditions=failed,
        )
        result = StrategyEvaluation(**payload)
        logger.info(
            "strategy evaluation completed",
            extra={"symbol": result.symbol, "state": result.setup_state.value},
        )
        return result

    def _setup_id(self, symbol: str, now: datetime, candles: list[OhlcvCandle]) -> str:
        stamp = candles[-1].close_time.isoformat() if candles else now.isoformat()
        raw = f"{symbol}:{STRATEGY_NAME}:{self.settings.strategy_version}:{stamp}:LONG"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _load_candles(
        self,
        db: Session,
        symbol: str,
        timeframe: CandleTimeframe,
        minimum: int | None = None,
    ) -> list[OhlcvCandle]:
        limit = max(minimum or self.settings.strategy_minimum_candle_history, 220)
        rows = list(
            db.scalars(
                select(OhlcvCandle)
                .where(OhlcvCandle.symbol == symbol, OhlcvCandle.timeframe == timeframe)
                .order_by(OhlcvCandle.open_time.desc())
                .limit(limit)
            )
        )
        rows.reverse()
        return rows

    def _latest_snapshot(self, db: Session, symbol: str) -> MarketSnapshot | None:
        return db.scalars(
            select(MarketSnapshot)
            .where(MarketSnapshot.symbol == symbol)
            .order_by(MarketSnapshot.snapshot_at.desc())
            .limit(1)
        ).first()

    def _is_symbol_supported(self, db: Session, symbol: str) -> bool:
        return (
            db.scalar(select(ExchangeSymbol.id).where(ExchangeSymbol.symbol == symbol)) is not None
        )

    def _latest_scanner_approved(self, db: Session, symbol: str) -> bool:
        row = db.scalars(
            select(ScannerDecision)
            .where(ScannerDecision.symbol == symbol)
            .order_by(ScannerDecision.created_at.desc())
            .limit(1)
        ).first()
        return bool(row and row.decision == ScannerDecisionType.SIGNAL_CANDIDATE)

    def _continuity_failures(self, candles: list[OhlcvCandle], seconds: int) -> list[str]:
        failures: list[str] = []
        for previous, current in zip(candles[-20:-1], candles[-19:], strict=True):
            gap = (current.open_time - previous.open_time).total_seconds()
            if gap != seconds:
                failures.append("missing_candle")
                break
        return failures

    def _stale(self, candle: OhlcvCandle, max_age_seconds: int) -> bool:
        return (datetime.now(UTC) - candle.close_time).total_seconds() > max_age_seconds


def dec(value: float | int | str | Decimal) -> Decimal:
    return Decimal(str(value))


def percent(numerator: Decimal, denominator: Decimal) -> Decimal:
    value = safe_div(numerator, denominator) * Decimal("100")
    return value.quantize(Decimal("0.00000001"))


def safe_div(numerator: Decimal, denominator: Decimal) -> Decimal:
    try:
        if denominator == 0:
            return Decimal("0")
        value = numerator / denominator
    except (DivisionByZero, InvalidOperation):
        return Decimal("0")
    if not value.is_finite():
        return Decimal("0")
    return value.quantize(Decimal("0.00000001"))


def evaluation_to_dict(result: StrategyEvaluation) -> dict[str, Any]:
    return asdict(result)
