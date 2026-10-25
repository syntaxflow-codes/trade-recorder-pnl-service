from ..schemas import normalize_symbol, normalize_venue


class InvalidFilter(Exception):
    pass


def filters(venue: str | None, symbol: str | None):
    try:
        return normalize_venue(venue) if venue is not None else None, normalize_symbol(symbol) if symbol is not None else None
    except ValueError as exc:
        raise InvalidFilter(str(exc)) from exc
