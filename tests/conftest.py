import os
import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_session, make_engine

@pytest.fixture(scope="session")
def engine():
    name = os.getenv("TEST_DB_NAME")
    if not name:
        pytest.skip("set TEST_DB_NAME to an isolated PostgreSQL test database")
    if "test" not in name.lower() or name == os.getenv("DB_NAME"):
        pytest.fail("TEST_DB_NAME must contain 'test' and differ from DB_NAME")
    engine = make_engine(database=name)
    with engine.connect() as conn:
        name = conn.scalar(text("SELECT current_database()"))
        if "test" not in name.lower():
            pytest.fail("refusing to clean a non-test database")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def client(engine):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE trades, positions, marks RESTART IDENTITY CASCADE"))
    factory = sessionmaker(engine, expire_on_commit=False)
    def override():
        with factory() as session:
            yield session
    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
