"""Pure weighted-average accounting. All stored monetary values have 12 decimal places."""
from dataclasses import dataclass
from decimal import Decimal, Context, ROUND_HALF_EVEN, localcontext

STEP = Decimal("0.000000000001")
CALC = Context(prec=80, rounding=ROUND_HALF_EVEN)

class AccountingError(ValueError):
    pass


def decimal_string(value: Decimal) -> str:
    """Render a Decimal without exponent notation or insignificant zeroes."""
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def money(value: Decimal) -> Decimal:
    with localcontext(CALC):
        result = value.quantize(STEP, rounding=ROUND_HALF_EVEN)
    if abs(result) >= Decimal("1e26"):
        raise AccountingError("accounting amount exceeds NUMERIC(38,12)")
    return result

@dataclass(frozen=True)
class State:
    quantity: Decimal = Decimal(0)
    cost_basis: Decimal = Decimal(0)
    realized_pnl: Decimal = Decimal(0)

def apply_trade(state: State, side: str, quantity: Decimal, price: Decimal) -> tuple[State, Decimal]:
    with localcontext(CALC):
        if side == "BUY":
            new_q = state.quantity + quantity
            if new_q >= Decimal("1e16"):
                raise AccountingError("position quantity exceeds NUMERIC(28,12)")
            return State(new_q, money(state.cost_basis + quantity * price), state.realized_pnl), Decimal(0)
        if side != "SELL":
            raise AccountingError("invalid side")
        if quantity > state.quantity:
            raise AccountingError("insufficient holdings")
        relieved = state.cost_basis if quantity == state.quantity else money(quantity * state.cost_basis / state.quantity)
        increment = money(quantity * price - relieved)
        new_q = state.quantity - quantity
        new_cost = Decimal(0) if new_q == 0 else money(state.cost_basis - relieved)
        return State(new_q, new_cost, money(state.realized_pnl + increment)), increment

def valuation(state: State, mark: Decimal | None) -> dict:
    with localcontext(CALC):
        avg = None if state.quantity == 0 else decimal_string(state.cost_basis / state.quantity)
        unrealized = None if state.quantity > 0 and mark is None else money((state.quantity * mark if mark is not None else Decimal(0)) - state.cost_basis)
        total = None if unrealized is None else money(state.realized_pnl + unrealized)
    return {"average_cost": avg, "unrealized_pnl": None if unrealized is None else decimal_string(unrealized), "total_pnl": None if total is None else decimal_string(total)}
