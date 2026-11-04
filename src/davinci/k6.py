"""Κανόνας Κ6: όταν ένα νεότερο στοιχείο αντικαθιστά μήνυμα παλιότερου, το παλιό έγγραφο δεν αλλάζει·
η αντικατάσταση γράφεται στα δεδομένα του παλιού στοιχείου («k6_replacements») και εφαρμόζεται εδώ.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=None)
def _messages(element: str) -> dict:
    return json.loads((DATA_DIR / f"element_{element}.json").read_text(encoding="utf-8"))["messages"]


def message(d: dict, key: str) -> str:
    rep = d.get("k6_replacements", {}).get(key)
    if rep is None:
        return d["messages"][key]
    return _messages(rep["element"])[rep["key"]]
