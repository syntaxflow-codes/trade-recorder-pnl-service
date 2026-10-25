from decimal import Decimal as D
import pytest
from app.services.accounting import State, apply_trade, decimal_string, valuation

def test_worked_example():
    s = State()
    for side, q, p in [("BUY", "10", "100"), ("BUY", "10", "110"), ("SELL", "5", "120")]:
        s, _ = apply_trade(s, side, D(q), D(p))
    v = valuation(s, D("125"))
    assert s.quantity == 15 and s.cost_basis == 1575 and s.realized_pnl == 75
    assert D(v["average_cost"]) == 105
    assert D(v["unrealized_pnl"]) == 300 and D(v["total_pnl"]) == 375

def test_full_close_reopen_and_fraction():
    s, _ = apply_trade(State(), "BUY", D("0.3"), D("0.1"))
    s, inc = apply_trade(s, "SELL", D("0.1"), D("0.2"))
    assert s.quantity == D("0.2") and s.cost_basis == D("0.02") and inc == D("0.01")
    s, _ = apply_trade(s, "SELL", D("0.2"), D("0.2"))
    assert s.quantity == s.cost_basis == 0
    assert valuation(s, None)["average_cost"] is None
    s, _ = apply_trade(s, "BUY", D("1"), D("4"))
    assert s.cost_basis == 4 and s.realized_pnl == D("0.03")

def test_oversell_pure_state_unchanged():
    original = State(D("2"), D("20"), D("0"))
    with pytest.raises(ValueError, match="insufficient"):
        apply_trade(original, "SELL", D("3"), D("15"))
    assert original.quantity == 2

def test_rounding_boundary():
    s, _ = apply_trade(State(), "BUY", D("3"), D("0.000000000001"))
    s, _ = apply_trade(s, "SELL", D("1"), D("0.000000000002"))
    assert s.cost_basis == D("0.000000000002")


@pytest.mark.parametrize(("value", "expected"), [
    ("0E-12", "0"), ("-0E-12", "0"), ("15.000000000000", "15"),
    ("105.500000000000", "105.5"), ("0.000000000001", "0.000000000001"),
    ("1E+26", "100000000000000000000000000"),
])
def test_decimal_string_is_plain_and_trimmed(value, expected):
    assert decimal_string(D(value)) == expected
