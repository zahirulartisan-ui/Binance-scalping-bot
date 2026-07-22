from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import RiskDecisionStatus, SignalStatus
from app.models.trading import AppSetting, RiskDecision, Signal, SystemEvent
from app.services.execution_service import ExecutionConflictError, ExecutionResult
from app.services.signal_automation_service import SignalAutomationService


@dataclass(frozen=True)
class FakeScannerRun:
    id: uuid.UUID
    metadata_json: dict[str, int]


class FakeScannerService:
    def __init__(self) -> None:
        self.calls = 0

    def run_scan(self, db: Session, limit: int = 100) -> FakeScannerRun:
        self.calls += 1
        return FakeScannerRun(uuid.uuid4(), {"symbols_scanned": limit})


class FakeSignalsService:
    def __init__(self, signals: list[Signal]) -> None:
        self.signals = signals

    def promote_from_run(self, db: Session, run: FakeScannerRun, limit: int = 100) -> SimpleNamespace:
        return SimpleNamespace(
            promoted_count=len(self.signals),
            reused_count=0,
            signals=self.signals,
        )


class FakeExecutionService:
    def __init__(self, reused_ids: set[uuid.UUID] | None = None, blocked_ids: set[uuid.UUID] | None = None) -> None:
        self.reused_ids = reused_ids or set()
        self.blocked_ids = blocked_ids or set()
        self.calls: list[uuid.UUID] = []

    def execute_signal(self, db: Session, signal_id: uuid.UUID) -> ExecutionResult:
        self.calls.append(signal_id)
        signal = db.scalar(select(Signal).where(Signal.id == signal_id))
        if signal is None:
            raise ExecutionConflictError("missing_signal")
        if signal_id in self.blocked_ids:
            raise ExecutionConflictError("execution_disabled")
        decision = RiskDecision(
            signal_id=signal.id,
            status=RiskDecisionStatus.APPROVED,
            risk_per_trade=Decimal("0.01"),
            daily_loss_limit=Decimal("0.03"),
            max_open_trades=3,
            reason_code="execution_approved",
            idempotency_key=f"risk-{signal_id}",
            metadata_json={},
        )
        return ExecutionResult(
            signal=signal,
            risk_decision=decision,
            order=None,  # type: ignore[arg-type]
            position=None,  # type: ignore[arg-type]
            reused=signal_id in self.reused_ids,
        )


def _settings() -> Settings:
    return Settings(app_env="test", database_url="sqlite+pysqlite:///:memory:")


def _create_signal(db_session: Session, symbol: str = "BTCUSDT", status: SignalStatus = SignalStatus.NEW) -> Signal:
    signal = Signal(
        symbol=symbol,
        status=status,
        side="buy",
        entry_price="100",
        stop_loss_price="95",
        take_profit_price="110",
        risk_amount="5",
        idempotency_key=f"signal-{symbol}-{uuid.uuid4()}",
        metadata_json={},
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    return signal


def test_signal_automation_service_respects_runtime_disable_flag(db_session: Session) -> None:
    service = SignalAutomationService(
        _settings(),
        scanner_service=FakeScannerService(),
        signals_service=FakeSignalsService([]),
        execution_service=FakeExecutionService(),
    )

    result = service.run_cycle(db_session)

    assert result.automation_enabled is False
    assert result.reasons == ["automation_disabled"]
    assert db_session.scalars(select(SystemEvent)).first() is None


def test_signal_automation_service_scans_promotes_and_executes(db_session: Session) -> None:
    db_session.add(
        AppSetting(
            key="signal_execution_automation_enabled",
            value={"value": True},
            value_type="boolean",
            description="test",
        )
    )
    db_session.add(
        AppSetting(
            key="signal_execution_batch_size",
            value={"value": 2},
            value_type="integer",
            description="test",
        )
    )
    db_session.commit()
    first = _create_signal(db_session, "BTCUSDT")
    second = _create_signal(db_session, "ETHUSDT")
    scanner = FakeScannerService()
    execution = FakeExecutionService(reused_ids={second.id})
    service = SignalAutomationService(
        _settings(),
        scanner_service=scanner,
        signals_service=FakeSignalsService([first, second]),
        execution_service=execution,
    )

    result = service.run_cycle(db_session)

    assert result.automation_enabled is True
    assert result.symbols_scanned == 2
    assert result.promoted_count == 2
    assert result.executed_count == 1
    assert result.reused_execution_count == 1
    assert result.blocked_count == 0
    assert execution.calls == [first.id, second.id]
    event = db_session.scalars(select(SystemEvent).where(SystemEvent.source == "signal_automation_service")).first()
    assert event is not None
    assert event.metadata_json["executed_count"] == 1


def test_signal_automation_service_tracks_blocked_execution(db_session: Session) -> None:
    db_session.add(
        AppSetting(
            key="signal_execution_automation_enabled",
            value={"value": True},
            value_type="boolean",
            description="test",
        )
    )
    db_session.commit()
    signal = _create_signal(db_session)
    execution = FakeExecutionService(blocked_ids={signal.id})
    service = SignalAutomationService(
        _settings(),
        scanner_service=FakeScannerService(),
        signals_service=FakeSignalsService([signal]),
        execution_service=execution,
    )

    result = service.run_cycle(db_session)

    assert result.blocked_count == 1
    assert result.reasons == [f"{signal.symbol}:execution_disabled"]
