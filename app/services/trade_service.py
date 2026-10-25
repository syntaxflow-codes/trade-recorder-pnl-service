from decimal import Decimal
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .accounting import State, apply_trade, decimal_string, valuation
from ..models import Trade, Position, Mark
from ..schemas import TradeIn, PriceIn, format_ist

class Conflict(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message

def lock(session: Session, domain: str, key: str):
    # Transaction-scoped PostgreSQL lock; a hash collision only causes extra serialization.
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": domain + ":" + key})

def equivalent(trade: Trade, incoming: TradeIn) -> bool:
    return (trade.venue == incoming.venue and trade.trade_id == incoming.trade_id
            and trade.symbol == incoming.symbol and trade.side == incoming.side
            and trade.quantity == incoming.quantity and trade.price == incoming.price
            and trade.event_at == incoming.timestamp)

def serialize_trade(t: Trade):
    return {"venue": t.venue, "trade_id": t.trade_id, "symbol": t.symbol, "side": t.side,
            "quantity": decimal_string(t.quantity), "price": decimal_string(t.price), "timestamp": format_ist(t.event_at),
            "accepted_at": format_ist(t.accepted_at), "sequence": t.sequence,
            "realized_pnl_increment": decimal_string(t.realized_increment)}

def ingest(session: Session, incoming: TradeIn, after_insert=None):
    lock(session, "trade", f"{len(incoming.venue)}:{incoming.venue}{incoming.trade_id}")
    existing = session.scalar(select(Trade).where(Trade.venue == incoming.venue, Trade.trade_id == incoming.trade_id))
    if existing:
        if equivalent(existing, incoming):
            return existing, False
        raise Conflict("duplicate_conflict", "trade key already exists with different fields")
    lock(session, "position", f"{len(incoming.venue)}:{incoming.venue}{incoming.symbol}")
    position = session.scalar(select(Position).where(Position.venue == incoming.venue, Position.symbol == incoming.symbol).with_for_update())
    if position and position.last_event_at and incoming.timestamp < position.last_event_at:
        raise Conflict("out_of_order", "new trade timestamp precedes last accepted trade")
    state = State(position.quantity, position.cost_basis, position.realized_pnl) if position else State()
    try:
        updated, increment = apply_trade(state, incoming.side, incoming.quantity, incoming.price)
    except ValueError as exc:
        raise Conflict("insufficient_holdings" if str(exc) == "insufficient holdings" else "accounting_limit", str(exc)) from exc
    sequence = position.last_sequence + 1 if position else 1
    trade = Trade(venue=incoming.venue, trade_id=incoming.trade_id, symbol=incoming.symbol,
                  side=incoming.side, quantity=incoming.quantity, price=incoming.price,
                  event_at=incoming.timestamp, sequence=sequence, realized_increment=increment)
    session.add(trade)
    session.flush()
    if after_insert:
        after_insert()
    if position is None:
        position = Position(venue=incoming.venue, symbol=incoming.symbol)
        session.add(position)
    position.quantity, position.cost_basis, position.realized_pnl = updated.quantity, updated.cost_basis, updated.realized_pnl
    position.last_event_at, position.last_sequence = incoming.timestamp, sequence
    session.flush()
    return trade, True

def update_mark(session: Session, incoming: PriceIn):
    lock(session, "mark", f"{len(incoming.venue)}:{incoming.venue}{incoming.symbol}")
    mark = session.scalar(select(Mark).where(Mark.venue == incoming.venue, Mark.symbol == incoming.symbol).with_for_update())
    if mark:
        if incoming.timestamp < mark.price_at:
            raise Conflict("stale_price", "mark timestamp is older than current mark")
        if incoming.timestamp == mark.price_at and incoming.price != mark.price:
            raise Conflict("price_conflict", "same timestamp has a different price")
        mark.price, mark.price_at = incoming.price, incoming.timestamp
    else:
        mark = Mark(venue=incoming.venue, symbol=incoming.symbol, price=incoming.price, price_at=incoming.timestamp)
        session.add(mark)
    session.flush()
    return mark

def serialize_position(p: Position, mark: Mark | None):
    state = State(p.quantity, p.cost_basis, p.realized_pnl)
    return {"venue": p.venue, "symbol": p.symbol, "quantity": decimal_string(p.quantity),
            "cost_basis": decimal_string(p.cost_basis), "realized_pnl": decimal_string(p.realized_pnl),
            "latest_mark": decimal_string(mark.price) if mark else None,
            "mark_timestamp": format_ist(mark.price_at) if mark else None,
            **valuation(state, mark.price if mark else None)}
