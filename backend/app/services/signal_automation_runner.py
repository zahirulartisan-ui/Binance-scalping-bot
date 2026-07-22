from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.services.settings_service import get_public_settings
from app.services.signal_automation_service import SignalAutomationService

logger = logging.getLogger(__name__)


class SignalAutomationRunner:
    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session],
        automation_service: SignalAutomationService | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.automation_service = automation_service or SignalAutomationService(settings)
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
            name="signal-automation-runner",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout_seconds: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout_seconds)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            wait_seconds = self.settings.scanner_interval_seconds
            try:
                wait_seconds = self.run_once()
            except Exception:
                logger.exception("signal automation cycle failed")
            self._stop_event.wait(wait_seconds)

    def run_once(self) -> int:
        if not self._cycle_lock.acquire(blocking=False):
            return self.settings.scanner_interval_seconds
        try:
            with self.session_factory() as db:
                runtime = get_public_settings(db, self.settings)
                self.automation_service.run_cycle(db)
                db.commit()
                return int(runtime["scanner_interval_seconds"])
        except Exception:
            logger.exception("signal automation cycle failed")
            return self.settings.scanner_interval_seconds
        finally:
            self._cycle_lock.release()
