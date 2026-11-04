"""Στοιχείο 22 — Λόγος Μέσης-Ισχίου (ΛΜΙ).

Ταξινόμηση με ένα όριο του ΠΟΥ (≥ 0,90 άνδρες / ≥ 0,85 γυναίκες), ίδιο σε όλα τα προφίλ και σε κάθε ΔΜΣ.
Πληροφορία: μέση Ζ = όριο × αναμενόμενο ισχίο (Στοιχείο 11), Κ = 0,50 × ύψος (Στοιχείο 05), Μ = min(Ζ, Κ).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import element_01 as e01
from davinci import element_05 as e05
from davinci import element_11 as e11
from davinci.fmt import num
from davinci.ratios import fmt_ratio, ratio2

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_22.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def threshold(sex: str) -> float:
    return load_data()["threshold"][sex]


def classify(ratio_2dp: float, sex: str) -> str:
    below, high = load_data()["threshold"]["categories"]
    return high if ratio_2dp >= threshold(sex) else below


@dataclass(frozen=True)
class WaistRow:
    target_weight_kg: float
    target_fat_percent: float
    expected_hip_cm: float  # Υ
    waist_for_whr_cm: float  # Ζ («κάτω από»)
    waist_for_whtr_cm: float  # Κ («κάτω από»)
    waist_for_both_cm: float  # Μ («κάτω από»)


def waist_rows(user: e01.UserCategories, targets: Iterable[tuple[float, float]]) -> tuple[WaistRow, ...]:
    k = e05.load_data()["target_ratio"] * user.height_cm
    out = []
    for w, f in targets:
        hip = e11.estimate(w, f, user.sex, user.height_cm).hip_cm
        z = threshold(user.sex) * hip
        out.append(WaistRow(w, f, hip, z, k, min(z, k)))
    return tuple(out)


@dataclass(frozen=True)
class WhrResult:
    ratio: float | None  # δύο δεκαδικά
    category: str | None
    rows: tuple[WaistRow, ...] = ()
    out_of_reference_label: str | None = None  # ηλικία 80+ (Στοιχείο 01)
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(waist_cm: float | None, hip_cm: float | None, user: e01.UserCategories,
           targets: Iterable[tuple[float, float]] = ()) -> WhrResult:
    """targets: (βάρος-στόχος, λίπος-στόχος %) της Φάσης 1 (Στοιχείο 03)· η πρώτη γραμμή είναι του προφίλ του χρήστη."""
    d = load_data()
    m = d["messages"]
    for v in (waist_cm, hip_cm):
        if v is not None and v <= 0:
            raise e01.InvalidInput("Οι περιφέρειες πρέπει να είναι θετικές.")
    have = waist_cm is not None and hip_cm is not None
    ratio = ratio2(waist_cm, hip_cm) if have else None
    if user.age < d["min_age"] or user.pregnant_or_breastfeeding:
        return WhrResult(ratio, None, messages=(m["record_only"],))

    rows = waist_rows(user, targets)
    msgs: list[str] = []
    category = None
    indicative = False
    if have:
        category = classify(ratio, user.sex)
        key = "U" if category == d["threshold"]["categories"][1] else "K"
        msgs.append(m[key].replace("είναι Χ,", f"είναι {fmt_ratio(ratio)},"))
    else:
        msgs.append(m["missing"])
    if rows:
        r = rows[0]
        msgs.append(m["M"].replace("(Υ cm)", f"({num(r.expected_hip_cm)} cm)")
                    .replace("κάτω από Ζ cm", f"κάτω από {num(r.waist_for_whr_cm)} cm")
                    .replace("κάτω από Κ cm", f"κάτω από {num(r.waist_for_whtr_cm)} cm")
                    .replace("κάτω από Μ cm", f"κάτω από {num(r.waist_for_both_cm)} cm"))
    if user.profile in ("Αθλητικό", "Bodybuilding"):
        msgs.append(m["P"])
    msgs.append(m["T"])
    if have:
        kind = d["ancestry_message"].get(user.effective_group or "5")
        if kind:
            msgs.append(m[kind])
            indicative = True
    return WhrResult(ratio, category, rows, e01.zone_for_age(user.age).label, indicative, tuple(msgs))
