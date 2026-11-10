"""Στοιχείο 02 — Ποσοστό σωματικού λίπους.

Δύο ανεξάρτητοι τρόποι (Ενότητα 1): όριο προφίλ (πού θέλει να φτάσει) και
ταξινόμηση υγείας (πόσο υγιής είναι τώρα, ίδια για όλα τα προφίλ).
Όρια και μηνύματα στο data/element_02.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_02.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def validate_fat_percent(fat_percent: float) -> float:
    if not (0 < fat_percent < 100):
        raise e01.InvalidInput(f"Λίπος {fat_percent}% εκτός 0–100.")
    return fat_percent


# --- Πίνακας ταξινόμησης για ενήλικες ------------------------------------------

@dataclass(frozen=True)
class AdultRow:
    healthy: tuple[float, float]
    overweight_from: float
    obese_from: float
    table: str  # "general" ή "asian"


def adult_table_for(user: e01.UserCategories) -> tuple[str, list[str]]:
    """Ποιος πίνακας (4 ή 5) και ποια μηνύματα Κ0 ισχύουν (Συμπλήρωμα, Πίνακες Σ1, Σ3)."""
    d = load_data()
    msgs = d["messages"]
    if user.ancestry is None:  # Κ5
        return "general", [msgs["K0_not_declared"]]
    if user.ancestry == "5" and user.mixed_chosen_group is not None:  # Κ2
        table = d["ancestry_to_table"][user.mixed_chosen_group]["table"]
        text = msgs["K0_mixed_chosen"].replace("[όνομα ομάδας]", e01.ancestry_name(user.mixed_chosen_group))
        return table, [text]
    entry = d["ancestry_to_table"][user.ancestry]
    return entry["table"], ([msgs[entry["message"]]] if entry["message"] else [])


def adult_row(user: e01.UserCategories) -> AdultRow:
    table, _ = adult_table_for(user)
    age = user.age
    for r in load_data()["adult_health_tables"][table]["rows"]:
        if r["sex"] == user.sex and age >= r["min_age"] and (r["max_age"] is None or age <= r["max_age"]):
            return AdultRow(tuple(r["healthy"]), r["overweight_from"], r["obese_from"], table)
    raise LookupError(f"Καμία γραμμή για {user.sex}, {age} ετών.")


# --- Αποτέλεσμα ------------------------------------------------------------------

@dataclass(frozen=True)
class FatResult:
    fat_percent: float
    fat_kg: float | None  # βάρος × λίπος % (Στοιχείο 03, Β-7)
    health_category: str | None  # None σε εγκυμοσύνη/θηλασμό ή στα 5 έτη
    health_label: str | None  # τι εμφανίζεται (π.χ. ετικέτα Κανόνα 3)
    in_healthy_range: bool | None  # για τον Κανόνα 2 του Στοιχείου 04
    table: str | None  # "general", "asian", "children"
    profile_range: tuple[float, float] | None  # όριο προφίλ (None: χωρίς στόχο)
    profile_status: str | None  # "εντός", "πάνω", "κάτω"
    below_safety_floor: bool = False  # Κανόνας 4
    near_boundary: bool = False  # Κανόνας 11
    indicative: bool = False
    out_of_reference_label: str | None = None  # 80+: «Εκτός δεδομένων αναφοράς»
    messages: tuple[str, ...] = ()


def classify_adult_value(value: float, row: AdultRow) -> str:
    if value < row.healthy[0]:
        return "Χαμηλό"
    if value < row.overweight_from:
        return "Υγιές"
    if value < row.obese_from:
        return "Υπέρβαρο"
    return "Παχυσαρκία"


def classify_child_value(value: float, sex: str, age: int) -> tuple[str, tuple[float, float]]:
    lo, hi, high_from, very_from = load_data()["children_tables"][sex][str(age)]
    if value < lo:
        cat = "Χαμηλό"
    elif value < high_from:
        cat = "Φυσιολογικό"
    elif value < very_from:
        cat = "Υψηλό"
    else:
        cat = "Πολύ υψηλό"
    return cat, (lo, hi)


def profile_range(user: e01.UserCategories) -> tuple[float, float] | None:
    """Όριο προφίλ (Πίνακες 2–3). Ανήλικοι και εγκυμοσύνη/θηλασμός: κανένας στόχος."""
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return None
    if user.profile == "Υγεία":
        return adult_row(user).healthy  # Κανόνας 1
    lo, hi = load_data()["profile_ranges"][user.profile][user.sex]  # Κανόνας 2
    return (lo, hi)


def profile_status(value: float, rng: tuple[float, float]) -> str:
    if value > rng[1]:
        return "πάνω"
    if value < rng[0]:
        return "κάτω"
    return "εντός"


def assess(fat_percent: float, user: e01.UserCategories, weight_kg: float | None = None) -> FatResult:
    d = load_data()
    value = validate_fat_percent(fat_percent)
    fat_kg = weight_kg * value / 100 if weight_kg is not None else None
    age = user.age

    if user.pregnant_or_breastfeeding:  # Κανόνας 10
        return FatResult(value, fat_kg, None, None, None, None, None, None)

    if e01.is_minor(age):
        if age == 5:  # Κανόνας 6
            return FatResult(value, fat_kg, None, None, None, None, None, None,
                             indicative=True, messages=(d["messages"]["K0_age_5"],))
        cat, normal = classify_child_value(value, user.sex, age)
        msgs = [] if user.ancestry == "1" else [d["messages"]["K0_children_groups_2_5"]]
        lo, _hi, high_from, very_from = d["children_tables"][user.sex][str(age)]
        # Κανόνας 11: το έγγραφο δεν τον περιορίζει σε ενήλικες· όρια ταξινόμησης των Πινάκων 6α/6β
        near = any(abs(value - b) <= d["near_boundary_units"] for b in (lo, high_from, very_from))
        return FatResult(value, fat_kg, cat, cat, cat == "Φυσιολογικό", "children", None, None,
                         near_boundary=near, indicative=bool(msgs), messages=tuple(msgs))

    row = adult_row(user)
    _, msgs = adult_table_for(user)
    msgs = list(msgs)
    zone = e01.zone_for_age(age)
    out_label = None
    if zone.label:  # 80+ (Κανόνας 8)
        out_label = zone.label
        msgs.append(d["messages"]["K0_age_80"])

    cat = classify_adult_value(value, row)
    label = cat
    if cat == "Χαμηλό" and user.profile in ("Αθλητικό", "Bodybuilding"):  # Κανόνας 3
        label = d["below_population_label"]

    boundaries = (row.healthy[0], row.overweight_from, row.obese_from)
    near = any(abs(value - b) <= d["near_boundary_units"] for b in boundaries)  # Κανόνας 11

    rng = profile_range(user)
    return FatResult(
        fat_percent=value,
        fat_kg=fat_kg,
        health_category=cat,
        health_label=label,
        in_healthy_range=cat == "Υγιές",
        table=row.table,
        profile_range=rng,
        profile_status=profile_status(value, rng) if rng else None,
        below_safety_floor=value < d["safety_floor"][user.sex],
        near_boundary=near,
        indicative=bool(msgs),
        out_of_reference_label=out_label,
        messages=tuple(msgs),
    )
