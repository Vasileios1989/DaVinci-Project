"""Στοιχείο 17 — Περιφέρεια καρπού.

Μόνο καταγραφή για τις αναλογίες. Δεν ταξινομείται, δεν κατατάσσει τον σκελετό, δεν έχει στόχο.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_04 as e04

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_17.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class WristResult:
    wrist_cm: float | None
    frame: str  # πάντα από το Στοιχείο 30· εδώ «Δεν έχει οριστεί» αν δεν υπάρχει αγκώνας
    messages: tuple[str, ...] = ()


def assess(wrist_cm: float | None, weight_kg: float, user: e01.UserCategories, *,
           elbow_breadth_measured: bool = False) -> WristResult:
    d = load_data()
    m = d["messages"]
    if wrist_cm is not None and wrist_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια καρπού πρέπει να είναι θετική.")
    frame = "από το Στοιχείο 30" if elbow_breadth_measured else "Δεν έχει οριστεί"
    if wrist_cm is None:
        return WristResult(None, frame, (m["no_value"],))
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return WristResult(wrist_cm, frame, (m["record_only"],))
    msgs = [m["A"]]
    if e04.bmi(weight_kg, user.height_cm) >= d["fat_message_bmi_from"]:
        msgs.append(m["B"])
    if not elbow_breadth_measured:
        msgs.append(m["S"])
    return WristResult(wrist_cm, frame, tuple(msgs))
