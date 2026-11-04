"""Στοιχείο 25 — Λόγος Πήχη-Δικεφάλου (ΛΠΔ).

Πήχης σφιγμένος (Στοιχείο 16) / δικέφαλος σφιγμένος (Στοιχείο 15). Χωρίς όριο και χωρίς στόχο· θέση στα
εκατοστημόρια ANSUR II. Αναμενόμενος λόγος: εκτίμηση Στοιχείου 16 / εκτίμηση Στοιχείου 15 στο βάρος-στόχο.
Τα χαλαρά πεδία δεν χρησιμοποιούνται.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import element_01 as e01
from davinci import element_15 as e15
from davinci import element_16 as e16
from davinci.fmt import num
from davinci.ratios import PercentileResult, TargetRow, assess_percentile, fmt_ratio

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_25.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def target_rows(user: e01.UserCategories, target_weights: Iterable[float]) -> tuple[TargetRow, ...]:
    out = []
    for w in target_weights:
        p, b = e16.estimate(w, user).value_cm, e15.estimate(w, user).value_cm
        out.append(TargetRow(w, p, b, p / b))
    return tuple(out)


def fill_e(text: str, r: TargetRow) -> str:
    return (text.replace("δικέφαλος Υ cm", f"δικέφαλος {num(r.denominator_cm)} cm")
            .replace("πήχης Ζ cm", f"πήχης {num(r.numerator_cm)} cm")
            .replace("περίπου Λ.", f"περίπου {fmt_ratio(r.ratio)}."))


def assess(forearm_flexed_cm: float | None, biceps_flexed_cm: float | None, user: e01.UserCategories,
           target_weights: Iterable[float] = (), injured_or_swollen: bool = False) -> PercentileResult:
    """Μόνο σφιγμένες τιμές, δεξί χέρι. injured_or_swollen: τραυματισμός ή πρήξιμο στο δεξί χέρι → μόνο καταγραφή."""
    d = load_data()
    exclusion = ("record", d["messages"]["injury"]) if injured_or_swollen else None
    return assess_percentile(d, forearm_flexed_cm, biceps_flexed_cm, user, target_rows(user, target_weights), fill_e,
                             exclusion)
