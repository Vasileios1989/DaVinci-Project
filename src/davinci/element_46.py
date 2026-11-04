"""Στοιχείο 46 — Επίπεδα μέτρησης: Normal και Professional.

Το επίπεδο ορίζει ποια πεδία ζητούνται (Κανόνας 2). Οι υπολογισμοί κάθε στοιχείου
γίνονται με όσες τιμές υπάρχουν. Ιατρικές εξετάσεις μόνο στο Professional (Κανόνας 6).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_46.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def levels() -> tuple[str, ...]:
    return tuple(load_data()["levels"])


def fields(level: str, include_medical: bool = True) -> tuple[str, ...]:
    """Πεδία που ζητά η φόρμα (Κανόνες 3, 4)."""
    f = load_data()["fields"]
    out = list(f["Normal"])
    if level == "Professional":
        out += f["Professional_extra"]
        if include_medical:
            out += f["Professional_medical_optional"]
    return tuple(out)


def element_available(element: str, level: str) -> bool:
    return level == "Professional" or element not in load_data()["professional_only_elements"]


def normal_message(element: str) -> str | None:
    """Τι εμφανίζεται στο Normal για ένα στοιχείο του Professional (Πίνακας 4)."""
    d = load_data()
    if element in d["tool_for_element"]:
        return d["messages"]["N1"].replace("[δερματοπτυχόμετρο / παχύμετρο οστών]", d["tool_for_element"][element])
    if element == "32":
        return d["messages"]["S"]
    if element in ("37", "38"):
        return d["messages"]["N2"]
    return None


def require_professional(user, what: str) -> None:
    """Κανόνας 6: στο Normal δεν καταχωρείται καμία ιατρική εξέταση."""
    if user.level != "Professional":
        from davinci.element_01 import InvalidInput

        raise InvalidInput(f"{what}: μόνο στο επίπεδο Professional (Στοιχείο 46, Κανόνας 6).")


def medical_entry_message() -> str:
    return load_data()["messages"]["N6"]
