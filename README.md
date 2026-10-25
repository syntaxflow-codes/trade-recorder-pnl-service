# Trade Recorder & PnL Service

FastAPI service for an immutable trade ledger, per-venue weighted-average positions, marks, PnL, and reconciliation.

## Start

Requires Python 3.12 and PostgreSQL 16. The values in `.env.example` are for local development; supply your own database credentials through environment variables. Set `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `TEST_DB_NAME` separately. The application builds the SQLAlchemy URL, so passwords containing characters such as `@`, `/`, `?`, `#`, or `%` do not need manual URL encoding. Quote a password in `.env` when it contains shell special characters, for example `DB_PASSWORD='p@ss:/?#%'`.

The API reuses one SQLAlchemy `QueuePool` per worker. Optional `DB_POOL_SIZE` (default `5`), `DB_MAX_OVERFLOW` (default `10`), `DB_POOL_TIMEOUT` in seconds (default `30`), and `DB_POOL_RECYCLE` in seconds (default `1800`) control it. `pool_pre_ping` is enabled and the pool is disposed on application shutdown. Size PostgreSQL `max_connections` for at most `(DB_POOL_SIZE + DB_MAX_OVERFLOW) × API workers`, plus migration, test, and administrative connections. Each request gets its own short-lived session; sessions are never shared across requests.

All input timestamps must include a timezone. The service converts them to UTC before persistence and configures its PostgreSQL sessions for UTC. API responses present every timestamp in IST as ISO 8601 with `+05:30`; for example, input `2026-10-24T10:00:00Z` is returned as `2026-10-24T15:30:00+05:30`. This applies to trade event and acceptance times, mark times, and timestamps echoed in external reconciliation conflicts. Ordering and comparisons use the UTC instant.

Financial values remain JSON strings. Responses use plain decimal notation without insignificant trailing zeros: for example, `"quantity": "15"` and `"realized_pnl": "0"`. This changes display only; calculations and PostgreSQL `NUMERIC` storage retain their documented precision.

Create separate application and test databases. For a local PostgreSQL installation on Linux, one example is:

```sh
sudo systemctl start postgresql
sudo -u postgres psql -c "CREATE ROLE trades LOGIN PASSWORD 'trades';"
sudo -u postgres createdb -O trades trades
sudo -u postgres createdb -O trades trades_test
```

If the role or databases already exist, use those and set matching database variables. Install dependencies, apply the migration, and start the API:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock -e '.[test]'
cp .env.example .env
set -a; . ./.env; set +a
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for OpenAPI, or check `curl http://localhost:8000/health`. Run the tests in another shell after loading `.env`. The test fixture refuses to clean a database unless `TEST_DB_NAME` contains `test` and differs from `DB_NAME`. Never point `TEST_DB_NAME` at production.

```sh
set -a; . ./.env; set +a
.venv/bin/pytest -q
```

Accounting and database URL unit tests run without PostgreSQL; integration tests skip when `TEST_DB_NAME` is unset.

## Sample data

After migrating an empty development database, load the example trades and marks:

```sh
set -a; . ./.env; set +a
.venv/bin/python -m app.seed
```

The seed creates five trades across Binance and Kraken and three mark prices. Positions are calculated from the trades through the normal ingestion service; they are never inserted directly. Binance `BTC/USDT` demonstrates the worked example: quantity `15`, realized PnL `75`, unrealized PnL `300`, and total PnL `375`. The command is repeatable: existing trade IDs have no extra financial effect, and a newer mark is preserved. Use it only for development data; new seed trades still obey timestamp ordering and may conflict with an existing ledger.

## API examples

The required worked example, using equal event timestamps to demonstrate processing sequence:

```sh
curl -s -X POST http://localhost:8000/trades -H 'Content-Type: application/json' -d '{"venue":"binance","trade_id":"T-1001","symbol":"BTC/USDT","side":"BUY","quantity":"10","price":"100","timestamp":"2026-10-24T10:00:00Z"}'
curl -s -X POST http://localhost:8000/trades -H 'Content-Type: application/json' -d '{"venue":"binance","trade_id":"T-1002","symbol":"BTC/USDT","side":"BUY","quantity":"10","price":"110","timestamp":"2026-10-24T10:00:00Z"}'
curl -s -X POST http://localhost:8000/trades -H 'Content-Type: application/json' -d '{"venue":"binance","trade_id":"T-1003","symbol":"BTC/USDT","side":"SELL","quantity":"5","price":"120","timestamp":"2026-10-24T10:00:00Z"}'
curl -s -X PUT http://localhost:8000/prices -H 'Content-Type: application/json' -d '{"venue":"binance","symbol":"BTC/USDT","price":"125","timestamp":"2026-10-24T11:00:00Z"}'
curl -s 'http://localhost:8000/positions?venue=binance&symbol=BTC%2FUSDT'
```

Expected position: quantity `15`, average cost `105`, cost basis `1575`, realized PnL `75`, unrealized PnL `300`, total PnL `375`. These are returned as plain decimal strings.

Retry the first `POST /trades` body: HTTP 200 returns the original trade and does not alter the position. Change its price under the same `(venue, trade_id)`: HTTP 409 `duplicate_conflict`. A new `SELL` of quantity `16` would return HTTP 409 `insufficient_holdings`; it inserts no trade and leaves quantity `15`.

```sh
curl -s 'http://localhost:8000/trades?venue=binance&limit=50&offset=0'
curl -s -X POST 'http://localhost:8000/reconciliation?venue=binance'
curl -s -X POST http://localhost:8000/reconciliation/venue -H 'Content-Type: application/json' -d '{"venue":"binance","start":"2026-10-24T00:00:00Z","end":"2026-10-25T00:00:00Z","complete":true,"trades":[{"venue":"binance","trade_id":"T-1001","symbol":"BTC/USDT","side":"BUY","quantity":"10","price":"100","timestamp":"2026-10-24T10:00:00Z"},{"venue":"binance","trade_id":"T-1002","symbol":"BTC/USDT","side":"BUY","quantity":"10","price":"110","timestamp":"2026-10-24T10:00:00Z"},{"venue":"binance","trade_id":"T-1003","symbol":"BTC/USDT","side":"SELL","quantity":"5","price":"120","timestamp":"2026-10-24T10:00:00Z"}]}'
```

The external endpoint reports missing, extra, and conflicting trade IDs but does not import or repair. See [DESIGN.md](DESIGN.md) for consistency, rounding, ordering, and transaction details.

## Known limits

One logical account per venue; no fees, funding, transfers, FX conversion, shorts, authentication, live exchange feed, or historical backfill. PnL is per pair in quote currency. External snapshots are caller supplied and limited to 1,000 trades per request. An open position without a mark has null unrealized and total PnL. Internal reconciliation cannot detect trades absent from the local ledger.
