from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import CandleTimeframe
from app.services.binance_client import BinanceMarketDataClient
from app.services.market_data_service import (
    create_cycle,
    ensure_symbol,
    finish_cycle,
    parse_closed_candle,
    parse_snapshot,
    persist_candle,
    persist_snapshot,
    refresh_symbols,
)

logger = logging.getLogger(__name__)


class MarketDataRunner:
    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session],
        client: BinanceMarketDataClient,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.client = client
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._cycle_lock = threading.Lock()
        self._last_symbol_refresh = 0.0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if not self.settings.market_data_collection_enabled:
            return
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="market-data-runner",
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
                logger.exception("market data cycle failed")
            self._stop_event.wait(self.settings.market_data_cycle_interval_seconds)

    def run_once(self) -> bool:
        if not self._cycle_lock.acquire(blocking=False):
            return False
        try:
            with self.session_factory() as db:
                self._run_cycle(db)
                db.commit()
            return True
        except Exception:
            logger.exception("market data cycle failed")
            return False
        finally:
            self._cycle_lock.release()

    def _run_cycle(self, db: Session) -> None:
        symbols = [symbol.upper() for symbol in self.settings.market_data_symbols]
        cycle = create_cycle(db, len(symbols))
        symbol_refresh_due = (
            time.monotonic() - self._last_symbol_refresh
            >= self.settings.market_data_symbol_refresh_seconds
        )
        if symbol_refresh_due:
            refresh_symbols(db, self.client.exchange_info())
            self._last_symbol_refresh = time.monotonic()

        succeeded = 0
        failed = 0
        candles_stored = 0
        snapshots_stored = 0
        rejection_reasons: dict[str, str] = {}

        for symbol in symbols:
            try:
                ensure_symbol(db, symbol)
                price_payload = self.client.recent_price(symbol)
                book_payload = self.client.book_ticker(symbol)
                if persist_snapshot(db, parse_snapshot(symbol, price_payload, book_payload)):
                    snapshots_stored += 1
                for timeframe in (CandleTimeframe.ONE_MINUTE, CandleTimeframe.FIVE_MINUTES):
                    klines = self.client.klines(symbol, timeframe.value, limit=2)
                    if not klines:
                        raise ValueError("no candles returned")
                    raw_candle = klines[-2] if len(klines) > 1 else klines[0]
                    candle = parse_closed_candle(raw_candle, symbol, timeframe)
                    if persist_candle(db, candle):
                        candles_stored += 1
                succeeded += 1
            except Exception as exc:
                failed += 1
                rejection_reasons[symbol] = exc.__class__.__name__

        finish_cycle(
            cycle,
            succeeded=succeeded,
            failed=failed,
            candles_stored=candles_stored,
            snapshots_stored=snapshots_stored,
            rejection_reasons=rejection_reasons,
        )
