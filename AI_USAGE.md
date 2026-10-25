# AI usage

OpenAI Codex assisted with the initial architecture, implementation, tests, and documentation in this workspace. The implementation was built from the assignment requirements; no outside AI interactions are claimed.

Codex checked the code against the assignment, including weighted-average cost, transaction ordering, database locking, Decimal validation, and reconciliation behavior. The initial PostgreSQL test run exposed a NUL byte in advisory-lock keys and a validation-error serialization problem; both were corrected. A test fixture initially rejected a valid Unix-socket test URL and was corrected to parse URLs with SQLAlchemy. The migration upgrade and Python import/compile checks also ran successfully.

At the user's request, Codex later reorganized the application into `app/api/` for route handlers, `app/services/` for accounting and trade/reconciliation logic, `app/database.py` for database setup, and `app/main.py` for router registration and shared error handling. `models.py` and `schemas.py` remain at the `app/` root. Imports, the Alembic environment, and tests were updated. 

## Database configuration change

At the user's request, Codex replaced full database URLs in environment settings with `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `TEST_DB_NAME`. It changed `app/database.py` to build the PostgreSQL connection with SQLAlchemy `URL.create`, avoiding manual URL encoding when a password contains characters such as `@`, `/`, `?`, `#`, or `%`. Alembic, the test fixture, CI, `.env.example`, and the README were updated to use those variables. Two URL construction tests were added. The resulting suite passed 19 tests against PostgreSQL 16 with a special-character password value in the environment.

Codex added a bounded SQLAlchemy connection pool with a shared engine and session factory per API worker. Pool size, overflow, wait timeout, and recycle interval are configurable through environment variables; connections are checked before reuse and the pool is disposed on shutdown. A pool reuse test was added, and the PostgreSQL suite passed 20 tests after this change.

Codex added optional development seed data through the existing trade and mark services. The seed test confirmed derived positions, weighted-average PnL, rerun idempotency, and preservation of newer marks. The full PostgreSQL suite passed 21 tests. The seed CLI was run twice on a temporary migrated database: the first run created five trades and three marks; the second created no trades.

Codex then standardized timestamp handling: timezone-aware inputs are normalized to UTC, application and migration database sessions use UTC, and API timestamps are serialized with the IST `+05:30` offset. A PostgreSQL test checked stored trade, position, and mark timestamps plus trade, price, position, and reconciliation responses.

## Decimal response formatting

After a position response showed fixed-scale values such as `"15.000000000000"` and scientific notation such as `"0E-12"`, Codex added a shared formatter for financial API strings. It now returns `"15"` and `"0"` while preserving Decimal calculations and database precision. The formatter is used by trade, position, price, and reconciliation responses. Tests covered zero, fractional values, exponent notation, and seeded API output; the full PostgreSQL suite passed 28 tests.

PostgreSQL concurrency was exercised with separate sessions and coordinated threads against the temporary local server.
