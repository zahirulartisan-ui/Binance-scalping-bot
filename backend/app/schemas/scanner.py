from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class ScannerStatusResponse(BaseModel):
    latest_run_id: str | None
    latest_run_status: str | None
    latest_run_started_at: datetime | None
    latest_run_finished_at: datetime | None
    symbols_scanned: int
    signal_candidates: int
    watch_candidates: int
    ignored_candidates: int


class ScannerRunResponse(BaseModel):
    run_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    idempotency_key: str
    metadata_json: dict[str, Any]


class ScannerCandidateResponse(BaseModel):
    run_id: str
    symbol: str
    decision: str
    reason_code: str
    regime: str | None
    entry_permission: str | None
    setup_state: str | None
    eligible_for_signal: bool
    signal_grade: str | None
    signal_score: int | None
    preferred_entry: Decimal | None
    reward_to_risk: Decimal | None
    reasons: list[str]
    metadata_json: dict[str, Any]


class ScannerRunDetailResponse(BaseModel):
    run: ScannerRunResponse
    decisions: list[ScannerCandidateResponse]
