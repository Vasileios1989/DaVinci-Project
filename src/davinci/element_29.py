"""Στοιχείο 29 — Λόγος Μηρού-Γονάτου (ΛΜΓν).

Μηρός (Στοιχείο 18) / πάνω από το γόνατο (Στοιχείο 19). Χωρίς όριο και χωρίς στόχο· θέση στα εκατοστημόρια
ANSUR II κατά προσέγγιση. Αναμενόμενος λόγος: εκτίμηση 18 / εκτίμηση 19 (όχι τα κατώτατα όρια).

Κανόνας Κ6: το μήνυμα Β του Στοιχείου 18 αντικαθίσταται από το μήνυμα Δ (βλ. element_18).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import element_01 as e01
from davinci import element_18 as e18
from davinci import element_19 as e19
from davinci.fmt import num
from davinci.ratios import PercentileResult, TargetRow, assess_percentile, fmt_ratio

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_29.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def target_rows(user: e01.UserCategories, target_weights: Iterable[float]) -> tuple[TargetRow, ...]:
    out = []
    for w in target_weights:
        t, k = e18.estimate(w, user).value_cm, e19.estimate(w, user).value_cm
        out.append(TargetRow(w, t, k, t / k))
    return tuple(out)


def fill_e(text: str, r: TargetRow) -> str:
    return (text.replace("μηρός Υ cm", f"μηρός {num(r.numerator_cm)} cm")
            .replace("γόνατο Κ cm", f"γόνατο {num(r.denominator_cm)} cm")
            .replace("περίπου Λ.", f"περίπου {fmt_ratio(r.ratio)}."))


def assess(thigh_cm: float | None, above_knee_cm: float | None, user: e01.UserCategories,
           target_weights: Iterable[float] = (), *, lipedema: bool = False,
           knee_swollen_or_injured: bool = False) -> PercentileResult:
    """lipedema → μόνο καταγραφή · knee_swollen_or_injured → δεν υπολογίζεται.

    Σύμβαση συστήματος: όταν ισχύουν και τα δύο, προηγείται το γόνατο (όπως στο Στοιχείο 28).
    """
    d = load_data()
    m = d["messages"]
    exclusion = ("skip", m["knee"]) if knee_swollen_or_injured else ("record", m["lipedema"]) if lipedema else None
    return assess_percentile(d, thigh_cm, above_knee_cm, user, target_rows(user, target_weights), fill_e, exclusion)
