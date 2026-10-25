from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import filters
from ..database import get_session
from ..models import Mark, Position
from ..services.trade_service import serialize_position

router = APIRouter()


@router.get("/positions")
def list_positions(venue: str | None = None, symbol: str | None = None, session: Session = Depends(get_session)):
    q = select(Position)
    venue, symbol = filters(venue, symbol)
    if venue:
        q = q.where(Position.venue == venue)
    if symbol:
        q = q.where(Position.symbol == symbol)
    positions = session.scalars(q.order_by(Position.venue, Position.symbol)).all()
    marks = {(m.venue, m.symbol): m for m in session.scalars(select(Mark)).all()}
    return {"items": [serialize_position(p, marks.get((p.venue, p.symbol))) for p in positions]}
