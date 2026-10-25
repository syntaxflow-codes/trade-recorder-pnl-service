from datetime import datetime, timedelta, timezone
import re
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, BeforeValidator, field_validator, model_validator

def amount(raw):
    if not isinstance(raw, str):
        raise ValueError("amount must be a decimal string")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValueError("invalid decimal string")
    if not value.is_finite() or value <= 0:
        raise ValueError("amount must be positive and finite")
    if value.as_tuple().exponent < -12 or value >= Decimal("1e16"):
        raise ValueError("amount exceeds NUMERIC(28,12) precision or scale")
    return value

Amount = Annotated[Decimal, BeforeValidator(amount)]

def normalize_venue(v):
    if not isinstance(v, str) or not v.strip() or len(v.strip()) > 64:
        raise ValueError("invalid venue")
    value = v.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value):
        raise ValueError("venue must contain ASCII letters, digits, dot, underscore, or hyphen")
    return value

def normalize_symbol(v):
    if not isinstance(v, str) or not v.strip() or len(v.strip()) > 64:
        raise ValueError("invalid symbol")
    value = v.strip().upper()
    parts = value.split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Z0-9]+", p) for p in parts):
        raise ValueError("symbol must be a pair such as BTC/USDT")
    return value

def aware(v):
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return v.astimezone(timezone.utc)


IST = timezone(timedelta(hours=5, minutes=30))


def format_ist(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("cannot format a naive timestamp")
    return value.astimezone(IST).isoformat()

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class TradeIn(StrictModel):
    venue: str
    trade_id: str = Field(min_length=1, max_length=128)
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Amount
    price: Amount
    timestamp: datetime

    _venue = field_validator("venue")(normalize_venue)
    _symbol = field_validator("symbol")(normalize_symbol)
    _timestamp = field_validator("timestamp")(aware)

    @field_validator("trade_id")
    @classmethod
    def valid_trade_id(cls, v):
        if "\x00" in v:
            raise ValueError("trade_id cannot contain NUL")
        return v

class PriceIn(StrictModel):
    venue: str
    symbol: str
    price: Amount
    timestamp: datetime
    _venue = field_validator("venue")(normalize_venue)
    _symbol = field_validator("symbol")(normalize_symbol)
    _timestamp = field_validator("timestamp")(aware)

class VenueSnapshot(StrictModel):
    venue: str
    start: datetime
    end: datetime
    complete: Literal[True]
    trades: list[TradeIn] = Field(max_length=1000)
    _venue = field_validator("venue")(normalize_venue)
    _start = field_validator("start")(aware)
    _end = field_validator("end")(aware)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start >= self.end:
            raise ValueError("start must precede end")
        if any(t.venue != self.venue or not self.start <= t.timestamp < self.end for t in self.trades):
            raise ValueError("all snapshot trades must match venue and interval")
        ids = [t.trade_id for t in self.trades]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate trade_id in snapshot")
        return self
