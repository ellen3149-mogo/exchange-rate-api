"""換算邏輯（純函式，不依賴外部服務，容易單元測試）。"""

from decimal import ROUND_HALF_UP, Decimal

from app.exceptions import UnsupportedCurrencyError
from app.services.rate_client import RateTable

RATE_PLACES = Decimal("0.000001")
AMOUNT_PLACES = Decimal("0.0001")


def get_rate(table: RateTable, to_currency: str) -> Decimal:
    if to_currency == table.base:
        return Decimal(1)
    rate = table.rates.get(to_currency)
    if rate is None or rate <= 0:
        raise UnsupportedCurrencyError(f"不支援的幣別：{to_currency}")
    return rate


def convert(table: RateTable, to_currency: str, amount: Decimal) -> dict:
    rate = get_rate(table, to_currency)
    return {
        "rate": rate.quantize(RATE_PLACES, ROUND_HALF_UP),
        "inverse_rate": (Decimal(1) / rate).quantize(RATE_PLACES, ROUND_HALF_UP),
        "result": (amount * rate).quantize(AMOUNT_PLACES, ROUND_HALF_UP),
    }


def filter_symbols(table: RateTable, symbols: list[str] | None) -> dict[str, Decimal]:
    if not symbols:
        return table.rates
    missing = [s for s in symbols if s not in table.rates]
    if missing:
        raise UnsupportedCurrencyError(f"不支援的幣別：{', '.join(missing)}")
    return {s: table.rates[s] for s in symbols}
