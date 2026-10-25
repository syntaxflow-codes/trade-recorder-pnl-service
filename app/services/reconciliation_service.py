from collections import defaultdict
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from .accounting import State, apply_trade, decimal_string
from ..models import Trade, Position
from ..schemas import VenueSnapshot, TradeIn, format_ist
from .trade_service import equivalent

def internal(session: Session, venue=None, symbol=None):
    # Caller starts a REPEATABLE READ transaction before this function.
    tq = select(Trade)
    pq = select(Position)
    if venue:
        tq, pq = tq.where(Trade.venue == venue), pq.where(Position.venue == venue)
    if symbol:
        tq, pq = tq.where(Trade.symbol == symbol), pq.where(Position.symbol == symbol)
    trades = session.scalars(tq.order_by(Trade.venue, Trade.symbol, Trade.sequence)).all()
    positions = {(p.venue, p.symbol): p for p in session.scalars(pq).all()}
    expected = defaultdict(State)
    last = {}
    for t in trades:
        key = (t.venue, t.symbol)
        expected[key], _ = apply_trade(expected[key], t.side, t.quantity, t.price)
        last[key] = (t.event_at, t.sequence)
    discrepancies = []
    for key in sorted(set(expected) | set(positions)):
        e, p = expected.get(key, State()), positions.get(key)
        actual = State(p.quantity, p.cost_basis, p.realized_pnl) if p else State()
        seq = last.get(key, (None, 0))[1]
        bad = p is None or (key not in expected and (actual != State() or p.last_sequence != 0)) or e != actual or (p and p.last_sequence != seq) or (p and p.last_event_at != last.get(key, (None, 0))[0])
        if bad:
            discrepancies.append({"venue": key[0], "symbol": key[1], "missing_position": p is None,
                "expected": {"quantity": decimal_string(e.quantity), "cost_basis": decimal_string(e.cost_basis), "realized_pnl": decimal_string(e.realized_pnl), "last_sequence": seq},
                "actual": None if p is None else {"quantity": decimal_string(actual.quantity), "cost_basis": decimal_string(actual.cost_basis), "realized_pnl": decimal_string(actual.realized_pnl), "last_sequence": p.last_sequence},
                "difference": {"quantity": decimal_string(actual.quantity - e.quantity), "cost_basis": decimal_string(actual.cost_basis - e.cost_basis), "realized_pnl": decimal_string(actual.realized_pnl - e.realized_pnl)}})
    return {"ok": not discrepancies, "discrepancies": discrepancies, "trades_replayed": len(trades)}

def external(session: Session, snapshot: VenueSnapshot):
    local = session.scalars(select(Trade).where(Trade.venue == snapshot.venue, Trade.event_at >= snapshot.start,
        Trade.event_at < snapshot.end).order_by(Trade.id)).all()
    local_by_id = {t.trade_id: t for t in local}
    remote = {t.trade_id: t for t in snapshot.trades}
    missing = sorted(set(remote) - set(local_by_id))
    extra = sorted(set(local_by_id) - set(remote))
    conflicts = []
    for trade_id in sorted(set(remote) & set(local_by_id)):
        if not equivalent(local_by_id[trade_id], remote[trade_id]):
            conflicts.append({"trade_id": trade_id, "local": {"symbol": local_by_id[trade_id].symbol,
                "side": local_by_id[trade_id].side, "quantity": decimal_string(local_by_id[trade_id].quantity),
                "price": decimal_string(local_by_id[trade_id].price), "timestamp": format_ist(local_by_id[trade_id].event_at)},
                "snapshot": {"symbol": remote[trade_id].symbol, "side": remote[trade_id].side,
                "quantity": decimal_string(remote[trade_id].quantity), "price": decimal_string(remote[trade_id].price),
                "timestamp": format_ist(remote[trade_id].timestamp)}})
    return {"ok": not (missing or extra or conflicts), "missing_locally": missing,
            "extra_locally": extra, "conflicting": conflicts}
