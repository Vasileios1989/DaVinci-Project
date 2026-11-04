"""Στοιχείο 32 — Οριστικοποίηση σκελετού.

Η κατηγορία σκελετού προέρχεται μόνο από το εύρος αγκώνα (Στοιχείο 30). Χωρίς αγκώνα: «Δεν έχει οριστεί».
Είναι πληροφορία, χωρίς χρώμα κινδύνου, και δεν αλλάζει κανέναν στόχο ή υπολογισμό.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_30 as e30
from davinci import element_46 as e46

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_32.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class FrameResult:
    frame: str
    elbow: e30.ElbowResult | None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def finalize(elbow_cm: float | None, user: e01.UserCategories, **elbow_kw) -> FrameResult:
    """Κανόνες 1–5. elbow_kw: left_arm, elbow_condition (Στοιχείο 30)."""
    d = load_data()
    nd = e30.load_data()["not_defined"]
    if not e46.element_available("32", user.level):
        return FrameResult(nd, None, messages=(e46.normal_message("32"),))
    r = e30.assess(elbow_cm, user, **elbow_kw)
    if r.frame == nd:
        return FrameResult(nd, r, messages=r.messages)
    p = d["messages"]["P"].replace("[κατηγορία]", r.frame)
    return FrameResult(r.frame, r, r.indicative, (p,) + r.messages)
