"""Στοιχείο 31 — Εύρος γονάτου (μόνο Professional).

Καταγραφή για τη Μεσομορφία· δεν κατατάσσει τον σκελετό και δεν έχει στόχο. Δύο μετρήσεις· αν διαφέρουν πάνω από
0,2 cm, τρίτη. Τιμή = μέσος όρος των δύο ή διάμεσος των τριών. Αποδεκτό εύρος 7,0–13,0 cm.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from statistics import median

from davinci import element_01 as e01
from davinci import element_04 as e04
from davinci import element_46 as e46

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_31.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class KneeBreadthResult:
    knee_breadth_cm: float | None  # η τιμή που αποθηκεύεται για τη Μεσομορφία
    measured_by: str | None = None
    side: str = "δεξί"
    uncertain: bool = False
    needs_third: bool = False
    messages: tuple[str, ...] = ()


def combine(measurements: list[float]) -> tuple[float | None, bool]:
    """(τιμή, χρειάζεται τρίτη). Δύο: μέσος όρος αν η διαφορά ≤ 0,2 cm· τρεις: διάμεσος."""
    d = load_data()
    dec = [Decimal(repr(x)) for x in measurements]
    if len(dec) == 2:
        if abs(dec[0] - dec[1]) > Decimal(repr(d["second_measurement_max_diff_cm"])):
            return None, True
        return float((dec[0] + dec[1]) / 2), False
    if len(dec) == 3:
        return float(median(dec)), False
    raise e01.InvalidInput("Χρειάζονται δύο μετρήσεις (ή τρεις, όταν οι δύο διαφέρουν πάνω από 0,2 cm).")


def assess(measurements: list[float] | None, user: e01.UserCategories, weight_kg: float, *,
           measured_by: str = "Άλλο άτομο", side: str = "δεξί", edema_or_bruise: bool = False,
           injured_right: bool = False) -> KneeBreadthResult:
    """measurements: οι μετρήσεις σε cm (δύο ή τρεις)· None = δεν μετρήθηκε.

    injured_right: τραυματισμός, πρόθεση ή αρθρίτιδα στο δεξί γόνατο. Με side="αριστερό" καταγράφεται το αριστερό·
    αλλιώς δεν καταγράφεται (σύμβαση συστήματος).
    """
    d = load_data()
    m = d["messages"]
    if not e46.element_available("31", user.level):
        return KneeBreadthResult(None, messages=(e46.normal_message("31"),))
    if not measurements:
        return KneeBreadthResult(None, messages=(m["not_measured"],))
    if measured_by not in d["measured_by"]:
        raise e01.InvalidInput(f"«Ποιος μέτρησε»: {', '.join(d['measured_by'])}.")
    if side not in ("δεξί", "αριστερό"):
        raise e01.InvalidInput("Πλευρά: «δεξί» ή «αριστερό».")
    if injured_right and side == "δεξί":
        return KneeBreadthResult(None, measured_by, side, messages=(m["injury"],))
    lo, hi = d["accepted_range_cm"]
    if any(not (lo <= x <= hi) for x in measurements):
        return KneeBreadthResult(None, measured_by, side, messages=(m["out_of_range"],))
    value, third = combine(list(measurements))
    if third:
        return KneeBreadthResult(None, measured_by, side, needs_third=True, messages=(m["third"],))

    if e01.is_minor(user.age):
        msgs = [m["minor"]]
    elif user.pregnant_or_breastfeeding:
        msgs = [m["pregnancy"]]
    else:
        msgs = [m["normal"]]
    if measured_by == "Ο ίδιος":
        msgs.append(m["self"])
    if edema_or_bruise:
        msgs.append(m["edema"])
    if e04.bmi(weight_kg, user.height_cm) >= d["high_bmi_note_from"]:
        msgs.append(m["high_bmi"])
    uncertain = edema_or_bruise or side == "αριστερό"
    return KneeBreadthResult(value, measured_by, side, uncertain, False, tuple(msgs))


def info() -> dict:
    """Κουμπί ⓘ (Πίνακες 8, 9)· τίτλος, βήματα, ✕ (χωρίς βίντεο, απόφαση του χρήστη)."""
    return load_data()["measurement"]
