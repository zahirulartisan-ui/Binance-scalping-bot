from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.database.session import get_db
from app.models.enums import ScannerDecisionType
from app.models.trading import ScannerDecision, ScannerRun
from app.schemas.scanner import (
    ScannerCandidateResponse,
    ScannerRunDetailResponse,
    ScannerRunResponse,
    ScannerStatusResponse,
)
from app.services.scanner_service import ScannerService

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner"])


def _enum_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError("scanner enum value must be str or StrEnum")


def _run_response(run: ScannerRun) -> ScannerRunResponse:
    return ScannerRunResponse(
        run_id=str(run.id),
        status=_enum_value(run.status),
        started_at=run.started_at,
        finished_at=run.finished_at,
        idempotency_key=run.idempotency_key,
        metadata_json=run.metadata_json,
    )


def _candidate_response(row: ScannerDecision) -> ScannerCandidateResponse:
    metadata = row.metadata_json or {}
    return ScannerCandidateResponse(
        run_id=str(row.scanner_run_id),
        symbol=row.symbol,
        decision=_enum_value(row.decision),
        reason_code=row.reason_code,
        regime=metadata.get("regime"),
        entry_permission=metadata.get("entry_permission"),
        setup_state=metadata.get("setup_state"),
        eligible_for_signal=bool(metadata.get("eligible_for_signal", False)),
        signal_grade=metadata.get("signal_grade"),
        signal_score=metadata.get("signal_score"),
        preferred_entry=metadata.get("preferred_entry"),
        reward_to_risk=metadata.get("reward_to_risk"),
        reasons=list(metadata.get("reasons", [])),
        metadata_json=metadata,
    )


@router.get("/status", response_model=ScannerStatusResponse)
def read_scanner_status(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ScannerStatusResponse:
    latest = ScannerService(settings).latest_status(db)
    metadata = latest.metadata_json if latest else {}
    return ScannerStatusResponse(
        latest_run_id=str(latest.id) if latest else None,
        latest_run_status=_enum_value(latest.status) if latest else None,
        latest_run_started_at=latest.started_at if latest else None,
        latest_run_finished_at=latest.finished_at if latest else None,
        symbols_scanned=int(metadata.get("symbols_scanned", 0)),
        signal_candidates=int(metadata.get("signal_candidates", 0)),
        watch_candidates=int(metadata.get("watch_candidates", 0)),
        ignored_candidates=int(metadata.get("ignored_candidates", 0)),
    )


@router.post("/run", response_model=ScannerRunResponse)
def run_scanner(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ScannerRunResponse:
    run = ScannerService(settings).run_scan(db, limit)
    return _run_response(run)


@router.get("/runs", response_model=list[ScannerRunResponse])
def read_scanner_runs(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ScannerRunResponse]:
    runs = ScannerService(settings).list_runs(db, limit)
    return [_run_response(run) for run in runs]


@router.get("/runs/{run_id}", response_model=ScannerRunDetailResponse)
def read_scanner_run(
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    decision: ScannerDecisionType | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> ScannerRunDetailResponse:
    service = ScannerService(settings)
    try:
        parsed = uuid.UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid run id") from exc
    run = service.get_run(db, parsed)
    if run is None:
        raise HTTPException(status_code=404, detail="scanner run not found")
    decisions = service.list_decisions(db, parsed, decision, limit)
    return ScannerRunDetailResponse(
        run=_run_response(run),
        decisions=[_candidate_response(item) for item in decisions],
    )


@router.get("/candidates", response_model=list[ScannerCandidateResponse])
def read_scanner_candidates(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    decision: ScannerDecisionType | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    refresh: bool = False,
) -> list[ScannerCandidateResponse]:
    service = ScannerService(settings)
    latest = service.latest_status(db)
    if latest is None or refresh:
        latest = service.run_scan(db, limit)
    rows = service.list_decisions(db, latest.id, decision, limit)
    return [_candidate_response(item) for item in rows]
