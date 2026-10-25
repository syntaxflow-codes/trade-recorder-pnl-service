from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import filters
from ..database import get_session
from ..schemas import VenueSnapshot
from ..services.reconciliation_service import external, internal

router = APIRouter()


@router.post("/reconciliation")
def reconcile(venue: str | None = None, symbol: str | None = None, session: Session = Depends(get_session)):
    venue, symbol = filters(venue, symbol)
    session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    result = internal(session, venue, symbol)
    session.rollback()
    return result


@router.post("/reconciliation/venue")
def reconcile_venue(body: VenueSnapshot, session: Session = Depends(get_session)):
    session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    result = external(session, body)
    session.rollback()
    return result
