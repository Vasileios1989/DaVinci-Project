"""Στοιχείο 04 — Δείκτης Μάζας Σώματος (ΔΜΣ).

Υλοποιεί το έγγραφο DaVinci_04 (Πίνακες 2–7, 9, 11). Όρια και μηνύματα στο
data/element_04.json· καμπύλες παιδιών στο data/who_bfa_2007.json (ΠΟΥ, anthroplus).
Ο ΔΜΣ είναι μόνο ταξινόμηση υγείας: δεν υπάρχει στόχος ΔΜΣ (Κανόνας 1).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SEX_CODE = {"Άνδρας": 1, "Γυναίκα": 2}


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads((DATA_DIR / "element_04.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _lms_table() -> dict[tuple[int, int], tuple[float, float, float]]:
    d = json.loads((DATA_DIR / "who_bfa_2007.json").read_text(encoding="utf-8"))
    return {(r["sex"], r["month"]): (r["L"], r["M"], r["S"]) for r in d["rows"]}


# --- Τύποι (Πίνακας 6) -----------------------------------------------------------

def bmi(weight_kg: float, height_cm: float) -> float:
    if weight_kg <= 0:
        raise e01.InvalidInput("Το βάρος πρέπει να είναι θετικό.")
    h = e01.validate_height(height_cm) / 100
    return weight_kg / (h * h)


def lms_at(sex: str, age_months: float) -> tuple[float, float, float]:
    """L, M, S με γραμμική παρεμβολή ανάμεσα στους δύο πλησιέστερους μήνες (όπως anthroplus)."""
    if not (60 <= age_months < 229):
        raise ValueError(f"Οι καμπύλες ΠΟΥ καλύπτουν 60–229 μήνες, όχι {age_months:.2f}.")
    code = SEX_CODE[sex]
    lo = math.trunc(age_months)
    frac = age_months - lo
    low = _lms_table()[(code, lo)]
    if frac == 0:
        return low
    upp = _lms_table()[(code, lo + 1)]
    return tuple(a + frac * (b - a) for a, b in zip(low, upp))  # type: ignore[return-value]


def sd_value(L: float, M: float, S: float, k: float) -> float:
    """Τιμή ΔΜΣ στο SD k: M × (1 + L·S·k)^(1/L)."""
    return M * (1 + L * S * k) ** (1 / L)


def z_score(value: float, L: float, M: float, S: float) -> float:
    """z με τη διόρθωση του ΠΟΥ για |z| > 3 (anthro, compute_zscore_adjusted)."""
    z = ((value / M) ** L - 1) / (L * S)
    if z > 3:
        sd3, sd2 = sd_value(L, M, S, 3), sd_value(L, M, S, 2)
        z = 3 + (value - sd3) / (sd3 - sd2)
    elif z < -3:
        sd3n, sd2n = sd_value(L, M, S, -3), sd_value(L, M, S, -2)
        z = -3 + (value - sd3n) / (sd2n - sd3n)
    return z


# --- Ταξινόμηση -----------------------------------------------------------------

def child_category(z: float) -> str:
    if z < -3:
        return "Σοβαρή λιποβαρία"
    if z < -2:
        return "Λιποβαρία"
    if z <= 1:
        return "Φυσιολογικό"
    if z <= 2:
        return "Υπέρβαρο"
    return "Παχυσαρκία"


def adult_table_name(group: str | None) -> str:
    """Ποιος πίνακας ενηλίκων ισχύει για την ομάδα (Πίνακας 9). None → γενικά (Κ5)."""
    if group is not None and group in load_data()["adult_tables"]["lower"]["groups"]:
        return "lower"
    return "general"


def adult_category(value: float, table: str) -> str:
    category = None
    for row in load_data()["adult_tables"][table]["lower_bounds"]:
        if row["from"] is None or value >= row["from"]:
            category = row["category"]
    return category


def suggest_mixed_group(parent_a: str, parent_b: str) -> str | None:
    """Κ2: αν μόνο μία από τις δύο ομάδες έχει χαμηλότερα όρια ΔΜΣ, προτείνεται αυτή."""
    lower = [g for g in (parent_a, parent_b) if adult_table_name(g) == "lower"]
    return lower[0] if len(lower) == 1 else None


@dataclass(frozen=True)
class BMIResult:
    value: float  # ακριβής τιμή· στρογγυλοποίηση μόνο στην εμφάνιση
    category: str | None  # None σε εγκυμοσύνη / θηλασμό (Κανόνας 5)
    table: str | None  # "general", "lower", "who_children" ή None
    z: float | None = None  # μόνο για 5–17
    indicative: bool = False  # «Ενδεικτική» (Κ0)
    messages: tuple[str, ...] = ()  # αυτολεξεί από το έγγραφο
    elderly_flags: tuple[str, ...] = ()
    elderly_note: str | None = None
    waist_to_height_applicable: bool = True  # Κανόνας 3
    possible_measurement_error: bool = False  # |z| > 5
    notes: tuple[str, ...] = field(default=())


def classify(
    weight_kg: float,
    user: e01.UserCategories,
    *,
    fat_in_healthy_range: bool | None = None,
) -> BMIResult:
    """Ταξινόμηση ΔΜΣ. fat_in_healthy_range: από το Στοιχείο 02 (None = δεν υπάρχει μέτρηση)."""
    d = load_data()
    msgs = d["messages"]
    value = bmi(weight_kg, user.height_cm)
    age = user.age
    w2h = value < d["rules"]["rule_3_no_waist_to_height_from_bmi"]

    if user.pregnant_or_breastfeeding:  # Κανόνας 5
        return BMIResult(value=value, category=None, table=None, waist_to_height_applicable=w2h)

    messages: list[str] = []
    indicative = False
    z = None
    implausible = False
    flags: list[str] = []
    note = None

    if e01.is_minor(age):  # Κανόνας 4: 5–17 → καμπύλες ΠΟΥ
        L, M, S = lms_at(user.sex, user.age_months_who)
        z = z_score(value, L, M, S)
        implausible = abs(z) > d["child_z_categories"]["implausible_abs_z"]
        category = child_category(z)
        table = "who_children"
        if user.ancestry != "1":  # ομάδες 2–5 και μη δηλωμένη (Κ5 → ομάδα 5)
            messages.append(msgs["K0_children_groups_2_5"])
            indicative = True
    else:  # 18+
        if user.ancestry is None:  # Κ5
            group = None
            messages.append(msgs["K0_not_declared"])
            indicative = True
        elif user.ancestry == "5" and user.mixed_chosen_group is not None:  # Κ2
            group = user.mixed_chosen_group
            messages.append(msgs["K0_mixed_chosen"].replace(
                "[όνομα ομάδας]", e01.ancestry_name(group)))
            indicative = True
        elif user.ancestry == "5":  # Κ1
            group = "5"
            messages.append(msgs["K0_group5_adult"])
            indicative = True
        else:
            group = user.ancestry
        table = adult_table_name(group)
        category = adult_category(value, table)

        eld = d["elderly"]
        if age >= eld["min_age"]:  # Πίνακας 3
            note = eld["note"]
            for f in eld["flags"]:
                if age < f["min_age"] or (f["max_age"] is not None and age > f["max_age"]):
                    continue
                hit = value < f["bmi"] if f["condition"] == "lt" else value > f["bmi"]
                if hit and f["label"] not in flags:
                    flags.append(f["label"])

    if fat_in_healthy_range and category in d["rules"]["rule_2_overweight_categories"]:
        messages.append(msgs["rule_2"])  # Κανόνας 2 / Κ3

    return BMIResult(
        value=value,
        category=category,
        table=table,
        z=z,
        indicative=indicative,
        messages=tuple(messages),
        elderly_flags=tuple(flags),
        elderly_note=note,
        waist_to_height_applicable=w2h,
        possible_measurement_error=implausible,
    )
