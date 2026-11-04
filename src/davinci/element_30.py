"""Στοιχείο 30 — Εύρος αγκώνα (μόνο Professional).

Κατάταξη σκελετού: Μικρός ≤ 15ο · Μεγάλος ≥ 85ο εκατοστημόριο NHANES III, κατά φύλο, δεκαετία και καταγωγή.
Ομάδα 1 (18–74): δεύτερη σύγκριση με τη Δαλματία. Η κατάταξη είναι πάντα «Ενδεικτική» και δεν αλλάζει κανέναν στόχο.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_46 as e46

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_30.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def decade(age: int) -> str:
    """18–19 → 20–29 (μήνυμα Υ)."""
    if age < 30:
        return "20–29"
    if age >= 80:
        return "80+"
    lo = age // 10 * 10
    return f"{lo}–{lo + 9}"


def classify(value_cm: float, limits: dict) -> str:
    small, medium, large = load_data()["categories"]
    v = Decimal(repr(value_cm))
    if v <= Decimal(repr(limits["small_le"])):
        return small
    if v >= Decimal(repr(limits["large_ge"])):
        return large
    return medium


def nhanes_limits(user: e01.UserCategories) -> tuple[dict, str, bool]:
    """(όρια, γραμμή, έγινε αλλαγή σε «όλος ο πληθυσμός» λόγω *)."""
    n = load_data()["nhanes_iii"]
    group = user.effective_group or "5"
    row = n["row_for_group"][group]
    col = decade(user.age)
    cell = n[user.sex][row][col]
    if cell is None:
        return n[user.sex]["all"][col], "all", True
    return cell, row, False


def near_limit(value_cm: float, limits: dict) -> bool:
    d = Decimal(repr(load_data()["near_limit_cm"]))
    v = Decimal(repr(value_cm))
    return any(abs(v - Decimal(repr(limits[k]))) <= d for k in ("small_le", "large_ge"))


@dataclass(frozen=True)
class ElbowResult:
    elbow_cm: float | None
    frame: str  # κατηγορία ή «Δεν έχει οριστεί»
    frame_europe: str | None = None  # Δαλματία (μόνο ομάδα 1, 18–74)
    limits: dict | None = None
    evaluated: bool = False
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(elbow_cm: float | None, user: e01.UserCategories, *, left_arm: bool = False,
           elbow_condition: bool = False) -> ElbowResult:
    """elbow_condition: δηλωμένο κάταγμα, φλεγμονή ή οίδημα στον αγκώνα."""
    d = load_data()
    m = d["messages"]
    nd = d["not_defined"]
    if not e46.element_available("30", user.level):
        return ElbowResult(None, nd, messages=(e46.normal_message("30"),))
    if elbow_cm is not None and elbow_cm <= 0:
        raise e01.InvalidInput("Το εύρος αγκώνα πρέπει να είναι θετικό.")
    # Βήμα 1
    if elbow_cm is None:
        return ElbowResult(None, nd, messages=(m["S"],))
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return ElbowResult(elbow_cm, nd, messages=(m["R"],))
    if elbow_condition:
        return ElbowResult(elbow_cm, nd, messages=(m["T"],))

    group = user.effective_group or "5"
    limits, row, star = nhanes_limits(user)  # Βήματα 2–3
    frame = classify(elbow_cm, limits)  # Βήμα 4
    msgs = [m["HP1"] if group == "1" else m["HP2"]]  # Βήμα 8
    europe = None
    dal = d["dalmatia"]
    if group in dal["groups"] and dal["age_range"][0] <= user.age <= dal["age_range"][1]:  # Βήμα 6
        europe = classify(elbow_cm, dal[user.sex])
        if europe != frame:
            msgs.append(m["D"].replace("[κατηγορία]", europe))
    if near_limit(elbow_cm, limits):  # Βήμα 5
        msgs.append(m["O"])
    if row == "all" and not star:
        msgs.append(m["E"])
    if star:
        msgs.append(m["X"])
    if user.age < 20:
        msgs.append(m["Y"])
    if left_arm:  # Βήμα 7
        msgs.append(m["A"])
    return ElbowResult(elbow_cm, frame, europe, limits, True, True, tuple(msgs))


def info() -> dict:
    """Κουμπί ⓘ (Πίνακας 12)."""
    return load_data()["measurement"]
