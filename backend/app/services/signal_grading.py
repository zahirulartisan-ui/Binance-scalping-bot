from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.core.settings import Settings
from app.models.enums import SignalGrade, StrategySetupState

if TYPE_CHECKING:
    from app.services.trend_pullback_strategy import StrategyEvaluation


@dataclass(frozen=True)
class SignalGradeResult:
    grade: SignalGrade | None
    score: int | None
    reasons: list[str]
    factors: dict[str, Any]


class SignalGradingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def grade(self, evaluation: StrategyEvaluation) -> SignalGradeResult:
        if (
            evaluation.setup_state is not StrategySetupState.READY
            or not evaluation.eligible_for_signal
        ):
            return SignalGradeResult(
                grade=None,
                score=None,
                reasons=["setup is not eligible for Batch 6 signal grading"],
                factors={},
            )

        rr = evaluation.reward_to_risk or Decimal("0")
        volume_ratio = evaluation.volume_ratio or Decimal("0")
        trend_slope = dec(evaluation.five_minute_trend_summary.get("ema20_slope") or 0)
        trend_strength = dec(evaluation.five_minute_trend_summary.get("trend_strength") or 0)
        body_ratio = dec(evaluation.rejection_confirmation.get("body_ratio") or 0)
        wick_ratio = dec(evaluation.rejection_confirmation.get("lower_wick_ratio") or 0)

        score_breakdown = {
            "reward_to_risk": self._score_reward_to_risk(rr),
            "volume_confirmation": self._score_volume(volume_ratio),
            "pullback_quality": self._score_pullback_depth(evaluation.pullback_depth),
            "trend_alignment": self._score_trend(trend_slope, trend_strength),
            "rejection_quality": self._score_rejection(body_ratio, wick_ratio),
            "confluence": self._score_confluence(
                bool(evaluation.liquidity_sweep.get("detected")),
                bool(evaluation.market_structure_shift.get("detected")),
            ),
        }
        total = sum(score_breakdown.values())
        grade = self._grade_for_score(total)
        reasons = self._reasons(evaluation, grade, rr, volume_ratio)
        factors = {
            "score_breakdown": score_breakdown,
            "reward_to_risk": str(rr),
            "volume_ratio": str(volume_ratio),
            "pullback_depth": str(evaluation.pullback_depth) if evaluation.pullback_depth else None,
            "trend_slope": str(trend_slope),
            "trend_strength": str(trend_strength),
            "rejection_body_ratio": str(body_ratio),
            "rejection_wick_ratio": str(wick_ratio),
            "liquidity_sweep_detected": bool(evaluation.liquidity_sweep.get("detected")),
            "mss_detected": bool(evaluation.market_structure_shift.get("detected")),
            "grade_thresholds": {
                "A": self.settings.strategy_signal_grade_a_min,
                "B": self.settings.strategy_signal_grade_b_min,
                "C": self.settings.strategy_signal_grade_c_min,
            },
        }
        return SignalGradeResult(grade=grade, score=total, reasons=reasons, factors=factors)

    def _score_reward_to_risk(self, rr: Decimal) -> int:
        if rr >= Decimal("2.50"):
            return 30
        if rr >= Decimal("2.00"):
            return 26
        if rr >= Decimal("1.75"):
            return 22
        return 18

    def _score_volume(self, ratio: Decimal) -> int:
        if ratio >= Decimal("1.80"):
            return 20
        if ratio >= Decimal("1.50"):
            return 17
        if ratio >= Decimal("1.30"):
            return 14
        return 10

    def _score_pullback_depth(self, depth: Decimal | None) -> int:
        if depth is None:
            return 0
        if Decimal("0.20") <= depth <= Decimal("0.80"):
            return 15
        if Decimal("0.10") <= depth <= Decimal("1.20"):
            return 11
        return 7

    def _score_trend(self, slope: Decimal, strength: Decimal) -> int:
        if slope >= Decimal("0.05000000") and strength >= Decimal("30"):
            return 15
        if slope >= Decimal("0.02000000") and strength >= Decimal("20"):
            return 12
        if slope > Decimal("0") and strength >= Decimal("10"):
            return 9
        return 6

    def _score_rejection(self, body_ratio: Decimal, wick_ratio: Decimal) -> int:
        if body_ratio >= Decimal("0.60") and wick_ratio >= Decimal("0.30"):
            return 10
        if body_ratio >= Decimal("0.45") and wick_ratio >= Decimal("0.20"):
            return 8
        return 6

    def _score_confluence(self, liquidity_sweep: bool, mss: bool) -> int:
        if liquidity_sweep and mss:
            return 10
        if liquidity_sweep or mss:
            return 7
        return 4

    def _grade_for_score(self, score: int) -> SignalGrade:
        if score >= self.settings.strategy_signal_grade_a_min:
            return SignalGrade.A
        if score >= self.settings.strategy_signal_grade_b_min:
            return SignalGrade.B
        return SignalGrade.C

    def _reasons(
        self,
        evaluation: StrategyEvaluation,
        grade: SignalGrade,
        reward_to_risk: Decimal,
        volume_ratio: Decimal,
    ) -> list[str]:
        reasons = [
            f"Batch 6 grade {grade.value} assigned from deterministic setup evidence",
            "Reward-to-risk measured "
            f"{reward_to_risk} and recovery volume ratio measured {volume_ratio}",
        ]
        if evaluation.liquidity_sweep.get("detected"):
            reasons.append("Liquidity sweep confluence improved the setup grade")
        if evaluation.market_structure_shift.get("detected"):
            reasons.append("Market structure shift confirmation improved the setup grade")
        return reasons


def dec(value: float | int | str | Decimal) -> Decimal:
    return Decimal(str(value))
