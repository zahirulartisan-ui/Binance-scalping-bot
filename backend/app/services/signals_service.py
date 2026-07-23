from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import OrderSide, ScannerDecisionType, SignalStatus
from app.models.trading import ScannerDecision, ScannerRun, Signal
from app.services.scanner_service import ScannerService


@dataclass(frozen=True)
class SignalPromotionResult:
    promoted_count: int
    reused_count: int
    signals: list[Signal]


class SignalsService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.scanner_service = ScannerService(settings)

    def promote_latest(
        self,
        db: Session,
        limit: int = 100,
        refresh_scanner: bool = False,
    ) -> SignalPromotionResult:
        latest = self.scanner_service.latest_status(db)
        if latest is None or refresh_scanner:
            latest = self.scanner_service.run_scan(db, limit)
        return self.promote_from_run(db, latest, limit)

    def promote_from_run(
        self,
        db: Session,
        run: ScannerRun,
        limit: int = 100,
    ) -> SignalPromotionResult:
        rows = self.scanner_service.list_decisions(
            db,
            run.id,
            ScannerDecisionType.SIGNAL_CANDIDATE,
            limit,
        )
        promoted: list[Signal] = []
        promoted_count = 0
        reused_count = 0
        for row in rows:
            signal, created = self._promote_decision(db, row)
            promoted.append(signal)
            if created:
                promoted_count += 1
            else:
                reused_count += 1
        return SignalPromotionResult(promoted_count, reused_count, promoted)

    def list_signals(
        self,
        db: Session,
        status: SignalStatus | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[Signal]:
        self._expire_stale(db)
        statement = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
        if status is not None:
            statement = statement.where(Signal.status == status)
        if symbol is not None:
            statement = statement.where(Signal.symbol == symbol)
        return list(db.scalars(statement))

    def get_signal(self, db: Session, signal_id: uuid.UUID) -> Signal | None:
        self._expire_stale(db)
        return db.scalar(select(Signal).where(Signal.id == signal_id))

    def _promote_decision(self, db: Session, row: ScannerDecision) -> tuple[Signal, bool]:
        existing = db.scalar(select(Signal).where(Signal.scanner_decision_id == row.id).limit(1))
        if existing is not None:
            return existing, False

        metadata = row.metadata_json or {}
        entry_price = Decimal(str(metadata.get("preferred_entry") or "0"))
        stop_loss = self._decimal_or_none(metadata.get("stop_loss"))
        take_profit = self._decimal_or_none(metadata.get("take_profit"))
        risk_amount = self._decimal_or_none(metadata.get("risk_amount")) or Decimal("0")
        expires_at = self._datetime_or_none(metadata.get("expires_at"))

        signal = Signal(
            scanner_decision_id=row.id,
            symbol=row.symbol,
            status=SignalStatus.NEW,
            side=OrderSide.BUY,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            risk_amount=risk_amount,
            expires_at=expires_at,
            idempotency_key=f"signal-{row.id}",
            metadata_json={
                "scanner_run_id": str(row.scanner_run_id),
                "setup_id": metadata.get("setup_id"),
                "setup_state": metadata.get("setup_state"),
                "strategy_name": metadata.get("strategy_name"),
                "strategy_version": metadata.get("strategy_version"),
                "signal_grade": metadata.get("signal_grade"),
                "signal_score": metadata.get("signal_score"),
                "reason_code": row.reason_code,
                "reasons": list(metadata.get("reasons", [])),
                "failed_conditions": list(metadata.get("failed_conditions", [])),
                "regime": metadata.get("regime"),
                "entry_permission": metadata.get("entry_permission"),
                "reward_to_risk": metadata.get("reward_to_risk"),
            },
        )
        db.add(signal)
        db.flush()
        return signal, True

    def _expire_stale(self, db: Session) -> None:
        now = datetime.now(UTC)
        rows = list(
            db.scalars(
                select(Signal).where(
                    Signal.status.in_([SignalStatus.NEW, SignalStatus.ACCEPTED]),
                    Signal.expires_at.is_not(None),
                )
            )
        )
        changed = False
        for row in rows:
            if row.expires_at is not None and row.expires_at <= now:
                row.status = SignalStatus.EXPIRED
                changed = True
        if changed:
            db.flush()

    def _decimal_or_none(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))

    def _datetime_or_none(self, value: Any) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(str(value))
