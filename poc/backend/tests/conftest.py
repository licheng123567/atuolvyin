import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

os.environ["ASR_BACKEND"] = "mock"
os.environ["LLM_BACKEND"] = "mock"
os.environ["LOCAL_STORAGE_ROOT"] = "/tmp/autoluyin_test_recordings"

from app.main import app  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.models.base import Base  # noqa: E402


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def engine(pg_container):
    url = pg_container.get_connection_url().replace("psycopg2", "psycopg")
    eng = create_engine(url, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    # Outer connection + transaction: session.commit() hits SAVEPOINT, not real commit.
    # trans.rollback() at teardown erases all test data regardless of session commits.
    connection = engine.connect()
    trans = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    try:
        trans.rollback()  # may already be rolled back if test raised IntegrityError
    except Exception:
        pass
    connection.close()


@pytest.fixture
async def client(db_session):
    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()
