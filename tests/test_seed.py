from decimal import Decimal

from sqlalchemy.orm import Session

from app.seed import seed_sample_data


def test_seed_creates_derived_positions_and_is_repeatable(client, engine):
    with Session(engine) as session:
        first = seed_sample_data(session)
    assert first == {"trades_created": 5, "trades_existing": 0, "marks_written": 3}

    with Session(engine) as session:
        second = seed_sample_data(session)
    assert second == {"trades_created": 0, "trades_existing": 5, "marks_written": 3}

    assert len(client.get("/trades").json()["items"]) == 5
    positions = {(p["venue"], p["symbol"]): p for p in client.get("/positions").json()["items"]}
    assert len(positions) == 3
    binance_btc = positions[("binance", "BTC/USDT")]
    assert Decimal(binance_btc["quantity"]) == 15
    assert Decimal(binance_btc["realized_pnl"]) == 75
    assert Decimal(binance_btc["unrealized_pnl"]) == 300
    assert Decimal(binance_btc["total_pnl"]) == 375
    assert binance_btc["quantity"] == "15"
    assert binance_btc["cost_basis"] == "1575"
    assert positions[("binance", "ETH/USDT")]["realized_pnl"] == "0"
    assert Decimal(positions[("kraken", "BTC/USDT")]["quantity"]) == 2
    assert client.post("/reconciliation").json()["ok"] is True

    newer = {"venue": "binance", "symbol": "BTC/USDT", "price": "130", "timestamp": "2026-10-24T12:00:00Z"}
    assert client.put("/prices", json=newer).status_code == 200
    with Session(engine) as session:
        third = seed_sample_data(session)
    assert third == {"trades_created": 0, "trades_existing": 5, "marks_written": 2}
    latest = client.get("/positions?venue=binance&symbol=BTC%2FUSDT").json()["items"][0]
    assert Decimal(latest["latest_mark"]) == 130
