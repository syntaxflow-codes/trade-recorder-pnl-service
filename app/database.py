import os
from threading import Lock
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool

class Base(DeclarativeBase):
    pass

def database_url(database: str | None = None) -> URL:
    """Build a safe connection URL without parsing or interpolating credentials."""
    host = os.environ["DB_HOST"]
    port = int(os.environ["DB_PORT"])
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=None if host.startswith("/") else host,
        port=port,
        database=os.environ["DB_NAME"] if database is None else database,
        query={"host": host} if host.startswith("/") else {},
    )


def pool_options() -> dict:
    size = int(os.getenv("DB_POOL_SIZE", "5"))
    overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    recycle = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    if size < 1 or overflow < 0 or timeout < 1 or recycle < 0:
        raise ValueError("invalid database pool settings")
    return {
        "poolclass": QueuePool,
        "pool_size": size,
        "max_overflow": overflow,
        "pool_timeout": timeout,
        "pool_recycle": recycle,
        "pool_pre_ping": True,
    }


def make_engine(database: str | None = None):
    return create_engine(database_url(database), connect_args={"options": "-c timezone=UTC"}, **pool_options())


_pool_lock = Lock()
_app_engine = None
_app_session_factory = None


def get_app_session_factory():
    """Create one engine and pool per worker, then reuse them across requests."""
    global _app_engine, _app_session_factory
    if _app_session_factory is None:
        with _pool_lock:
            if _app_session_factory is None:
                _app_engine = make_engine()
                _app_session_factory = sessionmaker(_app_engine, expire_on_commit=False)
    return _app_session_factory


def dispose_app_engine():
    global _app_engine, _app_session_factory
    with _pool_lock:
        if _app_engine is not None:
            _app_engine.dispose()
        _app_engine = None
        _app_session_factory = None



def get_session():
    factory = get_app_session_factory()
    with factory() as session:
        yield session
