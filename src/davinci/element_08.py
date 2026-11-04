"""Στοιχείο 08 — Υγρά (Μέρος Α) και ενυδάτωση (Μέρος Β).

Η ζυγαριά δεν δείχνει αφυδάτωση (Κανόνας 2). Η ενυδάτωση ελέγχεται χωριστά:
18–59 με Βάρος–Ούρα–Δίψα, 60+ μόνο με εξέταση αίματος (Πίνακας 6).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from davinci import element_01 as e01
from davinci import element_03 as e03
from davinci import element_04 as e04
from davinci import element_46 as e46

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_08.json"
SCALE, COMPUTED, MEDICAL = "ζυγαριά", "υπολογισμένη", "ιατρική μέτρηση"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


# --- Μέρος Α: υγρά ----------------------------------------------------------------

@dataclass(frozen=True)
class WaterResult:
    source: str
    water_kg: float
    ratio: float  # ακριβής τιμή· εμφάνιση με 3 δεκαδικά
    ratio_label: str | None  # None σε ανηλίκους / εγκυμοσύνη (καμία ταξινόμηση)
    pct_of_weight: float  # μόνο πληροφορία
    out_of_reference_label: str | None = None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess_water(weight_kg: float, fat_percent: float, user: e01.UserCategories, *,
                 scale_percent: float | None = None, medical_kg: float | None = None) -> WaterResult:
    d = load_data()
    m = d["messages"]
    ffm = e03.ffm(weight_kg, fat_percent)
    msgs: list[str] = []
    indicative = False

    if medical_kg is not None:
        e46.require_professional(user, "Αραίωση ισοτόπων")
        source, kg = MEDICAL, medical_kg
    elif scale_percent is not None:
        source, kg = SCALE, e03.scale_kg(weight_kg, scale_percent)
        msgs.append(m["scale_no_hydration"])
        b = d["scale_reliable_bmi"]
        bmi = e04.bmi(weight_kg, user.height_cm)
        if bmi < b["min"] or bmi > b["max"]:  # Κανόνας 6
            msgs.append(m["bmi_out_of_range"])
            indicative = True
    else:
        source, kg = COMPUTED, d["hydration_constant"]["value"] * ffm
        msgs.append(m["computed"])

    ratio = kg / ffm
    label = out_label = None
    if e01.is_minor(user.age):
        msgs.append(m["minor"])
    elif not user.pregnant_or_breastfeeding:
        lo, hi = d["ratio_check"]["usual"]
        usual = lo <= ratio <= hi  # Κανόνας 3: ακριβείς τιμές
        label = d["ratio_check"]["labels"]["usual" if usual else "unusual"]
        if not usual:
            msgs.append(m["unusual_ratio"])
        if (user.effective_group or "5") in d["ancestry_with_message"]:
            msgs.append(m["ancestry"])
            indicative = True
        out_label = e01.zone_for_age(user.age).label

    return WaterResult(source, kg, ratio, label, kg / weight_kg * 100, out_label, indicative, tuple(msgs))


def water_target(ffm_target_kg: float) -> tuple[float, str]:
    """Κανόνας 7: 0,73 × άλιπη-στόχος, με το μήνυμα του Πίνακα 15."""
    d = load_data()
    return d["hydration_constant"]["value"] * ffm_target_kg, d["messages"]["target"]


# --- Μέρος Β: ενυδάτωση -----------------------------------------------------------

@dataclass(frozen=True)
class HydrationResult:
    method: str | None  # "Βάρος–Ούρα–Δίψα", "εξέταση αίματος", None
    result: str | None
    positives: int | None = None
    evaluated: tuple[str, ...] = ()
    indicative: bool = False
    messages: tuple[str, ...] = ()


def calculated_osmolality(na: float, k: float, glucose: float, urea: float) -> float:
    """1,86 × (Na + K) + 1,15 × γλυκόζη + ουρία + 14 (mmol/L)."""
    return 1.86 * (na + k) + 1.15 * glucose + urea + 14


def _blood(measured: float | None, calc_inputs: tuple[float, float, float, float] | None,
           msgs: list[str], indicative: bool) -> HydrationResult:
    b = load_data()["blood"]
    if measured is not None:
        res = b["measured_label"] if measured > b["measured_gt"] else None
    else:
        res = b["calculated_label"] if calculated_osmolality(*calc_inputs) > b["calculated_gt"] else None
    return HydrationResult("εξέταση αίματος", res, indicative=indicative, messages=tuple(msgs))


def assess_hydration(user: e01.UserCategories, *,
                     previous_morning_weights: Sequence[float] = (),
                     today_morning_weight: float | None = None,
                     urine_color: int | None = None,
                     thirst: float | None = None,
                     serum_osmolality: float | None = None,
                     calc_osmolality_inputs: tuple[float, float, float, float] | None = None) -> HydrationResult:
    d = load_data()
    m, meth, w = d["messages"], d["hydration_methods"], d["wut"]
    age = user.age
    has_blood = serum_osmolality is not None or calc_osmolality_inputs is not None
    if has_blood:
        e46.require_professional(user, "Εξέταση αίματος")

    if age < meth["none_below"]:
        return HydrationResult(None, None, messages=(m["minor"],))
    if user.pregnant_or_breastfeeding:  # Κανόνας 8
        return HydrationResult(None, None)

    msgs: list[str] = []
    indicative = False
    if e01.zone_for_age(age).label:  # 80+
        msgs.append(m["age_80"])
        indicative = True

    if age >= meth["blood_only_from"]:
        if not has_blood:
            return HydrationResult(None, None, messages=tuple(msgs + [m["age_60_no_blood"]]),
                                   indicative=indicative)
        return _blood(serum_osmolality, calc_osmolality_inputs, msgs, indicative)

    if has_blood:  # 18+ με διαθέσιμη εξέταση (Πίνακας 9)
        return _blood(serum_osmolality, calc_osmolality_inputs, msgs, indicative)

    positives = 0
    evaluated: list[str] = []
    recent = list(previous_morning_weights)[-w["baseline_days"]:]
    if today_morning_weight is not None and len(recent) == w["baseline_days"]:
        base = sum(recent) / len(recent)  # Κανόνας 5
        evaluated.append("Βάρος")
        positives += (base - today_morning_weight) / base > w["weight_drop_gt"]
    else:
        msgs.append(m["baseline_missing"])
    if urine_color is not None:
        lo, hi = w["urine_scale"]
        if not (lo <= urine_color <= hi) or int(urine_color) != urine_color:
            raise e01.InvalidInput(f"Χρώμα ούρων {urine_color}: κλίμακα {lo}–{hi}.")
        evaluated.append("Ούρα")
        positives += urine_color > w["urine_color_gt"]
    if thirst is not None:
        evaluated.append("Δίψα")
        positives += thirst >= w["thirst_ge"]
    if not evaluated:
        return HydrationResult("Βάρος–Ούρα–Δίψα", None, None, (), indicative, tuple(msgs))
    return HydrationResult("Βάρος–Ούρα–Δίψα", w["results"][str(positives)], positives,
                           tuple(evaluated), indicative, tuple(msgs))
