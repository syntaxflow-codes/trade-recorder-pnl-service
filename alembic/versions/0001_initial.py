"""Initial immutable trade ledger, positions, and marks.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("trades",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("venue", sa.String(64), nullable=False),
        sa.Column("trade_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("price", sa.Numeric(28, 12), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("realized_increment", sa.Numeric(38, 12), nullable=False),
        sa.UniqueConstraint("venue", "trade_id", name="uq_trade_key"),
        sa.UniqueConstraint("venue", "symbol", "sequence", name="uq_trade_sequence"),
        sa.CheckConstraint("quantity > 0 AND price > 0", name="ck_trade_positive"))
    op.create_index("ix_trades_position_order", "trades", ["venue", "symbol", "sequence"])
    op.create_index("ix_trades_event", "trades", ["venue", "event_at"])
    op.create_table("positions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("venue", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("cost_basis", sa.Numeric(38, 12), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(38, 12), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True)),
        sa.Column("last_sequence", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("venue", "symbol", name="uq_position"),
        sa.CheckConstraint("quantity >= 0", name="ck_position_quantity"))
    op.create_table("marks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("venue", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("price", sa.Numeric(28, 12), nullable=False),
        sa.Column("price_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("venue", "symbol", name="uq_mark"),
        sa.CheckConstraint("price > 0", name="ck_mark_positive"))

def downgrade():
    op.drop_table("marks")
    op.drop_table("positions")
    op.drop_index("ix_trades_event", "trades")
    op.drop_index("ix_trades_position_order", "trades")
    op.drop_table("trades")
