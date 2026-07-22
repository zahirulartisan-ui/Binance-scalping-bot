from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import (
    EntryPermission,
    ScannerDecisionType,
    ScannerRunStatus,
    StrategySetupState,
)
from app.models.market_data import ExchangeSymbol
from app.models.trading import ScannerDecision, ScannerRun
from app.services.market_regime_service import MarketRegimeService
from app.services.trend_pullback_strategy import (
    StrategyEvaluationError,
    TrendPullbackStrategyService,
)


@dataclass(frozen=True)
class ScannerDecisionRecord:
    symbol: str
    decision: ScannerDecisionType
    reason_code: str
    metadata_json: dict[str, Any]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


class ScannerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.regime_service = MarketRegimeService(settings)
        self.strategy_service = TrendPullbackStrategyService(settings)

    def run_scan(self, db: Session, limit: int = 100) -> ScannerRun:
        run = ScannerRun(
            status=ScannerRunStatus.STARTED,
            idempotency_key=f"scanner-{uuid.uuid4().hex}",
            metadata_json={},
        )
        db.add(run)
        db.flush()

        symbols = list(
            db.scalars(
                select(ExchangeSymbol.symbol)
                .where(ExchangeSymbol.trading_status == "TRADING")
                .order_by(ExchangeSymbol.symbol)
                .limit(limit)
            )
        )

        decisions: list[ScannerDecisionRecord] = []
        for symbol in symbols:
            decisions.append(self._scan_symbol(db, symbol))

        counts = {
            "symbols_scanned": len(decisions),
            "signal_candidates": sum(
                1 for item in decisions if item.decision is ScannerDecisionType.SIGNAL_CANDIDATE
            ),
            "watch_candidates": sum(
                1 for item in decisions if item.decision is ScannerDecisionType.WATCH
            ),
            "ignored_candidates": sum(
                1 for item in decisions if item.decision is ScannerDecisionType.IGNORE
            ),
        }

        for item in decisions:
            db.add(
                ScannerDecision(
                    scanner_run_id=run.id,
                    symbol=item.symbol,
                    decision=item.decision,
                    reason_code=item.reason_code,
                    metadata_json=item.metadata_json,
                )
            )

        run.status = ScannerRunStatus.COMPLETED
        run.finished_at = datetime.now(UTC)
        run.metadata_json = {
            **counts,
            "symbols": symbols,
        }
        db.flush()
        return run

    def latest_status(self, db: Session) -> ScannerRun | None:
        statement = select(ScannerRun).order_by(ScannerRun.started_at.desc()).limit(1)
        return db.scalars(statement).first()

    def list_runs(self, db: Session, limit: int = 20) -> list[ScannerRun]:
        statement = select(ScannerRun).order_by(ScannerRun.started_at.desc()).limit(limit)
        return list(db.scalars(statement))

    def get_run(self, db: Session, run_id: uuid.UUID) -> ScannerRun | None:
        return db.scalar(select(ScannerRun).where(ScannerRun.id == run_id))

    def list_decisions(
        self,
        db: Session,
        run_id: uuid.UUID,
        decision: ScannerDecisionType | None = None,
        limit: int = 100,
    ) -> list[ScannerDecision]:
        statement = (
            select(ScannerDecision)
            .where(ScannerDecision.scanner_run_id == run_id)
            .order_by(ScannerDecision.symbol)
            .limit(limit)
        )
        if decision is not None:
            statement = statement.where(ScannerDecision.decision == decision)
        return list(db.scalars(statement))

    def _scan_symbol(self, db: Session, symbol: str) -> ScannerDecisionRecord:
        try:
            regime = self.regime_service.evaluate_symbol(db, symbol)
        except Exception as exc:
            return ScannerDecisionRecord(
                symbol=symbol,
                decision=ScannerDecisionType.IGNORE,
                reason_code="regime_unavailable",
                metadata_json={"reasons": [str(exc)]},
            )

        if regime.entry_permission is EntryPermission.BLOCK_NEW_ENTRIES or regime.market_wide_block:
            return ScannerDecisionRecord(
                symbol=symbol,
                decision=ScannerDecisionType.IGNORE,
                reason_code="regime_blocked",
                metadata_json={
                    "regime": regime.primary_regime.value,
                    "entry_permission": regime.entry_permission.value,
                    "reasons": regime.reasons,
                    "market_wide_block": regime.market_wide_block,
                },
            )

        try:
            result = self.strategy_service.evaluate_symbol(
                db,
                symbol,
                refresh=True,
                scanner_approved=True,
            )
        except StrategyEvaluationError as exc:
            return ScannerDecisionRecord(
                symbol=symbol,
                decision=ScannerDecisionType.IGNORE,
                reason_code="strategy_unavailable",
                metadata_json={
                    "regime": regime.primary_regime.value,
                    "entry_permission": regime.entry_permission.value,
                    "reasons": [str(exc)],
                },
            )

        decision = self._decision_for_result(result.setup_state, result.eligible_for_signal)
        reason_code = self._reason_for_result(result.setup_state, result.eligible_for_signal)
        return ScannerDecisionRecord(
            symbol=symbol,
            decision=decision,
            reason_code=reason_code,
            metadata_json=_json_safe(
                {
                    "setup_id": result.setup_id,
                    "strategy_name": result.strategy_name,
                    "strategy_version": result.strategy_version,
                    "regime": regime.primary_regime.value,
                    "entry_permission": regime.entry_permission.value,
                    "setup_state": result.setup_state.value,
                    "eligible_for_signal": result.eligible_for_signal,
                    "signal_grade": result.signal_grade.value if result.signal_grade else None,
                    "signal_score": result.signal_score,
                    "preferred_entry": result.preferred_entry,
                    "stop_loss": result.stop_loss,
                    "take_profit": result.take_profit,
                    "risk_amount": result.risk_amount,
                    "reward_to_risk": result.reward_to_risk,
                    "expires_at": result.setup_expires_at,
                    "reasons": result.reasons,
                    "failed_conditions": result.failed_conditions,
                }
            ),
        )

    def _decision_for_result(
        self, setup_state: StrategySetupState, eligible_for_signal: bool
    ) -> ScannerDecisionType:
        if setup_state is StrategySetupState.READY and eligible_for_signal:
            return ScannerDecisionType.SIGNAL_CANDIDATE
        if setup_state in {
            StrategySetupState.READY,
            StrategySetupState.FORMING,
            StrategySetupState.NO_SETUP,
        }:
            return ScannerDecisionType.WATCH
        return ScannerDecisionType.IGNORE

    def _reason_for_result(
        self, setup_state: StrategySetupState, eligible_for_signal: bool
    ) -> str:
        if setup_state is StrategySetupState.READY and eligible_for_signal:
            return "strategy_ready"
        if setup_state is StrategySetupState.READY:
            return "ready_but_not_eligible"
        if setup_state is StrategySetupState.FORMING:
            return "setup_forming"
        if setup_state is StrategySetupState.NO_SETUP:
            return "setup_not_ready"
        if setup_state is StrategySetupState.INSUFFICIENT_DATA:
            return "insufficient_data"
        if setup_state is StrategySetupState.EXPIRED:
            return "setup_expired"
        if setup_state is StrategySetupState.INVALIDATED:
            return "setup_invalidated"
        return "blocked_by_regime"
