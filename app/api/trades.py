from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import filters
from ..database import get_session
from ..models import Trade
from ..schemas import TradeIn
from ..services.trade_service import ingest, serialize_trade

router = APIRouter()


@router.post("/trades")
def post_trade(body: TradeIn, session: Session = Depends(get_session)):
    with session.begin():
        trade, created = ingest(session, body)
    return JSONResponse(status_code=201 if created else 200, content=serialize_trade(trade))


@router.get("/trades")
def list_trades(venue: str | None = None, symbol: str | None = None, limit: int = Query(50, ge=1, le=200),
                offset: int = Query(0, ge=0), session: Session = Depends(get_session)):
    q = select(Trade)
    venue, symbol = filters(venue, symbol)
    if venue:
        q = q.where(Trade.venue == venue)
    if symbol:
        q = q.where(Trade.symbol == symbol)
    rows = session.scalars(q.order_by(Trade.id).limit(limit).offset(offset)).all()
    return {"items": [serialize_trade(t) for t in rows], "limit": limit, "offset": offset}
