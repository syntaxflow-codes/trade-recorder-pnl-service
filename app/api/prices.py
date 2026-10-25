from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_session
from ..schemas import PriceIn, format_ist
from ..services.accounting import decimal_string
from ..services.trade_service import update_mark

router = APIRouter()


@router.put("/prices")
def put_price(body: PriceIn, session: Session = Depends(get_session)):
    with session.begin():
        mark = update_mark(session, body)
    return {"venue": mark.venue, "symbol": mark.symbol, "price": decimal_string(mark.price), "timestamp": format_ist(mark.price_at)}
