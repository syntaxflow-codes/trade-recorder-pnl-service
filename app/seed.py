"""Deterministic development data. Run with: python -m app.seed"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import make_engine
from .models import Mark
from .schemas import PriceIn, TradeIn
from .services.trade_service import ingest, update_mark


SAMPLE_TRADES = (
    {"venue": "binance", "trade_id": "SEED-BTC-1", "symbol": "BTC/USDT", "side": "BUY", "quantity": "10", "price": "100", "timestamp": "2026-10-24T10:00:00Z"},
    {"venue": "binance", "trade_id": "SEED-BTC-2", "symbol": "BTC/USDT", "side": "BUY", "quantity": "10", "price": "110", "timestamp": "2026-10-24T10:00:00Z"},
    {"venue": "binance", "trade_id": "SEED-BTC-3", "symbol": "BTC/USDT", "side": "SELL", "quantity": "5", "price": "120", "timestamp": "2026-10-24T10:00:00Z"},
    {"venue": "kraken", "trade_id": "SEED-KRAKEN-BTC-1", "symbol": "BTC/USDT", "side": "BUY", "quantity": "2", "price": "200", "timestamp": "2026-10-24T10:00:00Z"},
    {"venue": "binance", "trade_id": "SEED-ETH-1", "symbol": "ETH/USDT", "side": "BUY", "quantity": "4", "price": "50", "timestamp": "2026-10-24T10:00:00Z"},
)

SAMPLE_MARKS = (
    {"venue": "binance", "symbol": "BTC/USDT", "price": "125", "timestamp": "2026-10-24T11:00:00Z"},
    {"venue": "kraken", "symbol": "BTC/USDT", "price": "225", "timestamp": "2026-10-24T11:00:00Z"},
    {"venue": "binance", "symbol": "ETH/USDT", "price": "60", "timestamp": "2026-10-24T11:00:00Z"},
)


def seed_sample_data(session: Session) -> dict[str, int]:
    """Insert through normal business rules; a rerun does not duplicate trades."""
    created = 0
    marks_written = 0
    with session.begin():
        for values in SAMPLE_TRADES:
            _, inserted = ingest(session, TradeIn(**values))
            created += int(inserted)
        for values in SAMPLE_MARKS:
            incoming = PriceIn(**values)
            current = session.scalar(select(Mark).where(Mark.venue == incoming.venue, Mark.symbol == incoming.symbol))
            if current is not None and current.price_at > incoming.timestamp:
                continue
            update_mark(session, incoming)
            marks_written += 1
    return {"trades_created": created, "trades_existing": len(SAMPLE_TRADES) - created, "marks_written": marks_written}


def main() -> None:
    engine = make_engine()
    try:
        with Session(engine) as session:
            result = seed_sample_data(session)
        print(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
