from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.main import create_app


class DummyResult:
    pass


class DummySession:
    def execute(self, statement: object) -> DummyResult:
        return DummyResult()

    def close(self) -> None:
        pass


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield DummySession()  # type: ignore[misc]

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
