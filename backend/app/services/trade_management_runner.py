from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import PositionStatus, SystemEventLevel
from app.models.market_data import MarketSnapshot
from app.models.trading import Position, SystemEvent
from app.services.binance_client import BinanceMarketDataClient
from app.services.binance_trading_client import BinanceTradingClient
from app.services.execution_service import ExecutionService
from app.services.settings_service import get_public_settings

logger = logging.getLogger(__name__)


class TradeManagementRunner:
    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session],
        client: BinanceMarketDataClient,
        trading_client: BinanceTradingClient | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.client = client
        self.trading_client = trading_client
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._cycle_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="trade-management-runner",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout_seconds: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout_seconds)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("trade management cycle failed")
            self._stop_event.wait(self.settings.position_monitoring_interval_seconds)

    def run_once(self) -> bool:
        if not self._cycle_lock.acquire(blocking=False):
            return False
        try:
            with self.session_factory() as db:
                self._run_cycle(db)
                db.commit()
            return True
        except Exception:
            logger.exception("trade management cycle failed")
            return False
        finally:
            self._cycle_lock.release()

    def _run_cycle(self, db: Session) -> None:
        runtime = get_public_settings(db, self.settings)
        if not bool(runtime["position_monitoring_enabled"]):
            return

        rows = list(db.scalars(select(Position).where(Position.status == PositionStatus.OPEN)))
        symbols = sorted({row.symbol for row in rows if self._is_demo_position(row)})
        if not symbols:
            return

        price_max_age_seconds = int(runtime["position_monitoring_price_max_age_seconds"])
        prices: dict[str, Decimal] = {}
        used_snapshots: list[str] = []
        fallback_quotes: list[str] = []
        unavailable_symbols: list[str] = []

        for symbol in symbols:
            snapshot = self._latest_snapshot(db, symbol)
            if snapshot is not None and self._is_snapshot_fresh(snapshot, price_max_age_seconds):
                prices[symbol] = snapshot.last_price
                used_snapshots.append(symbol)
                continue
            try:
                payload = self.client.recent_price(symbol)
                prices[symbol] = Decimal(str(payload["price"]))
                fallback_quotes.append(symbol)
            except Exception:
                unavailable_symbols.append(symbol)

        result = ExecutionService(
            self.settings,
            trading_client=self.trading_client,
        ).run_monitor(
            db,
            prices=prices,
            note="continuous_monitor",
        )

        if result.actions or fallback_quotes or unavailable_symbols:
            db.add(
                SystemEvent(
                    level=(
                        SystemEventLevel.WARNING if unavailable_symbols else SystemEventLevel.INFO
                    ),
                    source="trade_management_runner",
                    message=(
                        f"Trade management cycle processed {len(result.actions)} actions across "
                        f"{len(symbols)} symbols."
                    ),
                    idempotency_key=f"trade-monitor-{uuid.uuid4()}",
                    event_at=datetime.now(UTC),
                    metadata_json={
                        "action_count": len(result.actions),
                        "used_snapshots": used_snapshots,
                        "fallback_quotes": fallback_quotes,
                        "unavailable_symbols": unavailable_symbols,
                    },
                )
            )

    def _latest_snapshot(self, db: Session, symbol: str) -> MarketSnapshot | None:
        return db.scalar(
            select(MarketSnapshot)
            .where(MarketSnapshot.symbol == symbol)
            .order_by(MarketSnapshot.snapshot_at.desc())
            .limit(1)
        )

    def _is_snapshot_fresh(self, snapshot: MarketSnapshot, max_age_seconds: int) -> bool:
        age_seconds = (datetime.now(UTC) - snapshot.snapshot_at).total_seconds()
        return age_seconds <= max_age_seconds

    def _is_demo_position(self, position: Position) -> bool:
        metadata = position.metadata_json or {}
        mode = metadata.get("mode") or metadata.get("execution_mode") or "unknown"
        return str(mode).lower() == "binance_demo"
