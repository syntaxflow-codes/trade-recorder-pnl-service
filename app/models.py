from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

Q = Numeric(28, 12)
M = Numeric(38, 12)

class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("venue", "trade_id", name="uq_trade_key"),
        UniqueConstraint("venue", "symbol", "sequence", name="uq_trade_sequence"),
        CheckConstraint("quantity > 0 AND price > 0", name="ck_trade_positive"),
        Index("ix_trades_position_order", "venue", "symbol", "sequence"),
        Index("ix_trades_event", "venue", "event_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    venue: Mapped[str] = mapped_column(String(64))
    trade_id: Mapped[str] = mapped_column(String(128))
    symbol: Mapped[str] = mapped_column(String(64))
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[Decimal] = mapped_column(Q)
    price: Mapped[Decimal] = mapped_column(Q)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    sequence: Mapped[int] = mapped_column(BigInteger)
    realized_increment: Mapped[Decimal] = mapped_column(M)

class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("venue", "symbol", name="uq_position"), CheckConstraint("quantity >= 0", name="ck_position_quantity"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    venue: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[Decimal] = mapped_column(Q)
    cost_basis: Mapped[Decimal] = mapped_column(M)
    realized_pnl: Mapped[Decimal] = mapped_column(M)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sequence: Mapped[int] = mapped_column(BigInteger, default=0)

class Mark(Base):
    __tablename__ = "marks"
    __table_args__ = (UniqueConstraint("venue", "symbol", name="uq_mark"), CheckConstraint("price > 0", name="ck_mark_positive"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    venue: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(64))
    price: Mapped[Decimal] = mapped_column(Q)
    price_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
