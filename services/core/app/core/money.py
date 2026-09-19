"""Money helpers. CLAUDE.md: 'Money is Decimal / integer minor units + ISO currency.
Never float.' Every stored amount is an int of minor units (cents); every amount that
crosses a Pydantic boundary is a Decimal string, never a float.
"""

from decimal import ROUND_HALF_UP, Decimal

MINOR_UNITS_EXPONENT = 2  # cents; fine for every currency this system supports today


def to_minor_units(amount: Decimal) -> int:
    quantized = amount.quantize(Decimal(10) ** -MINOR_UNITS_EXPONENT, rounding=ROUND_HALF_UP)
    return int(quantized * (10**MINOR_UNITS_EXPONENT))


def from_minor_units(amount: int) -> Decimal:
    return Decimal(amount).scaleb(-MINOR_UNITS_EXPONENT)
