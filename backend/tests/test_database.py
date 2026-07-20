from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.database.session as database_session
from app.database.base import Base
from app.database.session import get_db
from app.models.enums import OrderSide, PositionStatus
from app.models.trading import Position


def test_database_session_rolls_back_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(
        database_session,
        "SessionLocal",
        sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False),
    )

    dependency = get_db()
    db = next(dependency)
    db.add(
        Position(
            symbol="BTCUSDT",
            status=PositionStatus.OPEN,
            side=OrderSide.BUY,
            quantity=Decimal("-1"),
            average_entry_price=Decimal("100.00000000"),
        )
    )

    with pytest.raises(IntegrityError):
        dependency.throw(IntegrityError("statement", "params", Exception("boom")))

    with database_session.SessionLocal() as verification_session:
        assert verification_session.scalars(select(Position)).all() == []


def test_model_constraints_decimal_persistence_and_utc_timestamps(db_session: Session) -> None:
    position = Position(
        symbol="BTCUSDT",
        status=PositionStatus.OPEN,
        side=OrderSide.BUY,
        quantity=Decimal("0.01000000"),
        average_entry_price=Decimal("65432.12345678"),
        realized_pnl=Decimal("0.00000000"),
        unrealized_pnl=Decimal("1.23000000"),
    )
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)

    assert position.average_entry_price == Decimal("65432.12345678")
    assert position.created_at.tzinfo is not None
    assert position.updated_at.tzinfo is not None

    invalid_position = Position(
        symbol="ETHUSDT",
        status=PositionStatus.OPEN,
        side=OrderSide.BUY,
        quantity=Decimal("-0.01000000"),
        average_entry_price=Decimal("100.00000000"),
    )
    db_session.add(invalid_position)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
