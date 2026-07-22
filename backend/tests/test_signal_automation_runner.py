from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.trading import AppSetting
from app.services.signal_automation_runner import SignalAutomationRunner


class FakeAutomationService:
    def __init__(self) -> None:
        self.calls = 0

    def run_cycle(self, db: Session) -> None:
        self.calls += 1


def test_signal_automation_runner_uses_runtime_interval(db_session: Session) -> None:
    db_session.add(
        AppSetting(
            key="scanner_interval_seconds",
            value={"value": 45},
            value_type="integer",
            description="test",
        )
    )
    db_session.commit()
    service = FakeAutomationService()
    runner = SignalAutomationRunner(
        Settings(app_env="test", database_url="sqlite+pysqlite:///:memory:"),
        lambda: db_session,
        automation_service=service,  # type: ignore[arg-type]
    )

    wait_seconds = runner.run_once()

    assert wait_seconds == 45
    assert service.calls == 1


def test_signal_automation_runner_graceful_shutdown(db_session: Session) -> None:
    runner = SignalAutomationRunner(
        Settings(
            app_env="test",
            database_url="sqlite+pysqlite:///:memory:",
            scanner_interval_seconds=10,
        ),
        lambda: db_session,
        automation_service=FakeAutomationService(),  # type: ignore[arg-type]
    )

    runner.start()
    time.sleep(0.01)
    runner.stop()

    assert not runner.is_running
