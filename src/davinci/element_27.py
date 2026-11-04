"""Στοιχείο 27 — Λόγος Καρπού-Δικεφάλου (ΛΚΔ).

Καρπός (Στοιχείο 17) / δικέφαλος σφιγμένος (Στοιχείο 15). Χωρίς όριο και χωρίς στόχο· θέση στα εκατοστημόρια
ANSUR II. Αναμενόμενος λόγος: εκτίμηση καρπού / εκτίμηση σφιγμένου δικεφάλου στο βάρος-στόχο.

Η εκτίμηση του καρπού χρησιμοποιεί τον τύπο ANSUR II του Στοιχείου 17 (ln καρπός = a + b·ln ύψος + c·ln ΔΜΣ),
που εκεί είναι μόνο εξήγηση· το Στοιχείο 27 (Πίνακας 8) τον χρησιμοποιεί για τον Λ. Εδώ χρησιμεύει μόνο στο
μήνυμα Ε, όχι ως τιμή καρπού.

Κανόνας Κ6: το μήνυμα Β του Στοιχείου 15 αντικαθίσταται από το μήνυμα Δ (βλ. element_15.flexed_minimum_message).
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import element_01 as e01
from davinci import element_04 as e04
from davinci import element_15 as e15
from davinci import element_17 as e17
from davinci.fmt import num
from davinci.ratios import PercentileResult, TargetRow, assess_percentile, fmt_ratio

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_27.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def wrist_estimate(weight_kg: float, user: e01.UserCategories) -> float:
    c = e17.load_data()["ansur_ii_explanation_only"][user.sex]
    bmi = e04.bmi(weight_kg, user.height_cm)
    return math.exp(c["a"] + c["b"] * math.log(user.height_cm) + c["c"] * math.log(bmi))


def target_rows(user: e01.UserCategories, target_weights: Iterable[float]) -> tuple[TargetRow, ...]:
    out = []
    for w in target_weights:
        k, b = wrist_estimate(w, user), e15.estimate(w, user).value_cm
        out.append(TargetRow(w, k, b, k / b))
    return tuple(out)


def fill_e(text: str, r: TargetRow) -> str:
    return (text.replace("δικέφαλος Υ cm", f"δικέφαλος {num(r.denominator_cm)} cm")
            .replace("καρπός Κ cm", f"καρπός {num(r.numerator_cm)} cm")
            .replace("περίπου Λ.", f"περίπου {fmt_ratio(r.ratio)}."))


def assess(wrist_cm: float | None, biceps_flexed_cm: float | None, user: e01.UserCategories,
           target_weights: Iterable[float] = (), *, injured_or_swollen: bool = False) -> PercentileResult:
    """Μόνο σφιγμένος δικέφαλος, δεξί χέρι. injured_or_swollen: τραυματισμός ή πρήξιμο στο χέρι ή στον καρπό."""
    d = load_data()
    exclusion = ("record", d["messages"]["injury"]) if injured_or_swollen else None
    return assess_percentile(d, wrist_cm, biceps_flexed_cm, user, target_rows(user, target_weights), fill_e, exclusion)
