import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .api import InvalidFilter
from .api import positions, prices, reconciliation, trades
from .database import dispose_app_engine, get_session
from .services.trade_service import Conflict

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        await asyncio.to_thread(dispose_app_engine)


app = FastAPI(title="Trade Recorder & PnL Service", lifespan=lifespan)
app.include_router(trades.router)
app.include_router(positions.router)
app.include_router(prices.router)
app.include_router(reconciliation.router)


@app.exception_handler(Conflict)
def conflict_handler(request: Request, exc: Conflict):
    return JSONResponse(status_code=409, content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(RequestValidationError)
def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Invalid request", "details": [{"field": ".".join(map(str, item["loc"])), "message": item["msg"]} for item in exc.errors()]}})


@app.exception_handler(IntegrityError)
def integrity_handler(request: Request, exc: IntegrityError):
    log.exception("database integrity error")
    return JSONResponse(status_code=409, content={"error": {"code": "database_conflict", "message": "Concurrent database constraint conflict; retry request"}})


@app.exception_handler(InvalidFilter)
def invalid_filter_handler(request: Request, exc: InvalidFilter):
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": str(exc)}})


@app.exception_handler(SQLAlchemyError)
def database_error_handler(request: Request, exc: SQLAlchemyError):
    log.exception("database operation failed")
    return JSONResponse(status_code=503, content={"error": {"code": "database_unavailable", "message": "Database operation failed"}})


@app.get("/health")
def health(session: Session = Depends(get_session)):
    session.execute(text("SELECT 1"))
    return {"status": "ok"}
