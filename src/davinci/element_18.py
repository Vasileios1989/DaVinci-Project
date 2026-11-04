"""Στοιχείο 18 — Περιφέρεια μηρού (1 cm κάτω από τη γλουτιαία πτυχή).

Όριο υγείας 60 cm (Heitmann 2009, προς επιβεβαίωση) και εκτίμηση ANSUR II στο βάρος-στόχο.
Αθλητικό / Bodybuilding: κατώτατο όριο = max(εκτίμηση, 60 cm).
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

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_18.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def estimate(weight_kg: float, user: e01.UserCategories) -> ansur.AnsurEstimate:
    return ansur.estimate(load_data()["ansur_ii_model"], weight_kg, user)


@dataclass(frozen=True)
class ThighResult:
    thigh_cm: float | None
    category: str | None
    estimates: tuple[ansur.AnsurEstimate, ...] = ()
    minimums_cm: tuple[float, ...] = ()  # μόνο Αθλητικό / Bodybuilding
    below_expected_today: bool | None = None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(thigh_cm: float | None, weight_kg: float, user: e01.UserCategories,
           target_weights: Iterable[float] = ()) -> ThighResult:
    d = load_data()
    m, t, mdl = d["messages"], d["health_threshold"], d["ansur_ii_model"]
    if thigh_cm is not None and thigh_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια μηρού πρέπει να είναι θετική.")
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        msgs = ([m["no_value"]] if thigh_cm is None else []) + [m["record_only"]]
        return ThighResult(thigh_cm, None, messages=tuple(msgs))

    msgs: list[str] = []
    indicative = False
    category = None
    if thigh_cm is None:
        msgs.append(m["no_value"])
    else:
        above, below = t["categories"]
        category = above if thigh_cm >= t["cm"] else below
        msgs.append(m["O"] if category == above else m["X"])
        lo_age, hi_age = t["study_age"]
        if not (lo_age <= user.age <= hi_age):
            msgs.append(m["threshold_age"])
        if (user.effective_group or "5") in t["indicative_ancestries"]:
            msgs.append(m["threshold_ancestry"])
        if e04.bmi(weight_kg, user.height_cm) >= t["bmi_k0_from"]:
            msgs.append(m["threshold_bmi_30"])
        indicative = len(msgs) > 1

    ests = tuple(estimate(w, user) for w in target_weights)
    minimums: tuple[float, ...] = ()
    if ests:
        msgs.append(m["A"])
        if user.profile in mdl["minimum_for_profiles"]:
            msgs.append(k6.message(d, "B"))
            minimums = tuple(max(e.value_cm, t["cm"]) for e in ests)
        if any(e.value_cm < t["cm"] for e in ests):
            msgs.append(m["D"])
    k0 = ansur.k0_messages(mdl, user, ests, m)
    indicative = indicative or bool(k0)

    below_today = None
    if thigh_cm is not None:
        today = estimate(weight_kg, user)
        below_today = thigh_cm < today.range_cm[0]
        if below_today:
            msgs.append(m["C"])
    return ThighResult(thigh_cm, category, ests, minimums, below_today, indicative, tuple(msgs + k0))
