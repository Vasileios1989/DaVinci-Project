"""Μορφή αριθμών στα μηνύματα: υποδιαστολή με κόμμα (Στοιχείο 44, Πίνακας 5).

Στρογγυλοποίηση μόνο στην εμφάνιση, προς τα πάνω στο μισό (σύμβαση συστήματος).
"""

from decimal import ROUND_HALF_UP, Decimal


def round_half_up(x: float, decimals: int = 1) -> float:
    q = Decimal(1).scaleb(-decimals)
    return float(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))


def num(x: float, decimals: int = 1) -> str:
    """79.4261 → «79,4»· χιλιάδες με τελεία."""
    q = Decimal(1).scaleb(-decimals)
    s = f"{Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP):,}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")
