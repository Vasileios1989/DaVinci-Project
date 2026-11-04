"""Στοιχείο 11 — Περιφέρεια ισχίου.

Δεν ταξινομείται. Δίνεται εκτίμηση στο βάρος-στόχο (Heymsfield 2008): πληροφορία, όχι στόχος.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import element_01 as e01
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_11.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def body_density(fat_percent: float) -> float:
    """Siri: D = 1 / [λίπος / 0,9007 + (1 − λίπος) / 1,100]."""
    s = load_data()["siri_density"]
    f = fat_percent / 100
    return 1 / (f / s["fat"] + (1 - f) / s["ffm"])


def body_volume(weight_kg: float, fat_percent: float) -> float:
    return weight_kg / body_density(fat_percent)


@dataclass(frozen=True)
class HipEstimate:
    target_weight_kg: float
    target_fat_percent: float
    volume_l: float
    hip_cm: float
    range_cm: tuple[float, float]


def estimate(target_weight_kg: float, target_fat_percent: float, sex: str, height_cm: float) -> HipEstimate:
    h = load_data()["heymsfield_2008"]
    c = h[sex]
    v = body_volume(target_weight_kg, target_fat_percent)
    hip = math.exp(c["intercept"] + c["exponent"] * math.log(v / height_cm))
    se = h["log_se"]
    return HipEstimate(target_weight_kg, target_fat_percent, v, hip, (hip * math.exp(-se), hip * math.exp(se)))


@dataclass(frozen=True)
class HipResult:
    hip_cm: float | None
    estimates: tuple[HipEstimate, ...] = ()
    out_of_reference_label: str | None = None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(user: e01.UserCategories, hip_cm: float | None,
           targets: Iterable[tuple[float, float]] = ()) -> HipResult:
    """targets: (βάρος-στόχος, λίπος-στόχος %) της Φάσης 1 (Στοιχείο 03)."""
    d = load_data()
    m = d["messages"]
    if hip_cm is not None and hip_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια ισχίου πρέπει να είναι θετική.")
    msgs = [m["A"]]
    if hip_cm is None:
        msgs.append(m["no_hip"])
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return HipResult(hip_cm, messages=tuple(msgs + [m["record_only"]]))

    ests = tuple(estimate(w, f, user.sex, user.height_cm) for w, f in targets)
    indicative = False
    if ests:
        primary = ests[0]
        msgs.append(m["B"].replace("Χ cm", f"{num(primary.hip_cm)} cm")
                    .replace("Υ–Ζ", f"{num(primary.range_cm[0])}–{num(primary.range_cm[1])}"))
        if (user.effective_group or "5") in d["indicative_ancestries"]:
            msgs.append(m["ancestry"])
            indicative = True
    if user.profile == "Bodybuilding":
        msgs.append(m["C"])
    return HipResult(hip_cm, ests, e01.zone_for_age(user.age).label, indicative, tuple(msgs))
