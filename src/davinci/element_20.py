"""Στοιχείο 20 — Περιφέρεια γάμπας (μέγιστη, όρθια).

Όριο υγείας για χαμηλή μυϊκή μάζα με διόρθωση ΔΜΣ ανά καταγωγή (Gonzalez 2021) και εκτίμηση ANSUR II.
Αθλητικό / Bodybuilding: κατώτατο όριο = max(εκτίμηση, τιμή για «φυσιολογική» στο βάρος-στόχο).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import ansur
from davinci import element_01 as e01
from davinci import k6
from davinci import element_04 as e04

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_20.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def bmi_adjustment(bmi: float, user: e01.UserCategories) -> int:
    """Πίνακας 4: προστίθεται στη μέτρηση (π.χ. −12 για ΔΜΣ ≥ 40, +5 για ΔΜΣ < 18,5 στην ομάδα 1)."""
    t = load_data()["health_threshold"]
    table = t["bmi_adjustment"][t["group_table"][user.effective_group or "5"]]
    for row in table:
        lo, hi = row["bmi_from"], row["bmi_below"]
        if (lo is None or bmi >= lo) and (hi is None or bmi < hi):
            return row[user.sex]
    raise LookupError(bmi)


def category(corrected_cm: float, sex: str) -> str:
    t = load_data()["health_threshold"]
    normal, moderate, very_low = t["categories"]
    if corrected_cm >= t[sex]["normal_ge"]:
        return normal
    if corrected_cm >= t[sex]["moderate_ge"]:
        return moderate
    return very_low


def normal_value_at(weight_kg: float, user: e01.UserCategories) -> float:
    """Τιμή για «φυσιολογική» σε δεδομένο βάρος: όριο − προσαρμογή (π.χ. 34 + 3 = 37)."""
    t = load_data()["health_threshold"]
    return t[user.sex]["normal_ge"] - bmi_adjustment(e04.bmi(weight_kg, user.height_cm), user)


def estimate(weight_kg: float, user: e01.UserCategories) -> ansur.AnsurEstimate:
    return ansur.estimate(load_data()["ansur_ii_model"], weight_kg, user)


@dataclass(frozen=True)
class CalfResult:
    calf_cm: float | None
    corrected_cm: float | None
    category: str | None
    estimates: tuple[ansur.AnsurEstimate, ...] = ()
    normal_values_at_targets: tuple[float, ...] = ()
    minimums_cm: tuple[float, ...] = ()
    below_expected_today: bool | None = None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(calf_cm: float | None, weight_kg: float, user: e01.UserCategories,
           target_weights: Iterable[float] = (), *, edema: bool = False) -> CalfResult:
    d = load_data()
    m, t, mdl = d["messages"], d["health_threshold"], d["ansur_ii_model"]
    if calf_cm is not None and calf_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια γάμπας πρέπει να είναι θετική.")
    head = [m["no_value"]] if calf_cm is None else []
    if user.age < t["min_age"] or user.pregnant_or_breastfeeding:
        return CalfResult(calf_cm, None, None, messages=tuple(head + [m["record_only"]]))
    if edema:
        return CalfResult(calf_cm, None, None, messages=tuple(head + [m["edema"]]))

    msgs = list(head)
    indicative = False
    corrected = cat = None
    if calf_cm is not None:
        bmi = e04.bmi(weight_kg, user.height_cm)
        corrected = calf_cm + bmi_adjustment(bmi, user)
        cat = category(corrected, user.sex)
        msgs.append(m[{"Φυσιολογική": "O", "Μέτρια χαμηλή": "M", "Πολύ χαμηλή": "PX"}[cat]])
        if (user.effective_group or "5") in t["indicative_ancestries"]:
            msgs.append(m["threshold_ancestry"])
            indicative = True
        if bmi >= t["bmi_k0_from"]:
            msgs.append(m["threshold_bmi_50"])
            indicative = True

    ests = tuple(estimate(w, user) for w in target_weights)
    normals = tuple(normal_value_at(e.weight_kg, user) for e in ests)
    minimums: tuple[float, ...] = ()
    if ests:
        msgs.append(m["A"])
        if user.profile in mdl["minimum_for_profiles"]:
            msgs.append(k6.message(d, "B"))
            minimums = tuple(max(e.value_cm, n) for e, n in zip(ests, normals))
        if any(e.value_cm < n for e, n in zip(ests, normals)):
            msgs.append(m["D"])
    k0 = ansur.k0_messages(mdl, user, ests, m)
    indicative = indicative or bool(k0)

    below_today = None
    if calf_cm is not None:
        today = estimate(weight_kg, user)
        below_today = calf_cm < today.range_cm[0]
        if below_today:
            msgs.append(m["C"])
        if not today.bmi_in_range:
            indicative = True
    return CalfResult(calf_cm, corrected, cat, ests, normals, minimums, below_today, indicative, tuple(msgs + k0))
