"""Στοιχείο 16 — Πήχης χαλαρός (όριο υγείας, Canda 2015) και πήχης σφιγμένος (εκτίμηση ANSUR II).

Δύο ξεχωριστά πεδία· δεν γίνεται μετατροπή από το ένα στο άλλο.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import ansur
from davinci import element_01 as e01
from davinci import element_04 as e04

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_16.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class RelaxedResult:
    measured_cm: float | None
    category: str | None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess_relaxed(relaxed_cm: float | None, weight_kg: float, user: e01.UserCategories) -> RelaxedResult:
    d = load_data()
    m, r = d["messages"], d["relaxed_forearm"]
    if relaxed_cm is None:
        return RelaxedResult(None, None, messages=(m["no_relaxed"],))
    if relaxed_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια πήχη πρέπει να είναι θετική.")
    if user.age < r["min_age"] or user.pregnant_or_breastfeeding:
        return RelaxedResult(relaxed_cm, None, messages=(m["record_only"],))

    normal, low = r["categories"]
    cat = normal if relaxed_cm >= r[user.sex]["normal_ge"] else low
    msgs = [m["O"] if cat == normal else m["X"]]
    bmi = e04.bmi(weight_kg, user.height_cm)
    lo, hi = r["bmi_reference"]
    if bmi >= hi:
        msgs.append(m["relaxed_bmi_30"])
    elif bmi < lo:
        msgs.append(m["relaxed_bmi_18"])
    if (user.effective_group or "5") in r["indicative_ancestries"]:
        msgs.append(m["relaxed_ancestry"])
    return RelaxedResult(relaxed_cm, cat, len(msgs) > 1, tuple(msgs))


def estimate(weight_kg: float, user: e01.UserCategories) -> ansur.AnsurEstimate:
    return ansur.estimate(load_data()["ansur_ii_model"], weight_kg, user)


@dataclass(frozen=True)
class FlexedResult:
    measured_cm: float | None
    estimates: tuple[ansur.AnsurEstimate, ...] = ()
    is_minimum: bool = False
    below_expected_today: bool | None = None
    today: ansur.AnsurEstimate | None = None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess_flexed(flexed_cm: float | None, weight_kg: float, user: e01.UserCategories,
                  target_weights: Iterable[float] = ()) -> FlexedResult:
    d = load_data()
    m, mdl = d["messages"], d["ansur_ii_model"]
    if flexed_cm is not None and flexed_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια πήχη πρέπει να είναι θετική.")
    msgs: list[str] = [] if flexed_cm is not None else [m["no_flexed"]]
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return FlexedResult(flexed_cm, messages=tuple(msgs + [m["record_only"]]))

    ests = tuple(estimate(w, user) for w in target_weights)
    is_min = user.profile in mdl["minimum_for_profiles"]
    msgs.insert(0, m["A"])
    if is_min:
        msgs.append(m["B"])
    k0 = ansur.k0_messages(mdl, user, ests, m)
    indicative = bool(k0)
    today = below = None
    if flexed_cm is not None:
        today = estimate(weight_kg, user)
        below = flexed_cm < today.range_cm[0]
        if below:
            msgs.append(m["C"])
        if not today.bmi_in_range:
            indicative = True
    return FlexedResult(flexed_cm, ests, is_min, below, today, indicative, tuple(msgs + k0))
