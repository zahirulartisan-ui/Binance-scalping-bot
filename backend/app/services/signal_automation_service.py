from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import SignalStatus, SystemEventLevel
from app.models.trading import Signal, SystemEvent
from app.services.execution_service import (
    ExecutionConflictError,
    ExecutionService,
    SignalExecutionNotFoundError,
)
from app.services.scanner_service import ScannerService
from app.services.settings_service import get_public_settings
from app.services.signals_service import SignalsService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SignalAutomationResult:
    scanner_run_id: str | None
    symbols_scanned: int
    promoted_count: int
    reused_count: int
    executed_count: int
    reused_execution_count: int
    blocked_count: int
    signal_ids: list[str]
    reasons: list[str]
    automation_enabled: bool


class SignalAutomationService:
    def __init__(
        self,
        settings: Settings,
        scanner_service: ScannerService | None = None,
        signals_service: SignalsService | None = None,
        execution_service: ExecutionService | None = None,
    ) -> None:
        self.settings = settings
        self.scanner_service = scanner_service or ScannerService(settings)
        self.signals_service = signals_service or SignalsService(settings)
        self.execution_service = execution_service or ExecutionService(settings)

    def run_cycle(self, db: Session) -> SignalAutomationResult:
        runtime = get_public_settings(db, self.settings)
        if not bool(runtime["signal_execution_automation_enabled"]):
            return SignalAutomationResult(
                scanner_run_id=None,
                symbols_scanned=0,
                promoted_count=0,
                reused_count=0,
                executed_count=0,
                reused_execution_count=0,
                blocked_count=0,
                signal_ids=[],
                reasons=["automation_disabled"],
                automation_enabled=False,
            )

        limit = int(runtime["signal_execution_batch_size"])
        scanner_run = self.scanner_service.run_scan(db, limit)
        promotion = self.signals_service.promote_from_run(db, scanner_run, limit)

        executed_count = 0
        reused_execution_count = 0
        blocked_count = 0
        reasons: list[str] = []
        automated_signals = self._eligible_signals(promotion.signals)

        for signal in automated_signals:
            try:
                result = self.execution_service.execute_signal(db, signal.id)
                if result.reused:
                    reused_execution_count += 1
                else:
                    executed_count += 1
            except (ExecutionConflictError, SignalExecutionNotFoundError) as exc:
                blocked_count += 1
                reasons.append(f"{signal.symbol}:{exc}")

        summary = SignalAutomationResult(
            scanner_run_id=str(scanner_run.id),
            symbols_scanned=int((scanner_run.metadata_json or {}).get("symbols_scanned", 0)),
            promoted_count=promotion.promoted_count,
            reused_count=promotion.reused_count,
            executed_count=executed_count,
            reused_execution_count=reused_execution_count,
            blocked_count=blocked_count,
            signal_ids=[str(signal.id) for signal in automated_signals],
            reasons=reasons,
            automation_enabled=True,
        )
        self._record_system_event(db, summary)
        return summary

    def _eligible_signals(self, signals: Sequence[Signal]) -> list[Signal]:
        return [
            signal
            for signal in signals
            if signal.status in {SignalStatus.NEW, SignalStatus.ACCEPTED}
        ]

    def _record_system_event(self, db: Session, summary: SignalAutomationResult) -> None:
        level = (
            SystemEventLevel.WARNING
            if summary.blocked_count > 0
            else SystemEventLevel.INFO
        )
        db.add(
            SystemEvent(
                level=level,
                source="signal_automation_service",
                message=(
                    f"Signal automation scanned {summary.symbols_scanned} symbols, "
                    f"promoted {summary.promoted_count}, "
                    f"and executed {summary.executed_count} signals."
                ),
                idempotency_key=f"signal-automation-{uuid.uuid4()}",
                event_at=datetime.now(UTC),
                metadata_json={
                    "scanner_run_id": summary.scanner_run_id,
                    "symbols_scanned": summary.symbols_scanned,
                    "promoted_count": summary.promoted_count,
                    "reused_count": summary.reused_count,
                    "executed_count": summary.executed_count,
                    "reused_execution_count": summary.reused_execution_count,
                    "blocked_count": summary.blocked_count,
                    "signal_ids": summary.signal_ids,
                    "reasons": summary.reasons,
                },
            )
        )
        db.flush()
