from sqlalchemy.pool import QueuePool
from app.database import database_url, dispose_app_engine, get_app_session_factory


def test_password_with_url_special_characters(monkeypatch):
    values = {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_USER": "trades",
        "DB_PASSWORD": "p@ss:/?#%",
        "DB_NAME": "trades",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    url = database_url()
    assert url.password == "p@ss:/?#%"
    assert url.database == "trades"
    assert url.render_as_string(hide_password=False).split("@localhost")[0].endswith("p%40ss%3A%2F%3F%23%25")


def test_test_database_uses_same_connection_settings(monkeypatch):
    values = {
        "DB_HOST": "/tmp",
        "DB_PORT": "55432",
        "DB_USER": "hadi",
        "DB_PASSWORD": "",
        "DB_NAME": "trades",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    url = database_url("trades_test")
    assert url.database == "trades_test"
    assert url.query["host"] == "/tmp"
    assert url.port == 55432


def test_application_reuses_bounded_pool(monkeypatch):
    settings = {
        "DB_HOST": "localhost", "DB_PORT": "5432", "DB_USER": "trades",
        "DB_PASSWORD": "p@ss:/?#%", "DB_NAME": "trades",
        "DB_POOL_SIZE": "2", "DB_MAX_OVERFLOW": "3",
        "DB_POOL_TIMEOUT": "7", "DB_POOL_RECYCLE": "60",
    }
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    dispose_app_engine()
    try:
        factory = get_app_session_factory()
        assert get_app_session_factory() is factory
        engine = factory.kw["bind"]
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.size() == 2
        assert engine.pool._max_overflow == 3
        assert engine.pool.timeout() == 7
        assert engine.pool._recycle == 60
        with factory() as first, factory() as second:
            assert first.bind is second.bind is engine
    finally:
        dispose_app_engine()
