from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.models import Trade, Position, Mark
from app.schemas import TradeIn
from app.services.trade_service import ingest

def trade(trade_id="a", side="BUY", quantity="10", price="100", timestamp="2026-10-24T10:00:00Z", venue="binance", symbol="BTC/USDT"):
    return dict(venue=venue, trade_id=trade_id, symbol=symbol, side=side, quantity=quantity, price=price, timestamp=timestamp)

def test_worked_api_and_marks(client):
    assert client.get("/health").json() == {"status": "ok"}
    for t in [trade(), trade("b", quantity="10", price="110"), trade("c", side="SELL", quantity="5", price="120")]:
        assert client.post("/trades", json=t).status_code == 201
    p = client.get("/positions").json()["items"][0]
    assert p["quantity"] == "15" and p["unrealized_pnl"] is None
    assert client.put("/prices", json={"venue":"binance","symbol":"BTC/USDT","price":"125","timestamp":"2026-10-24T11:00:00Z"}).status_code == 200
    p = client.get("/positions").json()["items"][0]
    assert D(p["realized_pnl"]) == 75 and D(p["unrealized_pnl"]) == 300 and D(p["total_pnl"]) == 375
    assert client.put("/prices", json={"venue":"binance","symbol":"BTC/USDT","price":"130","timestamp":"2026-10-24T12:00:00Z"}).status_code == 200
    updated = client.get("/positions").json()["items"][0]
    assert D(updated["realized_pnl"]) == 75 and D(updated["unrealized_pnl"]) == 375
    assert client.post("/reconciliation").json()["ok"] is True


def test_utc_storage_and_ist_responses(client, engine):
    accepted = client.post("/trades", json=trade())
    assert accepted.status_code == 201
    body = accepted.json()
    assert body["timestamp"] == "2026-10-24T15:30:00+05:30"
    assert datetime.fromisoformat(body["accepted_at"]).utcoffset() == timedelta(hours=5, minutes=30)
    assert client.get("/trades").json()["items"][0]["timestamp"] == body["timestamp"]

    mark = {"venue": "binance", "symbol": "BTC/USDT", "price": "125", "timestamp": "2026-10-24T11:00:00Z"}
    assert client.put("/prices", json=mark).json()["timestamp"] == "2026-10-24T16:30:00+05:30"
    assert client.get("/positions").json()["items"][0]["mark_timestamp"] == "2026-10-24T16:30:00+05:30"

    snapshot = {"venue": "binance", "start": "2026-10-24T00:00:00Z", "end": "2026-10-25T00:00:00Z",
                "complete": True, "trades": [{**trade(), "price": "101"}]}
    conflict = client.post("/reconciliation/venue", json=snapshot).json()["conflicting"][0]
    assert conflict["local"]["timestamp"] == body["timestamp"]
    assert conflict["snapshot"]["timestamp"] == body["timestamp"]

    with Session(engine) as session:
        assert session.scalar(text("SELECT current_setting('TimeZone')")) == "UTC"
        stored_trade = session.scalar(select(Trade))
        stored_position = session.scalar(select(Position))
        stored_mark = session.scalar(select(Mark))
        assert stored_trade.event_at == datetime(2026, 10, 24, 10, tzinfo=timezone.utc)
        assert stored_trade.accepted_at.utcoffset() == timedelta(0)
        assert stored_position.last_event_at.utcoffset() == timedelta(0)
        assert stored_mark.price_at == datetime(2026, 10, 24, 11, tzinfo=timezone.utc)

def test_duplicates_order_oversell(client):
    t = trade()
    assert client.post("/trades", json=t).status_code == 201
    equivalent = {**t, "quantity":"10.0", "timestamp":"2026-10-24T15:30:00+05:30"}
    assert client.post("/trades", json=equivalent).status_code == 200
    assert client.post("/trades", json={**t, "price":"101"}).status_code == 409
    assert client.post("/trades", json=trade("a", symbol="ETH/USDT")).status_code == 409
    assert client.post("/trades", json=trade("old", timestamp="2026-10-24T09:00:00Z")).status_code == 409
    assert client.post("/trades", json=trade("sell", side="SELL", quantity="15")).status_code == 409
    assert client.post("/trades", json=trade("sell", side="SELL", quantity="7")).status_code == 201
    assert D(client.get("/positions").json()["items"][0]["quantity"]) == 3

def test_validation_and_venue(client):
    assert client.post("/trades", json=trade(side="HOLD")).status_code == 422
    for q in [0, -1, 1.2, "NaN", "Infinity", "0", "-1", "1.0000000000001"]:
        assert client.post("/trades", json=trade(quantity=q)).status_code == 422
    for p in [1.2, "NaN", "Infinity", "10000000000000000", "1.0000000000001"]:
        assert client.post("/trades", json=trade(price=p)).status_code == 422
    assert client.post("/trades", json=trade(timestamp="2026-10-24T10:00:00")).status_code == 422
    assert client.post("/trades", json={k:v for k,v in trade().items() if k != "price"}).status_code == 422
    assert client.post("/trades", json=trade(trade_id="bad\u0000id")).status_code == 422
    assert client.get("/trades?symbol=BTC").status_code == 422
    assert client.post("/trades", json=trade(venue="binance")).status_code == 201
    assert client.post("/trades", json=trade(venue="kraken")).status_code == 201
    assert len(client.get("/trades").json()["items"]) == 2

def test_marks_and_external(client):
    t = trade()
    client.post("/trades", json=t)
    mark = {"venue":"binance","symbol":"BTC/USDT","price":"120","timestamp":"2026-10-24T11:00:00Z"}
    assert client.put("/prices", json=mark).status_code == 200
    assert client.put("/prices", json=mark).status_code == 200
    assert client.put("/prices", json={**mark,"price":"121"}).status_code == 409
    assert client.put("/prices", json={**mark,"timestamp":"2026-10-24T09:00:00Z"}).status_code == 409
    snap = {"venue":"binance","start":"2026-10-24T00:00:00Z","end":"2026-10-25T00:00:00Z","complete":True,
            "trades":[{**t,"price":"101"},trade("remote")]}
    report = client.post("/reconciliation/venue", json=snap).json()
    assert report["missing_locally"] == ["remote"] and report["conflicting"][0]["trade_id"] == "a"
    assert client.post("/reconciliation/venue", json={**snap,"trades":[]}).json()["extra_locally"] == ["a"]

def test_corruption_detected(client, engine):
    client.post("/trades", json=trade())
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE positions SET cost_basis=999")
    report = client.post("/reconciliation").json()
    assert report["ok"] is False and report["discrepancies"][0]["difference"]["cost_basis"] != "0"

def test_missing_position_detected(client, engine):
    client.post("/trades", json=trade())
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM positions")
    report = client.post("/reconciliation").json()
    assert report["discrepancies"][0]["missing_position"] is True

def test_snapshot_rejects_duplicate_and_incomplete(client):
    snapshot = {"venue":"binance", "start":"2026-10-24T00:00:00Z", "end":"2026-10-25T00:00:00Z",
                "complete":True, "trades":[trade(),trade()]}
    assert client.post("/reconciliation/venue", json=snapshot).status_code == 422
    assert client.post("/reconciliation/venue", json={**snapshot,"complete":False,"trades":[]}).status_code == 422

def test_injected_failure_rolls_back(client, engine):
    from sqlalchemy.orm import Session
    from sqlalchemy import func
    with Session(engine) as session:
        try:
            with session.begin():
                ingest(session, TradeIn(**trade()), after_insert=lambda: (_ for _ in ()).throw(RuntimeError("injected")))
        except RuntimeError:
            pass
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Trade)) == 0
        assert session.scalar(select(func.count()).select_from(Position)) == 0

def test_concurrent_sells(client, engine):
    client.post("/trades", json=trade())
    from sqlalchemy.orm import Session
    from threading import Barrier
    barrier = Barrier(2)
    def worker(n):
        barrier.wait()
        with Session(engine) as session:
            try:
                with session.begin():
                    ingest(session, TradeIn(**trade(str(n), side="SELL", quantity="7")))
                return "ok"
            except Exception as exc:
                return type(exc).__name__
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))
    assert results.count("ok") == 1
    assert D(client.get("/positions").json()["items"][0]["quantity"]) == 3

def test_concurrent_identical_and_first_position(client, engine):
    from sqlalchemy.orm import Session
    from threading import Barrier
    barrier = Barrier(2)
    def worker(_):
        barrier.wait()
        with Session(engine) as session:
            with session.begin():
                _, created = ingest(session, TradeIn(**trade()))
            return created
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(worker, [1,2])) == [False, True]
    assert len(client.get("/trades").json()["items"]) == 1

def test_concurrent_distinct_first_position(client, engine):
    from sqlalchemy.orm import Session
    from threading import Barrier
    barrier = Barrier(2)
    def worker(n):
        barrier.wait()
        with Session(engine) as session:
            with session.begin():
                ingest(session, TradeIn(**trade(str(n), quantity="2")))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker, [1, 2]))
    p = client.get("/positions").json()["items"][0]
    assert D(p["quantity"]) == 4
    assert len(client.get("/trades").json()["items"]) == 2

def test_replay_older_duplicate_and_equal_sequence(client):
    first = trade("first")
    second = trade("second", timestamp="2026-10-24T11:00:00Z")
    assert client.post("/trades", json=first).status_code == 201
    assert client.post("/trades", json=trade("equal")).json()["sequence"] == 2
    assert client.post("/trades", json=second).status_code == 201
    replay = client.post("/trades", json=first)
    assert replay.status_code == 200 and replay.json()["sequence"] == 1
    assert client.post("/reconciliation").json()["ok"] is True

def test_sell_without_holdings_and_closed_mark(client):
    assert client.post("/trades", json=trade(side="SELL")).status_code == 409
    assert client.get("/trades").json()["items"] == []
    assert client.post("/trades", json=trade("buy")).status_code == 201
    assert client.post("/trades", json=trade("close", side="SELL", price="120")).status_code == 201
    p = client.get("/positions").json()["items"][0]
    assert D(p["quantity"]) == 0 and D(p["cost_basis"]) == 0
    assert p["average_cost"] is None and D(p["total_pnl"]) == 200
    assert client.post("/trades", json=trade("reopen", quantity="2", price="50")).status_code == 201
    assert D(client.get("/positions").json()["items"][0]["realized_pnl"]) == 200
