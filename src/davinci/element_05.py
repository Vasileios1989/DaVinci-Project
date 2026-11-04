"""Στοιχείο 05 — Περιφέρεια μέσης και λόγος μέσης / ύψους (ΛΜΥ).

Η ταξινόμηση γίνεται μόνο με τον ΛΜΥ (NICE)· η μέση μόνη της δεν ταξινομείται (Κανόνας 5).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_04 as e04

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_05.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def whtr(waist_cm: float, height_cm: float) -> float:
    if waist_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια μέσης πρέπει να είναι θετική.")
    return waist_cm / e01.validate_height(height_cm)


def whtr_category(ratio: float) -> str:
    cat = None
    for row in load_data()["classification"]["lower_bounds"]:
        if row["from"] is None or ratio >= row["from"]:
            cat = row["category"]
    return cat


@dataclass(frozen=True)
class WaistResult:
    waist_cm: float
    ratio: float  # ακριβής· εμφάνιση με 2 δεκαδικά
    category: str | None
    meaning: str | None
    target_waist_below_cm: float  # «κάτω από»
    distance_to_target_cm: float  # 0 αν είναι ήδη κάτω
    max_weight_for_classification_kg: float | None  # βάρος κάτω από το οποίο ΔΜΣ < 35
    messages: tuple[str, ...] = ()


def assess(waist_cm: float, weight_kg: float, user: e01.UserCategories) -> WaistResult:
    d = load_data()
    c, m = d["classification"], d["messages"]
    ratio = whtr(waist_cm, user.height_cm)
    h_m = user.height_cm / 100
    target = d["target_ratio"] * user.height_cm
    distance = max(0.0, waist_cm - target)
    msgs: list[str] = []
    category = meaning = None
    max_w = None

    if user.profile in ("Αθλητικό", "Bodybuilding"):
        msgs.append(m["profile_target"])

    if user.pregnant_or_breastfeeding or user.age < c["min_age"]:  # Κανόνας 4
        pass
    elif e04.bmi(weight_kg, user.height_cm) >= c["max_bmi_exclusive"]:  # Κανόνας 1
        msgs.append(m["bmi_35"])
        max_w = c["max_bmi_exclusive"] * h_m * h_m
    else:
        category = whtr_category(ratio)
        meaning = c["meaning"].get(category)
        if ratio < c["lower_bounds"][1]["from"]:  # Κανόνας 2
            msgs.append(m["below_040"])

    return WaistResult(waist_cm, ratio, category, meaning, target, distance, max_w, tuple(msgs))
